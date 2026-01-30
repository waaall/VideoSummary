"""核心节点实现 - 阶段3真实业务逻辑"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yt_dlp

from app.config import APPDATA_PATH, WORK_PATH
from app.core.asr.asr_data import ASRData
from app.core.utils.logger import setup_logger
from app.core.utils.video_utils import get_video_info, video2audio
from app.pipeline.context import PipelineContext
from app.pipeline.node_base import PipelineNode

logger = setup_logger("pipeline_nodes")


# ============ 输入验证节点 ============

class InputNode(PipelineNode):
    """输入验证节点 - 验证输入参数并设置 source_type"""

    def run(self, ctx: PipelineContext) -> None:
        # 验证 source_type
        if ctx.source_type not in ("url", "local"):
            raise ValueError(f"无效的 source_type: {ctx.source_type}")

        # URL 类型需要 source_url
        if ctx.source_type == "url" and not ctx.source_url:
            raise ValueError("source_type 为 url 时必须提供 source_url")

        # local 类型需要 video_path
        if ctx.source_type == "local" and not ctx.video_path:
            raise ValueError("source_type 为 local 时必须提供 video_path")

        logger.info(f"输入验证通过: source_type={ctx.source_type}")

    def get_output_keys(self) -> List[str]:
        return ["source_type"]


# ============ 元数据获取节点 ============

class FetchMetadataNode(PipelineNode):
    """获取视频元数据节点 - 获取视频时长等信息"""

    def run(self, ctx: PipelineContext) -> None:
        # 确定视频路径
        video_path = ctx.video_path

        if ctx.source_type == "url" and not video_path:
            # URL 模式下，使用 yt-dlp 获取元数据（不下载）
            duration = self._get_url_duration(ctx.source_url)
            ctx.set("video_duration", duration)
            logger.info(f"URL 视频时长: {duration}s")
            return

        if not video_path or not Path(video_path).exists():
            raise ValueError(f"视频文件不存在: {video_path}")

        # 本地文件使用 ffmpeg 获取信息
        video_info = get_video_info(video_path)
        if video_info is None:
            raise RuntimeError(f"无法获取视频信息: {video_path}")

        ctx.set("video_duration", video_info.duration_seconds)
        # 存储额外信息到 extra
        ctx.set("video_width", video_info.width)
        ctx.set("video_height", video_info.height)
        ctx.set("video_fps", video_info.fps)
        ctx.set("video_bitrate", video_info.bitrate_kbps)

        logger.info(f"视频元数据: 时长={video_info.duration_seconds}s, "
                   f"分辨率={video_info.width}x{video_info.height}")

    def _get_url_duration(self, url: str) -> float:
        """使用 yt-dlp 获取 URL 视频时长"""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }
        # 检查 cookies 文件
        cookiefile_path = APPDATA_PATH / "cookies.txt"
        if cookiefile_path.exists():
            ydl_opts["cookiefile"] = str(cookiefile_path)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return float(info.get("duration", 0))

    def get_output_keys(self) -> List[str]:
        return ["video_duration"]


# ============ 下载相关节点 ============

class DownloadSubtitleNode(PipelineNode):
    """下载字幕节点 - 从 URL 下载字幕"""

    def run(self, ctx: PipelineContext) -> None:
        url = ctx.source_url
        if not url:
            raise ValueError("source_url 未设置")

        work_dir = self.params.get("work_dir", str(WORK_PATH))
        subtitle_path = self._download_subtitle(url, work_dir)

        if subtitle_path:
            ctx.set("subtitle_path", subtitle_path)
            logger.info(f"字幕下载成功: {subtitle_path}")
        else:
            logger.info("未找到可用字幕")
            ctx.set("subtitle_path", None)

    def _download_subtitle(self, url: str, work_dir: str) -> Optional[str]:
        """下载字幕文件"""
        # 创建临时目录存放字幕
        subtitle_dir = Path(work_dir) / "subtitles"
        subtitle_dir.mkdir(parents=True, exist_ok=True)

        ydl_opts = {
            "outtmpl": {"subtitle": str(subtitle_dir / "%(title).100s.%(ext)s")},
            "skip_download": True,  # 不下载视频
            "writeautomaticsub": True,  # 下载自动生成的字幕
            "writesubtitles": True,  # 下载手动字幕
            "subtitlesformat": "vtt/srt/ass",
            "quiet": True,
            "no_warnings": True,
        }

        # 检查 cookies 文件
        cookiefile_path = APPDATA_PATH / "cookies.txt"
        if cookiefile_path.exists():
            ydl_opts["cookiefile"] = str(cookiefile_path)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                subtitle_language = info.get("language", "")
                if subtitle_language:
                    subtitle_language = subtitle_language.lower().split("-")[0]

                # 尝试获取自动字幕链接
                subtitle_link = None
                automatic_captions = info.get("automatic_captions", {})
                if automatic_captions and subtitle_language:
                    for lang_code in automatic_captions:
                        if lang_code.startswith(subtitle_language):
                            formats = automatic_captions[lang_code]
                            # 优先选择 vtt 格式
                            for fmt in formats:
                                if fmt.get("ext") in ("vtt", "srt"):
                                    subtitle_link = fmt.get("url")
                                    break
                            if not subtitle_link and formats:
                                subtitle_link = formats[-1].get("url")
                            break

                # 如果有字幕链接，直接下载
                if subtitle_link:
                    response = requests.get(subtitle_link, timeout=30)
                    if response.ok:
                        ext = "vtt" if "vtt" in subtitle_link else "srt"
                        subtitle_path = subtitle_dir / f"downloaded.{ext}"
                        subtitle_path.write_text(response.text, encoding="utf-8")
                        return str(subtitle_path)

                # 尝试使用 yt-dlp 下载
                ydl.download([url])

                # 查找下载的字幕文件
                for ext in ("*.vtt", "*.srt", "*.ass"):
                    files = list(subtitle_dir.glob(ext))
                    if files:
                        return str(files[0])

        except Exception as e:
            logger.warning(f"字幕下载失败: {e}")

        return None

    def get_output_keys(self) -> List[str]:
        return ["subtitle_path"]


class DownloadVideoNode(PipelineNode):
    """下载视频节点 - 按需下载视频（仅在字幕无效时触发）"""

    def run(self, ctx: PipelineContext) -> None:
        url = ctx.source_url
        if not url:
            raise ValueError("source_url 未设置")

        work_dir = self.params.get("work_dir", str(WORK_PATH))
        video_path = self._download_video(url, work_dir)

        if not video_path:
            raise RuntimeError("视频下载失败")

        ctx.set("video_path", video_path)
        logger.info(f"视频下载成功: {video_path}")

    def _sanitize_filename(self, name: str, replacement: str = "_") -> str:
        """清理文件名中不允许的字符"""
        forbidden_chars = r'<>:"/\\|?*'
        sanitized = re.sub(f"[{re.escape(forbidden_chars)}]", replacement, name)
        sanitized = re.sub(r"[\0-\31]", "", sanitized)
        sanitized = sanitized.rstrip(" .")

        max_length = 255
        if len(sanitized) > max_length:
            base, ext = os.path.splitext(sanitized)
            sanitized = base[:max_length - len(ext)] + ext

        return sanitized if sanitized else "default_video"

    def _download_video(self, url: str, work_dir: str) -> Optional[str]:
        """下载视频文件"""
        ydl_opts = {
            "outtmpl": {"default": "%(title).200s.%(ext)s"},
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }

        # 检查 cookies 文件
        cookiefile_path = APPDATA_PATH / "cookies.txt"
        if cookiefile_path.exists():
            ydl_opts["cookiefile"] = str(cookiefile_path)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = self._sanitize_filename(info.get("title", "video"))
                video_work_dir = Path(work_dir) / video_title
                video_work_dir.mkdir(parents=True, exist_ok=True)

                ydl.params["paths"] = {"home": str(video_work_dir)}
                ydl.process_info(info)

                # 尝试从 yt-dlp 的返回信息中解析最终文件路径
                candidate_paths: list[str] = []
                prepared = ydl.prepare_filename(info)
                if prepared:
                    candidate_paths.append(prepared)

                requested = info.get("requested_downloads") or []
                for item in requested:
                    filepath = item.get("filepath")
                    if filepath:
                        candidate_paths.append(filepath)

                # 回退：在工作目录中查找常见视频格式
                for ext in ("*.mp4", "*.mkv", "*.webm", "*.mov"):
                    for p in video_work_dir.glob(ext):
                        candidate_paths.append(str(p))

                for path in candidate_paths:
                    if path and Path(path).exists():
                        return str(Path(path))

        except Exception as e:
            logger.exception(f"视频下载失败: {e}")

        return None

    def get_output_keys(self) -> List[str]:
        return ["video_path"]


# ============ 字幕相关节点 ============

class ParseSubtitleNode(PipelineNode):
    """解析字幕节点 - 将字幕文件解析为结构化数据"""

    def run(self, ctx: PipelineContext) -> None:
        subtitle_path = ctx.subtitle_path

        if not subtitle_path or not Path(subtitle_path).exists():
            logger.info("字幕文件不存在，跳过解析")
            ctx.set("asr_data", None)
            return

        try:
            asr_data = ASRData.from_subtitle_file(subtitle_path)
            ctx.set("asr_data", asr_data)
            ctx.set("subtitle_segment_count", len(asr_data.segments))
            logger.info(f"字幕解析成功: {len(asr_data.segments)} 个片段")
        except Exception as e:
            logger.warning(f"字幕解析失败: {e}")
            ctx.set("asr_data", None)

    def get_output_keys(self) -> List[str]:
        return ["asr_data", "subtitle_segment_count"]


class ValidateSubtitleNode(PipelineNode):
    """校验字幕节点 - 检查字幕有效性和覆盖率"""

    def run(self, ctx: PipelineContext) -> None:
        asr_data: Optional[ASRData] = ctx.get("asr_data")
        video_duration = ctx.video_duration

        # 获取阈值配置
        coverage_min = ctx.thresholds.subtitle_coverage_min

        if not asr_data or not asr_data.has_data():
            ctx.set("subtitle_valid", False)
            ctx.set("subtitle_coverage_ratio", 0.0)
            logger.info("字幕无效: 无数据")
            return

        if not video_duration or video_duration <= 0:
            # 无法计算覆盖率，假设有效
            ctx.set("subtitle_valid", True)
            ctx.set("subtitle_coverage_ratio", 1.0)
            logger.info("无法获取视频时长，假设字幕有效")
            return

        # 计算字幕覆盖时长（避免用跨度高估）
        segments = asr_data.segments
        covered_ms = 0.0
        for seg in segments:
            seg_duration = max(0.0, seg.end_time - seg.start_time)
            covered_ms += seg_duration

        # 计算覆盖率（以总覆盖时长为准）
        video_duration_ms = video_duration * 1000
        coverage_ratio = covered_ms / video_duration_ms

        # 额外检查：字幕密度（每分钟段数）
        duration_minutes = video_duration / 60
        segments_per_minute = len(segments) / max(duration_minutes, 0.1)

        # 判断有效性
        is_valid = coverage_ratio >= coverage_min and segments_per_minute >= 1.0

        ctx.set("subtitle_valid", is_valid)
        ctx.set("subtitle_coverage_ratio", round(coverage_ratio, 4))
        ctx.set("subtitle_density", round(segments_per_minute, 2))

        logger.info(f"字幕校验: valid={is_valid}, coverage={coverage_ratio:.2%}, "
                    f"density={segments_per_minute:.1f}/min")

    def get_output_keys(self) -> List[str]:
        return ["subtitle_valid", "subtitle_coverage_ratio"]


# ============ 音频相关节点 ============

class ExtractAudioNode(PipelineNode):
    """抽取音频节点 - 从视频提取音频"""

    def run(self, ctx: PipelineContext) -> None:
        video_path = ctx.video_path

        if not video_path or not Path(video_path).exists():
            raise ValueError(f"视频文件不存在: {video_path}")

        # 创建临时音频文件
        audio_track_index = self.params.get("audio_track_index", 0)
        temp_dir = Path(tempfile.gettempdir()) / "videosummary"
        temp_dir.mkdir(parents=True, exist_ok=True)

        audio_path = temp_dir / f"{ctx.run_id}_audio.wav"

        # 执行转换
        success = video2audio(video_path, str(audio_path), audio_track_index)

        if not success or not audio_path.exists():
            raise RuntimeError("音频提取失败")

        ctx.set("audio_path", str(audio_path))
        logger.info(f"音频提取成功: {audio_path}")

    def get_output_keys(self) -> List[str]:
        return ["audio_path"]


class DetectSilenceNode(PipelineNode):
    """静音检测节点 - 判断视频是否为无声视频"""

    def run(self, ctx: PipelineContext) -> None:
        # 获取阈值配置
        token_per_min_min = ctx.thresholds.transcript_token_per_min_min
        rms_max = ctx.thresholds.audio_rms_max_for_silence

        transcript_token_count = ctx.transcript_token_count or 0
        video_duration = ctx.video_duration or 0

        # 方法1：基于转录 token 数/时长判断
        if video_duration > 0:
            tokens_per_minute = transcript_token_count / (video_duration / 60)
        else:
            tokens_per_minute = 0

        # 方法2：基于音频 RMS（若已有值）
        audio_rms = ctx.audio_rms
        if audio_rms is None:
            # 无真实 RMS 时估算：token 稀疏则接近静音阈值
            audio_rms = (rms_max * 0.9) if tokens_per_minute < token_per_min_min else (rms_max * 1.5)

        # 判断是否为无声：满足任一静音条件
        is_silent = (tokens_per_minute < token_per_min_min) or (audio_rms <= rms_max)

        ctx.set("is_silent", is_silent)
        ctx.set("audio_rms", audio_rms)
        ctx.set("tokens_per_minute", round(tokens_per_minute, 2))

        logger.info(f"静音检测: is_silent={is_silent}, tokens/min={tokens_per_minute:.2f}")

    def get_output_keys(self) -> List[str]:
        return ["is_silent", "audio_rms"]


# ============ 转录节点 ============

class TranscribeNode(PipelineNode):
    """转录节点 - 音频转文字"""

    def run(self, ctx: PipelineContext) -> None:
        audio_path = ctx.audio_path

        if not audio_path or not Path(audio_path).exists():
            raise ValueError(f"音频文件不存在: {audio_path}")

        # 获取转录配置
        transcribe_config = self.params.get("config")

        if not transcribe_config:
            # 使用默认配置或从 extra 获取
            transcribe_config = ctx.get("transcribe_config")

        if not transcribe_config:
            raise ValueError("转录配置未提供")

        # 延迟导入避免循环依赖
        from app.core.asr import transcribe

        # 执行转录
        logger.info(f"开始转录: {audio_path}")
        asr_data = transcribe(audio_path, transcribe_config, callback=None)

        # 计算 token 数（使用片段文本总字符数估算）
        total_text = "".join(seg.text for seg in asr_data.segments)
        token_count = len(total_text)

        ctx.set("asr_data", asr_data)
        ctx.set("transcript_token_count", token_count)
        ctx.set("transcript_segment_count", len(asr_data.segments))

        logger.info(f"转录完成: {len(asr_data.segments)} 个片段, ~{token_count} 字符")

    def get_output_keys(self) -> List[str]:
        return ["transcript_token_count", "asr_data"]


# ============ 总结节点 ============

class TextSummarizeNode(PipelineNode):
    """文本总结节点 - 使用 LLM 生成摘要"""

    def run(self, ctx: PipelineContext) -> None:
        # 获取文本内容
        asr_data: Optional[ASRData] = ctx.get("asr_data")

        if not asr_data or not asr_data.has_data():
            ctx.set("summary_text", "无法生成摘要：无有效文本内容")
            logger.warning("无有效文本内容用于总结")
            return

        # 拼接文本
        full_text = "\n".join(seg.text for seg in asr_data.segments)

        # 获取 LLM 配置
        model = self.params.get("model", os.getenv("LLM_MODEL", "gpt-3.5-turbo"))
        max_tokens = self.params.get("max_tokens", 1000)

        # 构建提示词
        prompt = self.params.get("prompt", "请总结以下视频内容的主要观点：")

        messages = [
            {"role": "system", "content": "你是一个专业的视频内容总结助手。"},
            {"role": "user", "content": f"{prompt}\n\n{full_text[:8000]}"}  # 限制输入长度
        ]

        try:
            # 延迟导入
            from app.core.llm.client import call_llm

            response = call_llm(messages, model=model, max_tokens=max_tokens)
            summary = response.choices[0].message.content

            ctx.set("summary_text", summary)
            logger.info(f"总结生成成功: {len(summary)} 字符")

        except Exception as e:
            logger.exception(f"LLM 调用失败: {e}")
            ctx.set("summary_text", f"总结生成失败: {e}")

    def get_output_keys(self) -> List[str]:
        return ["summary_text"]


# ============ VLM 相关节点（阶段4实现） ============

class SampleFramesNode(PipelineNode):
    """抽帧节点 - 从视频中采样关键帧（阶段4实现）"""

    def run(self, ctx: PipelineContext) -> None:
        # 阶段4实现
        ctx.set("frames_paths", [])
        logger.info("SampleFramesNode: 阶段4实现")

    def get_output_keys(self) -> List[str]:
        return ["frames_paths"]


class VlmSummarizeNode(PipelineNode):
    """VLM 视觉总结节点（阶段4实现）"""

    def run(self, ctx: PipelineContext) -> None:
        # 阶段4实现
        ctx.set("vlm_summary", "")
        logger.info("VlmSummarizeNode: 阶段4实现")

    def get_output_keys(self) -> List[str]:
        return ["vlm_summary"]


class MergeSummaryNode(PipelineNode):
    """合并总结节点 - 合并文本和视觉总结（阶段4实现）"""

    def run(self, ctx: PipelineContext) -> None:
        # 合并已有的总结
        text_summary = ctx.summary_text or ""
        vlm_summary = ctx.get("vlm_summary", "")

        if vlm_summary:
            merged = f"{text_summary}\n\n视觉分析：\n{vlm_summary}"
        else:
            merged = text_summary

        ctx.set("summary_text", merged)
        logger.info("总结合并完成")

    def get_output_keys(self) -> List[str]:
        return ["summary_text"]
