"""Pipeline 节点实现"""

# 核心节点（真实实现）
from app.pipeline.nodes.core import (
    InputNode,
    FetchMetadataNode,
    DownloadSubtitleNode,
    DownloadVideoNode,
    ParseSubtitleNode,
    ValidateSubtitleNode,
    ExtractAudioNode,
    TranscribeNode,
    DetectSilenceNode,
    WarningNode,
    TextSummarizeNode,
    SampleFramesNode,
    VlmSummarizeNode,
    MergeSummaryNode,
)

__all__ = [
    # 输入
    "InputNode",
    # 元数据
    "FetchMetadataNode",
    # 下载
    "DownloadSubtitleNode",
    "DownloadVideoNode",
    # 字幕
    "ParseSubtitleNode",
    "ValidateSubtitleNode",
    # 音频
    "ExtractAudioNode",
    "DetectSilenceNode",
    # 转录
    "TranscribeNode",
    # 总结
    "WarningNode",
    "TextSummarizeNode",
    # VLM（阶段4）
    "SampleFramesNode",
    "VlmSummarizeNode",
    "MergeSummaryNode",
]
