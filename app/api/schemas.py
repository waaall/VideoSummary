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


class TraceEvent(BaseModel):
    node_id: str
    status: str
    elapsed_ms: Optional[int] = None
    error: Optional[str] = None
    output_keys: Optional[List[str]] = None


class PipelineRunResponse(BaseModel):
    run_id: str
    status: str
    summary_text: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    trace: List[TraceEvent] = Field(default_factory=list)
