"""Mock 节点实现 - 阶段2验证用"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from app.pipeline.context import PipelineContext
from app.pipeline.node_base import PipelineNode


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

    def get_output_keys(self) -> List[str]:
        return ["source_type"]


class FetchMetadataNode(PipelineNode):
    """获取视频元数据节点 - 模拟获取视频时长"""

    def run(self, ctx: PipelineContext) -> None:
        # 模拟获取视频时长
        mock_duration = self.params.get("mock_duration", 300.0)
        ctx.set("video_duration", mock_duration)

    def get_output_keys(self) -> List[str]:
        return ["video_duration"]


class DownloadSubtitleNode(PipelineNode):
    """下载字幕节点 - 模拟从 URL 下载字幕"""

    def run(self, ctx: PipelineContext) -> None:
        # 模拟下载字幕
        mock_path = self.params.get("mock_path", "/tmp/mock_subtitle.srt")
        ctx.set("subtitle_path", mock_path)

    def get_output_keys(self) -> List[str]:
        return ["subtitle_path"]


class ValidateSubtitleNode(PipelineNode):
    """校验字幕节点 - 模拟检查字幕有效性和覆盖率"""

    def run(self, ctx: PipelineContext) -> None:
        # 可通过参数控制 mock 结果
        mock_valid = self.params.get("mock_valid", True)
        mock_coverage = self.params.get("mock_coverage", 0.85)

        ctx.set("subtitle_valid", mock_valid)
        ctx.set("subtitle_coverage_ratio", mock_coverage)

    def get_output_keys(self) -> List[str]:
        return ["subtitle_valid", "subtitle_coverage_ratio"]


class ExtractAudioNode(PipelineNode):
    """抽取音频节点 - 模拟从视频提取音频"""

    def run(self, ctx: PipelineContext) -> None:
        # 模拟抽取音频
        mock_path = self.params.get("mock_path", "/tmp/mock_audio.wav")
        ctx.set("audio_path", mock_path)

    def get_output_keys(self) -> List[str]:
        return ["audio_path"]


class TranscribeNode(PipelineNode):
    """转录节点 - 模拟音频转文字"""

    def run(self, ctx: PipelineContext) -> None:
        # 模拟转录结果 token 数
        mock_tokens = self.params.get("mock_tokens", 1500)
        ctx.set("transcript_token_count", mock_tokens)

        # 可选：模拟转录文本
        if "mock_text" in self.params:
            ctx.set("transcript_text", self.params["mock_text"])

    def get_output_keys(self) -> List[str]:
        return ["transcript_token_count"]


class DetectSilenceNode(PipelineNode):
    """静音检测节点 - 模拟检测音频是否为静音"""

    def run(self, ctx: PipelineContext) -> None:
        # 可通过参数控制 mock 结果
        mock_silent = self.params.get("mock_silent", False)
        mock_rms = self.params.get("mock_rms", 0.05)

        ctx.set("is_silent", mock_silent)
        ctx.set("audio_rms", mock_rms)

    def get_output_keys(self) -> List[str]:
        return ["is_silent", "audio_rms"]


class TextSummarizeNode(PipelineNode):
    """文本总结节点 - 模拟生成摘要"""

    def run(self, ctx: PipelineContext) -> None:
        # 模拟生成摘要
        mock_summary = self.params.get(
            "mock_summary",
            "这是一段模拟的视频摘要内容。视频主要讲述了..."
        )
        ctx.set("summary_text", mock_summary)

    def get_output_keys(self) -> List[str]:
        return ["summary_text"]
