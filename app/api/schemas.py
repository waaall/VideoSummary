from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PipelineNodeConfig(BaseModel):
    id: str = Field(..., description="Unique node id")
    type: str = Field(..., description="Node type registered in NodeRegistry")
    params: Dict[str, Any] = Field(default_factory=dict)


class PipelineEdgeConfig(BaseModel):
    source: str = Field(..., description="Upstream node id")
    target: str = Field(..., description="Downstream node id")
    condition: Optional[str] = Field(
        default=None, description="Boolean expression evaluated on Context"
    )


class PipelineConfig(BaseModel):
    version: str = "v1"
    entrypoint: Optional[str] = Field(
        default=None, description="Optional entry node id"
    )
    nodes: List[PipelineNodeConfig]
    edges: List[PipelineEdgeConfig]


class PipelineInputs(BaseModel):
    source_type: str = Field(..., description="url|local")
    source_url: Optional[str] = None
    video_path: Optional[str] = None
    subtitle_path: Optional[str] = None
    audio_path: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class PipelineThresholds(BaseModel):
    subtitle_coverage_min: float = Field(
        0.8, description="Minimum subtitle coverage ratio to be considered valid"
    )
    transcript_token_per_min_min: float = Field(
        2.0, description="Minimum transcript tokens per minute"
    )
    audio_rms_max_for_silence: float = Field(
        0.01, description="Max RMS to be considered silent"
    )


class PipelineRunRequest(BaseModel):
    pipeline: PipelineConfig
    inputs: PipelineInputs
    thresholds: Optional[PipelineThresholds] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class AutoPipelineInputs(BaseModel):
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    video_path: Optional[str] = None
    subtitle_path: Optional[str] = None
    audio_path: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class AutoPipelineRunRequest(BaseModel):
    inputs: AutoPipelineInputs
    thresholds: Optional[PipelineThresholds] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    node_id: str
    status: str
    elapsed_ms: Optional[int] = None
    error: Optional[str] = None
    output_keys: Optional[List[str]] = None
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    retryable: Optional[bool] = None


class PipelineRunResponse(BaseModel):
    run_id: str
    status: str
    summary_text: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    trace: List[TraceEvent] = Field(default_factory=list)
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    error: Optional[str] = None


class PipelineRunCreateResponse(BaseModel):
    run_id: str
    status: str
    queued_at: Optional[float] = None


# ============ 文件上传相关 ============


class UploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str = Field(..., description="文件唯一标识，用于后续流程引用")
    original_name: str = Field(..., description="原始文件名")
    size: int = Field(..., description="文件大小（字节）")
    mime_type: str = Field(..., description="MIME 类型")
    file_type: str = Field(..., description="文件类型: video|audio|subtitle")


class LocalPipelineInputs(BaseModel):
    """本地流程输入（支持 file_id）

    优先使用 file_id 参数，如果提供则忽略对应的 path 参数。
    """
    # file_id 方式（推荐，前端上传后使用）
    video_file_id: Optional[str] = Field(
        default=None, description="视频文件 ID（通过 /uploads 上传后获得）"
    )
    audio_file_id: Optional[str] = Field(
        default=None, description="音频文件 ID（通过 /uploads 上传后获得）"
    )
    subtitle_file_id: Optional[str] = Field(
        default=None, description="字幕文件 ID（通过 /uploads 上传后获得）"
    )

    # path 方式（服务端本地路径，内部调试用）
    video_path: Optional[str] = Field(
        default=None, description="视频文件本地路径（服务端路径）"
    )
    audio_path: Optional[str] = Field(
        default=None, description="音频文件本地路径（服务端路径）"
    )
    subtitle_path: Optional[str] = Field(
        default=None, description="字幕文件本地路径（服务端路径）"
    )

    extra: Dict[str, Any] = Field(default_factory=dict)


class LocalPipelineRunRequest(BaseModel):
    """本地流程请求（支持 file_id）"""
    inputs: LocalPipelineInputs
    thresholds: Optional[PipelineThresholds] = None
    options: Dict[str, Any] = Field(default_factory=dict)
