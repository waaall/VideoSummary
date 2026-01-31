"""管线执行上下文 - 承载全局状态"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from app.api.schemas import PipelineInputs, PipelineThresholds, TraceEvent
from app.core.asr.asr_data import ASRData


@dataclass
class PipelineContext:
    """管线执行上下文，承载执行过程中的全局状态"""

    # 运行标识
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # 输入相关
    source_type: str = ""
    source_url: Optional[str] = None
    video_path: Optional[str] = None
    subtitle_path: Optional[str] = None
    audio_path: Optional[str] = None

    # 阈值配置
    thresholds: PipelineThresholds = field(default_factory=PipelineThresholds)

    # 中间状态
    video_duration: Optional[float] = None
    subtitle_valid: bool = False
    subtitle_coverage_ratio: Optional[float] = None
    is_silent: bool = False
    audio_rms: Optional[float] = None
    transcript_token_count: Optional[int] = None

    # 输出
    summary_text: Optional[str] = None

    # 执行追踪
    trace: List[TraceEvent] = field(default_factory=list)

    # 扩展字段存储
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_inputs(
        cls,
        inputs: PipelineInputs,
        thresholds: Optional[PipelineThresholds] = None,
    ) -> "PipelineContext":
        """从 PipelineInputs 构造上下文"""
        return cls(
            source_type=inputs.source_type,
            source_url=inputs.source_url,
            video_path=inputs.video_path,
            subtitle_path=inputs.subtitle_path,
            audio_path=inputs.audio_path,
            thresholds=thresholds or PipelineThresholds(),
            extra=inputs.extra.copy(),
        )

    def add_trace(
        self,
        node_id: str,
        status: str,
        elapsed_ms: Optional[int] = None,
        error: Optional[str] = None,
        output_keys: Optional[List[str]] = None,
    ) -> None:
        """添加执行追踪记录"""
        self.trace.append(
            TraceEvent(
                node_id=node_id,
                status=status,
                elapsed_ms=elapsed_ms,
                error=error,
                output_keys=output_keys,
            )
        )

    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文中的值，优先从标准字段获取，否则从 extra 获取"""
        if hasattr(self, key) and key != "extra":
            return getattr(self, key)
        return self.extra.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置上下文中的值，优先写入标准字段，否则写入 extra"""
        if hasattr(self, key) and key not in ("extra", "trace", "thresholds", "run_id"):
            setattr(self, key, value)
        else:
            self.extra[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典（用于响应返回）"""
        result = {
            "run_id": self.run_id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "video_path": self.video_path,
            "subtitle_path": self.subtitle_path,
            "audio_path": self.audio_path,
            "video_duration": self.video_duration,
            "subtitle_valid": self.subtitle_valid,
            "subtitle_coverage_ratio": self.subtitle_coverage_ratio,
            "is_silent": self.is_silent,
            "audio_rms": self.audio_rms,
            "transcript_token_count": self.transcript_token_count,
            "summary_text": self.summary_text,
        }
        # 合并 extra 字段
        result.update(self._serialize_value(self.extra))
        return result

    def _serialize_value(self, value: Any) -> Any:
        """将上下文值序列化为可 JSON 输出的结构"""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, ASRData):
            return value.to_json()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._serialize_value(v) for v in value]
        if is_dataclass(value):
            return self._serialize_value(asdict(value))
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except Exception:
                pass
        return str(value)

    def to_eval_namespace(self) -> Dict[str, Any]:
        """导出用于条件表达式评估的命名空间"""
        return {
            "source_type": self.source_type,
            "subtitle_valid": self.subtitle_valid,
            "is_silent": self.is_silent,
            "video_duration": self.video_duration,
            "subtitle_coverage_ratio": self.subtitle_coverage_ratio,
            "audio_rms": self.audio_rms,
            "transcript_token_count": self.transcript_token_count,
            # 阈值相关
            "subtitle_coverage_min": self.thresholds.subtitle_coverage_min,
            "transcript_token_per_min_min": self.thresholds.transcript_token_per_min_min,
            "audio_rms_max_for_silence": self.thresholds.audio_rms_max_for_silence,
            # extra 中的值也可用于条件
            **self.extra,
        }
