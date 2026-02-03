"""In-process job queue and worker for fixed pipeline execution."""
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

INVALID_SUMMARY_PREFIXES = (
    "无法生成摘要",
    "总结生成失败",
    "无有效信息",
)


@dataclass
class CacheJob:
    """缓存任务"""

    job_id: str
    cache_key: str
    source_type: str  # "url" | "local"
    source_url: Optional[str] = None
    file_hash: Optional[str] = None
    request_id: Optional[str] = None


class JobQueue:
    def __init__(self, worker_count: int = 1) -> None:
        self.worker_count = worker_count
        self._queue: "queue.Queue[CacheJob]" = queue.Queue()
        self._stop_event = threading.Event()
        self._workers: list[threading.Thread] = []

    def start(self) -> None:
        if self.worker_count <= 0:
            return
        if self._workers:
            return
        for idx in range(self.worker_count):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"cache-worker-{idx}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

    def stop(self) -> None:
        self._stop_event.set()

    def enqueue(self, job: CacheJob) -> None:
        self._queue.put(job)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._process_cache_job(job)
            finally:
                self._queue.task_done()

    def _log_prefix(self, job: CacheJob) -> str:
        request_id = job.request_id or "-"
        return (
            f"request_id={request_id} job_id={job.job_id} "
            f"cache_key={job.cache_key} source_type={job.source_type}"
        )

    def _is_summary_text_valid(self, text: Optional[str]) -> bool:
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
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def _write_asr_json(self, ctx: PipelineContext, target_dir: Path) -> None:
        asr_data = ctx.get("asr_data")
        if not asr_data:
            return
        asr_path = target_dir / "asr.json"
        with open(asr_path, "w", encoding="utf-8") as f:
            json.dump(asr_data.to_json(), f, ensure_ascii=False, indent=2)

    def _find_prefixed_file(self, target_dir: Path, prefix: str, preferred: str) -> Optional[Path]:
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
        summary_text: str,
        profile_version: str,
    ) -> None:
        artifacts: dict[str, ArtifactInfo] = {}

        video_path = self._find_prefixed_file(target_dir, "video", "video.mp4")
        audio_path = self._find_prefixed_file(target_dir, "audio", "audio.wav")
        subtitle_path = self._find_prefixed_file(target_dir, "subtitle", "subtitle.vtt")
        asr_path = target_dir / "asr.json"
        summary_path = target_dir / "summary.json"

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

        source_path = target_dir / "source.json"
        with open(source_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "source_type": job.source_type,
                    "source_ref": source_ref,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _prepare_local_inputs(
        self, job: CacheJob, tmp_dir: Path
    ) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
        store = get_store()
        if not job.file_hash:
            raise RuntimeError("local job missing file_hash")

        record = store.get_upload_by_hash(job.file_hash)
        if not record:
            raise RuntimeError("file_hash not found in uploads")

        file_type = record.get("file_type")
        stored_path = Path(record.get("stored_path", ""))
        if not stored_path.exists():
            raise RuntimeError("stored file missing")

        if file_type == "subtitle":
            ext = stored_path.suffix or ".vtt"
            target = tmp_dir / f"subtitle{ext.lower()}"
            shutil.copy2(stored_path, target)
            return file_type, None, None, str(target)

        if file_type == "audio":
            ext = stored_path.suffix or ""
            target = tmp_dir / f"audio{ext.lower()}"
            shutil.copy2(stored_path, target)
            return file_type, None, str(target), None

        if file_type == "video":
            ext = stored_path.suffix or ""
            target = tmp_dir / f"video{ext.lower()}"
            shutil.copy2(stored_path, target)
            return file_type, str(target), None, None

        raise RuntimeError(f"unsupported file_type: {file_type}")

    def _run_step(self, job: CacheJob, step: str, node_run, ctx: PipelineContext) -> None:
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
        self._run_step(job, "download_subtitle", DownloadSubtitleNode("download_sub").run, ctx)
        self._run_step(job, "parse_subtitle", ParseSubtitleNode("parse").run, ctx)
        self._write_asr_json(ctx, tmp_dir)
        self._run_step(job, "fetch_metadata", FetchMetadataNode("meta").run, ctx)
        self._run_step(job, "validate_subtitle", ValidateSubtitleNode("validate").run, ctx)

        if ctx.get("subtitle_valid"):
            self._run_step(
                job,
                "summarize",
                TextSummarizeNode("summary", params=profile.summary_params).run,
                ctx,
            )
            return

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
        file_type, video_path, audio_path, subtitle_path = self._prepare_local_inputs(
            job, tmp_dir
        )

        ctx.video_path = video_path
        ctx.audio_path = audio_path
        ctx.subtitle_path = subtitle_path

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
        cache_service = get_cache_service()
        bundle_manager = BundleManager()

        cache_service.update_status(job.cache_key, "running")
        cache_service.update_job(job.job_id, "running")

        ctx: Optional[PipelineContext] = None
        error: Optional[str] = None
        status = "failed"
        summary_text: Optional[str] = None

        tmp_dir = bundle_manager.create_tmp_dir(job.job_id)
        profile = get_processing_profile()

        try:
            entry = cache_service.get_entry(job.cache_key)
            if not entry:
                raise RuntimeError("cache_entry_missing")

            ctx = PipelineContext(
                source_type=job.source_type,
                source_url=job.source_url,
            )
            ctx.run_id = job.job_id
            ctx.cache_key = job.cache_key
            ctx.job_id = job.job_id
            ctx.bundle_dir = str(tmp_dir)

            if job.source_type == "url":
                self._execute_url_flow(job, ctx, profile, tmp_dir)
            elif job.source_type == "local":
                self._execute_local_flow(job, ctx, profile, tmp_dir)
            else:
                raise RuntimeError(f"unsupported source_type: {job.source_type}")

            summary_text = ctx.summary_text
            if not self._is_summary_text_valid(summary_text):
                error_detail = ctx.get("summary_error")
                if not error_detail and isinstance(summary_text, str):
                    stripped = summary_text.strip()
                    if stripped:
                        error_detail = stripped
                raise RuntimeError(error_detail or "summary_invalid")

            self._validate_summary_json(tmp_dir, profile.profile_version)

            self._write_bundle_manifest(
                job=job,
                target_dir=tmp_dir,
                source_ref=entry.source_ref,
                summary_text=summary_text,
                profile_version=profile.profile_version,
            )

            if not bundle_manager.finalize_from_tmp(
                job.job_id, job.cache_key, job.source_type
            ):
                raise RuntimeError("bundle_finalize_failed")

            status = "completed"

        except Exception as e:
            error = str(e)
            status = "failed"
        finally:
            if status != "completed":
                bundle_manager.cleanup_tmp(job.job_id)

        cache_service.update_status(
            job.cache_key,
            status,
            summary_text=summary_text if status == "completed" else None,
            error=error,
        )
        cache_service.update_job(job.job_id, status, error=error)


_queue: Optional[JobQueue] = None


def get_job_queue(worker_count: int = 1) -> JobQueue:
    global _queue
    if _queue is None:
        _queue = JobQueue(worker_count=worker_count)
    return _queue
