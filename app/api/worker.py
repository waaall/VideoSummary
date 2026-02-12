"""进程内任务队列与工作线程模块。

负责将视频/音频/字幕的处理请求封装为 CacheJob，通过多线程工作队列
异步执行固定流水线（下载 → 转录 → 摘要），并将产物打包为缓存 Bundle。

整体架构：
  API 层提交 CacheJob → JobQueue 入队 → 工作线程消费 →
  执行 url/local 流水线 → 校验摘要 → 写入 Bundle → 更新缓存状态
"""
from __future__ import annotations

import hashlib
import json
import queue
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.api.persistence import get_store
from app.cache.bundle import ArtifactInfo, BundleManager, BundleManifest
from app.cache.cache_service import get_cache_service
from app.core.profile import get_processing_profile
from app.core.utils.logger import setup_logger
from app.pipeline.context import PipelineContext
from app.pipeline.nodes.core import (
    DownloadSubtitleNode,
    DownloadVideoNode,
    ExtractAudioNode,
    FetchMetadataNode,
    ParseSubtitleNode,
    TextSummarizeNode,
    TranscribeNode,
    ValidateSubtitleNode,
)

logger = setup_logger("worker")

# 摘要文本以这些前缀开头时，视为生成失败（LLM 返回了拒绝/兜底回答）
INVALID_SUMMARY_PREFIXES = (
    "无法生成摘要",
    "总结生成失败",
    "无有效信息",
)


@dataclass
class CacheJob:
    """一次缓存构建任务的描述。

    Attributes:
        job_id: 任务唯一标识，用于日志追踪和临时目录命名。
        cache_key: 缓存键，标识最终产物在缓存体系中的位置。
        source_type: 输入来源类型，"url" 表示在线视频，"local" 表示本地上传文件。
        source_url: 在线视频地址，仅 source_type="url" 时使用。
        file_hash: 上传文件的 SHA256 哈希，仅 source_type="local" 时使用，
                   用于从持久化存储中查找对应的上传记录。
        request_id: 关联的 API 请求 ID，用于日志链路追踪。
    """

    job_id: str
    cache_key: str
    source_type: str  # "url" | "local"
    source_url: Optional[str] = None
    file_hash: Optional[str] = None
    request_id: Optional[str] = None


class JobQueue:
    """基于线程的任务队列，管理多个工作线程并发消费 CacheJob。

    通过 start()/stop() 控制生命周期，enqueue() 提交任务。
    内部使用 threading.Event 实现优雅停止，queue.Queue 保证线程安全的任务分发。
    """

    def __init__(self, worker_count: int = 1) -> None:
        self.worker_count = worker_count
        self._queue: "queue.Queue[CacheJob]" = queue.Queue()
        self._stop_event = threading.Event()
        self._workers: list[threading.Thread] = []

    def start(self) -> None:
        """启动工作线程。worker_count <= 0 时不启动；已启动时幂等返回。"""
        if self.worker_count <= 0:
            return
        if self._workers:
            return
        for idx in range(self.worker_count):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"cache-worker-{idx}",
                daemon=True,  # 守护线程，主进程退出时自动终止
            )
            worker.start()
            self._workers.append(worker)

    def stop(self) -> None:
        """通知所有工作线程停止（非阻塞，线程将在当前任务完成后退出）。"""
        self._stop_event.set()

    def enqueue(self, job: CacheJob) -> None:
        """将任务放入队列，等待工作线程消费。"""
        self._queue.put(job)

    def _worker_loop(self) -> None:
        """工作线程主循环：轮询队列取任务并执行，收到停止信号后退出。"""
        while not self._stop_event.is_set():
            try:
                # 带超时的阻塞获取，超时后重新检查停止信号
                job = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._process_cache_job(job)
            finally:
                self._queue.task_done()

    def _log_prefix(self, job: CacheJob) -> str:
        """构造结构化日志前缀，包含请求和任务的关键标识。"""
        request_id = job.request_id or "-"
        return (
            f"request_id={request_id} job_id={job.job_id} "
            f"cache_key={job.cache_key} source_type={job.source_type}"
        )

    def _is_summary_text_valid(self, text: Optional[str]) -> bool:
        """校验摘要文本是否有效：非空且不以已知的失败前缀开头。"""
        if not text:
            return False
        stripped = text.strip()
        if not stripped:
            return False
        for prefix in INVALID_SUMMARY_PREFIXES:
            if stripped.startswith(prefix):
                return False
        return True

    def _compute_file_hash(self, file_path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
        """分块计算文件 SHA256 哈希，避免大文件一次性读入内存。"""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def _write_asr_json(self, ctx: PipelineContext, target_dir: Path) -> None:
        """将语音识别（ASR）结果序列化为 JSON 写入产物目录。"""
        asr_data = ctx.get("asr_data")
        if not asr_data:
            return
        asr_path = target_dir / "asr.json"
        with open(asr_path, "w", encoding="utf-8") as f:
            json.dump(asr_data.to_json(), f, ensure_ascii=False, indent=2)

    def _find_prefixed_file(self, target_dir: Path, prefix: str, preferred: str) -> Optional[Path]:
        """在目录中查找产物文件：优先返回指定文件名，否则按前缀通配匹配。

        例如查找视频文件时，优先返回 video.mp4，找不到则匹配 video.* 取第一个。
        """
        preferred_path = target_dir / preferred
        if preferred_path.exists():
            return preferred_path
        matches = sorted(target_dir.glob(f"{prefix}.*"))
        return matches[0] if matches else None

    def _write_bundle_manifest(
        self,
        *,
        job: CacheJob,
        target_dir: Path,
        source_ref: str,
        source_name: Optional[str],
        summary_text: str,
        profile_version: str,
    ) -> None:
        """收集产物目录中所有文件信息，生成 Bundle 清单并写入 source.json。

        遍历 video/audio/subtitle/asr/summary 五类产物，计算各自大小和哈希，
        组装 BundleManifest 后通过 BundleManager 持久化。同时写入 source.json
        记录来源元数据，供后续查询使用。
        """
        artifacts: dict[str, ArtifactInfo] = {}

        video_path = self._find_prefixed_file(target_dir, "video", "video.mp4")
        audio_path = self._find_prefixed_file(target_dir, "audio", "audio.wav")
        subtitle_path = self._find_prefixed_file(target_dir, "subtitle", "subtitle.vtt")
        asr_path = target_dir / "asr.json"
        summary_path = target_dir / "summary.json"

        # 逐一检查各产物是否存在，存在则记录文件名、大小、哈希
        for key, path in (
            ("video", video_path),
            ("audio", audio_path),
            ("subtitle", subtitle_path),
            ("asr", asr_path if asr_path.exists() else None),
            ("summary", summary_path if summary_path.exists() else None),
        ):
            if path and path.exists():
                artifacts[key] = ArtifactInfo(
                    path=path.name,
                    size=path.stat().st_size,
                    sha256=self._compute_file_hash(path),
                )

        manifest = BundleManifest(
            cache_key=job.cache_key,
            source_type=job.source_type,
            source_ref=source_ref,
            source_name=source_name,
            status="completed",
            summary_text=summary_text,
            profile_version=profile_version,
            artifacts=artifacts,
        )

        bundle_manager = BundleManager()
        bundle_manager.save_manifest(
            job.cache_key,
            job.source_type,
            manifest,
            target_dir=target_dir,
        )

        # 写入来源元信息文件
        source_path = target_dir / "source.json"
        with open(source_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "source_type": job.source_type,
                    "source_ref": source_ref,
                    "source_name": source_name,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _prepare_local_inputs(
        self, job: CacheJob, tmp_dir: Path
    ) -> tuple[str, Optional[str], Optional[str], Optional[str], Optional[str]]:
        """根据上传记录准备本地文件输入。

        通过 file_hash 从持久化存储中查找上传记录，将原始文件复制到临时目录
        并按类型（video/audio/subtitle）规范命名。

        Returns:
            (file_type, video_path, audio_path, subtitle_path, source_name)
            其中只有与 file_type 对应的路径非 None。
        """
        store = get_store()
        if not job.file_hash:
            raise RuntimeError("local job missing file_hash")

        record = store.get_upload_by_hash(job.file_hash)
        if not record:
            raise RuntimeError("file_hash not found in uploads")

        file_type = record.get("file_type")
        source_name = record.get("original_name")
        stored_path = Path(record.get("stored_path", ""))
        if not stored_path.exists():
            raise RuntimeError("stored file missing")

        # 按文件类型复制到临时目录，保留原始扩展名
        if file_type == "subtitle":
            ext = stored_path.suffix or ".vtt"
            target = tmp_dir / f"subtitle{ext.lower()}"
            shutil.copy2(stored_path, target)
            return file_type, None, None, str(target), source_name

        if file_type == "audio":
            ext = stored_path.suffix or ""
            target = tmp_dir / f"audio{ext.lower()}"
            shutil.copy2(stored_path, target)
            return file_type, None, str(target), None, source_name

        if file_type == "video":
            ext = stored_path.suffix or ""
            target = tmp_dir / f"video{ext.lower()}"
            shutil.copy2(stored_path, target)
            return file_type, str(target), None, None, source_name

        raise RuntimeError(f"unsupported file_type: {file_type}")

    def _run_step(self, job: CacheJob, step: str, node_run, ctx: PipelineContext) -> None:
        """执行单个流水线步骤，记录耗时日志，异常时记录错误后重新抛出。"""
        prefix = self._log_prefix(job)
        start = time.time()
        logger.info("step start %s step=%s", prefix, step)
        try:
            node_run(ctx)
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.error(
                "step failed %s step=%s elapsed_ms=%d error=%s",
                prefix,
                step,
                elapsed_ms,
                e,
            )
            raise
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info("step done %s step=%s elapsed_ms=%d", prefix, step, elapsed_ms)

    def _execute_url_flow(self, job: CacheJob, ctx: PipelineContext, profile, tmp_dir: Path) -> None:
        """在线视频处理流水线。

        执行顺序：
          1. 下载字幕 → 2. 解析字幕 → 3. 保存 ASR 数据 → 4. 获取元数据 → 5. 校验字幕
          若字幕有效 → 直接摘要
          若字幕无效 → 6. 下载视频 → 7. 提取音频 → 8. 语音转录 → 9. 摘要

        优先使用在线字幕以减少下载和转录开销；字幕不可用时回退到音频转录。
        """
        self._run_step(job, "download_subtitle", DownloadSubtitleNode("download_sub").run, ctx)
        self._run_step(job, "parse_subtitle", ParseSubtitleNode("parse").run, ctx)
        self._write_asr_json(ctx, tmp_dir)
        self._run_step(job, "fetch_metadata", FetchMetadataNode("meta").run, ctx)
        self._run_step(job, "validate_subtitle", ValidateSubtitleNode("validate").run, ctx)

        # 字幕有效：跳过下载视频和转录，直接用字幕文本生成摘要
        if ctx.get("subtitle_valid"):
            self._run_step(
                job,
                "summarize",
                TextSummarizeNode("summary", params=profile.summary_params).run,
                ctx,
            )
            return

        # 字幕无效：走完整的视频下载 → 音频提取 → 语音转录 → 摘要流程
        self._run_step(job, "download_video", DownloadVideoNode("download_video").run, ctx)
        self._run_step(
            job,
            "extract_audio",
            ExtractAudioNode("extract_audio").run,
            ctx,
        )
        self._run_step(
            job,
            "transcribe",
            TranscribeNode("transcribe", params={"config": profile.transcribe_config}).run,
            ctx,
        )
        self._run_step(
            job,
            "summarize",
            TextSummarizeNode("summary", params=profile.summary_params).run,
            ctx,
        )

    def _execute_local_flow(
        self, job: CacheJob, ctx: PipelineContext, profile, tmp_dir: Path
    ) -> None:
        """本地上传文件处理流水线，根据文件类型选择对应的处理路径。

        - subtitle: 解析 → 校验 → 摘要
        - audio: 语音转录 → 摘要
        - video: 提取音频 → 语音转录 → 摘要
        """
        file_type, video_path, audio_path, subtitle_path, source_name = self._prepare_local_inputs(
            job, tmp_dir
        )

        # 将文件路径注入流水线上下文
        ctx.video_path = video_path
        ctx.audio_path = audio_path
        ctx.subtitle_path = subtitle_path
        if source_name:
            ctx.set("source_name", source_name)

        if file_type == "subtitle":
            self._run_step(job, "parse_subtitle", ParseSubtitleNode("parse").run, ctx)
            self._write_asr_json(ctx, tmp_dir)
            self._run_step(job, "validate_subtitle", ValidateSubtitleNode("validate").run, ctx)
            if not ctx.get("subtitle_valid"):
                raise RuntimeError("subtitle_invalid")
            self._run_step(
                job,
                "summarize",
                TextSummarizeNode("summary", params=profile.summary_params).run,
                ctx,
            )
            return

        if file_type == "audio":
            self._run_step(
                job,
                "transcribe",
                TranscribeNode("transcribe", params={"config": profile.transcribe_config}).run,
                ctx,
            )
            self._run_step(
                job,
                "summarize",
                TextSummarizeNode("summary", params=profile.summary_params).run,
                ctx,
            )
            return

        if file_type == "video":
            self._run_step(
                job,
                "extract_audio",
                ExtractAudioNode("extract_audio").run,
                ctx,
            )
            self._run_step(
                job,
                "transcribe",
                TranscribeNode("transcribe", params={"config": profile.transcribe_config}).run,
                ctx,
            )
            self._run_step(
                job,
                "summarize",
                TextSummarizeNode("summary", params=profile.summary_params).run,
                ctx,
            )
            return

        raise RuntimeError(f"unsupported file_type: {file_type}")

    def _validate_summary_json(self, target_dir: Path, profile_version: str) -> None:
        """校验 summary.json 产物的结构完整性。

        检查项：文件存在、JSON 可解析、顶层为 dict、
        profile_version 匹配、summary_text/model/input_chars 字段类型正确。
        """
        summary_path = target_dir / "summary.json"
        if not summary_path.exists():
            raise RuntimeError("summary_json_missing")
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(f"summary_json_invalid: {e}")

        if not isinstance(data, dict):
            raise RuntimeError("summary_json_invalid")
        if data.get("profile_version") != profile_version:
            raise RuntimeError("summary_profile_version_mismatch")
        if not isinstance(data.get("summary_text"), str):
            raise RuntimeError("summary_json_invalid")
        if not isinstance(data.get("model"), str):
            raise RuntimeError("summary_json_invalid")
        if not isinstance(data.get("input_chars"), int):
            raise RuntimeError("summary_json_invalid")

    def _process_cache_job(self, job: CacheJob) -> None:
        """处理单个缓存构建任务的完整生命周期。

        流程：
          1. 标记任务和缓存条目为 running
          2. 创建临时工作目录
          3. 根据 source_type 执行对应流水线（url/local）
          4. 校验摘要文本和 summary.json 产物
          5. 生成 Bundle 清单并将临时目录归档为正式缓存
          6. 更新缓存和任务状态为 completed 或 failed
          7. 失败时清理临时目录
        """
        cache_service = get_cache_service()
        bundle_manager = BundleManager()

        # 标记任务开始执行
        cache_service.update_status(job.cache_key, "running")
        cache_service.update_job(job.job_id, "running")

        ctx: Optional[PipelineContext] = None
        error: Optional[str] = None
        status = "failed"  # 默认失败，成功时显式覆盖
        summary_text: Optional[str] = None

        tmp_dir = bundle_manager.create_tmp_dir(job.job_id)
        profile = get_processing_profile()

        try:
            # 确认缓存条目存在
            entry = cache_service.get_entry(job.cache_key)
            if not entry:
                raise RuntimeError("cache_entry_missing")

            # 初始化流水线上下文
            ctx = PipelineContext(
                source_type=job.source_type,
                source_url=job.source_url,
            )
            ctx.run_id = job.job_id
            ctx.cache_key = job.cache_key
            ctx.job_id = job.job_id
            ctx.bundle_dir = str(tmp_dir)

            # 按来源类型分发到对应流水线
            if job.source_type == "url":
                self._execute_url_flow(job, ctx, profile, tmp_dir)
            elif job.source_type == "local":
                self._execute_local_flow(job, ctx, profile, tmp_dir)
            else:
                raise RuntimeError(f"unsupported source_type: {job.source_type}")

            # 校验摘要文本有效性
            summary_text = ctx.summary_text
            if not self._is_summary_text_valid(summary_text):
                error_detail = ctx.get("summary_error")
                if not error_detail and isinstance(summary_text, str):
                    stripped = summary_text.strip()
                    if stripped:
                        error_detail = stripped
                raise RuntimeError(error_detail or "summary_invalid")

            # 校验 summary.json 产物结构
            self._validate_summary_json(tmp_dir, profile.profile_version)

            # 写入 Bundle 清单（manifest.json + source.json）
            source_name = ctx.get("source_name") if ctx else None
            self._write_bundle_manifest(
                job=job,
                target_dir=tmp_dir,
                source_ref=entry.source_ref,
                source_name=source_name,
                summary_text=summary_text,
                profile_version=profile.profile_version,
            )

            # 将临时目录提升为正式缓存目录
            if not bundle_manager.finalize_from_tmp(
                job.job_id, job.cache_key, job.source_type
            ):
                raise RuntimeError("bundle_finalize_failed")

            status = "completed"

        except Exception as e:
            error = str(e)
            status = "failed"
        finally:
            # 失败时清理临时目录，成功时已被 finalize 移走
            if status != "completed":
                bundle_manager.cleanup_tmp(job.job_id)

        # 更新缓存条目和任务记录的最终状态
        cache_service.update_status(
            job.cache_key,
            status,
            summary_text=summary_text if status == "completed" else None,
            error=error,
            source_name=ctx.get("source_name") if ctx else None,
        )
        cache_service.update_job(job.job_id, status, error=error)


# ---------------------------------------------------------------------------
# 模块级单例：全局唯一的任务队列实例
# ---------------------------------------------------------------------------
_queue: Optional[JobQueue] = None


def get_job_queue(worker_count: int = 1) -> JobQueue:
    """获取全局 JobQueue 单例，首次调用时创建。

    Args:
        worker_count: 工作线程数，仅首次创建时生效。
    """
    global _queue
    if _queue is None:
        _queue = JobQueue(worker_count=worker_count)
    return _queue
