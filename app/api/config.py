# coding:utf-8
"""后端专用配置模块

配置从 JSON 文件读取，支持环境变量覆盖。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from app.config import SETTINGS_PATH, WORK_PATH
from app.core.entities import (
    FasterWhisperModelEnum,
    SubtitleLayoutEnum,
    SubtitleRenderModeEnum,
    TranscribeLanguageEnum,
    TranscribeModelEnum,
    TranscribeOutputFormatEnum,
    TranslatorServiceEnum,
    VadMethodEnum,
    VideoQualityEnum,
    WhisperModelEnum,
)
from app.core.translate.types import TargetLanguage


@dataclass
class LLMConfig:
    """通用 OpenAI 兼容 LLM 配置。"""

    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"


@dataclass
class TranslateConfig:
    """翻译配置"""

    service: TranslatorServiceEnum = TranslatorServiceEnum.BING
    need_reflect_translate: bool = False
    deeplx_endpoint: str = ""
    batch_size: int = 10
    thread_num: int = 10


@dataclass
class TranscribeConfig:
    """转录配置"""

    model: TranscribeModelEnum = TranscribeModelEnum.BIJIAN
    output_format: TranscribeOutputFormatEnum = TranscribeOutputFormatEnum.SRT
    language: TranscribeLanguageEnum = TranscribeLanguageEnum.AUTO


@dataclass
class WhisperConfig:
    """Whisper Cpp 配置"""

    model: WhisperModelEnum = WhisperModelEnum.LARGE_V3_TURBO


@dataclass
class FasterWhisperConfig:
    """Faster Whisper 配置"""

    program: str = "faster-whisper-xxl.exe"
    model: FasterWhisperModelEnum = FasterWhisperModelEnum.TINY
    model_dir: str = ""
    device: str = "cuda"
    vad_filter: bool = True
    vad_threshold: float = 0.4
    vad_method: VadMethodEnum = VadMethodEnum.SILERO_V4
    ff_mdx_kim2: bool = False
    one_word: bool = True
    prompt: str = ""


@dataclass
class WhisperAPIConfig:
    """Whisper API 配置"""

    api_base: str = ""
    api_key: str = ""
    model: str = ""
    prompt: str = ""


@dataclass
class WhisperServiceConfig:
    """Whisper Service 配置（自建 HTTP 服务）"""

    base_url: str = ""
    encode: bool = True
    task: str = "transcribe"
    vad_filter: bool = False
    output: str = "srt"
    prompt: str = ""


@dataclass
class SubtitleConfig:
    """字幕配置"""

    need_optimize: bool = False
    need_translate: bool = False
    need_split: bool = False
    target_language: TargetLanguage = TargetLanguage.SIMPLIFIED_CHINESE
    max_word_count_cjk: int = 28
    max_word_count_english: int = 20
    custom_prompt_text: str = ""


@dataclass
class VideoConfig:
    """视频合成配置"""

    soft_subtitle: bool = False
    need_video: bool = True
    quality: VideoQualityEnum = VideoQualityEnum.MEDIUM
    use_subtitle_style: bool = False


@dataclass
class SubtitleStyleConfig:
    """字幕样式配置"""

    style_name: str = "default"
    layout: SubtitleLayoutEnum = SubtitleLayoutEnum.TRANSLATE_ON_TOP
    preview_image: str = ""
    render_mode: SubtitleRenderModeEnum = SubtitleRenderModeEnum.ROUNDED_BG

    # 圆角背景样式
    rounded_bg_font_name: str = "LXGW WenKai"
    rounded_bg_font_size: int = 52
    rounded_bg_color: str = "#191919C8"
    rounded_bg_text_color: str = "#FFFFFF"
    rounded_bg_corner_radius: int = 12
    rounded_bg_padding_h: int = 28
    rounded_bg_padding_v: int = 14
    rounded_bg_margin_bottom: int = 60
    rounded_bg_line_spacing: int = 10
    rounded_bg_letter_spacing: int = 0


@dataclass
class CacheConfig:
    """缓存配置"""

    enabled: bool = True


@dataclass
class BackendConfig:
    """后端总配置"""

    llm: LLMConfig = field(default_factory=LLMConfig)
    translate: TranslateConfig = field(default_factory=TranslateConfig)
    transcribe: TranscribeConfig = field(default_factory=TranscribeConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    faster_whisper: FasterWhisperConfig = field(default_factory=FasterWhisperConfig)
    whisper_api: WhisperAPIConfig = field(default_factory=WhisperAPIConfig)
    whisper_service: WhisperServiceConfig = field(default_factory=WhisperServiceConfig)
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    subtitle_style: SubtitleStyleConfig = field(default_factory=SubtitleStyleConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    work_dir: Path = field(default_factory=lambda: WORK_PATH)


def _enum_to_str(obj: Any) -> Any:
    """递归将枚举转换为字符串"""
    if hasattr(obj, "value") and hasattr(obj, "name"):
        return obj.value if isinstance(obj.value, str) else obj.name
    if isinstance(obj, dict):
        return {k: _enum_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_enum_to_str(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _dataclass_to_dict(obj: Any) -> dict:
    """将 dataclass 转换为字典（递归）"""
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for key in obj.__dataclass_fields__:
            value = getattr(obj, key)
            result[key] = _dataclass_to_dict(value)
        return result
    return _enum_to_str(obj)


def _coerce_value(current: Any, value: Any) -> Any:
    """按当前字段类型尝试转换值"""
    if isinstance(current, Enum):
        try:
            return type(current)(value)
        except Exception:
            return current
    if isinstance(current, Path):
        try:
            return Path(value)
        except Exception:
            return current
    return value


def _apply_config(cfg: Any, data: dict) -> None:
    """将 JSON 写入 dataclass（递归）"""
    if not hasattr(cfg, "__dataclass_fields__"):
        return
    for key in cfg.__dataclass_fields__:
        if key not in data:
            continue
        current_value = getattr(cfg, key)
        incoming = data[key]
        if hasattr(current_value, "__dataclass_fields__") and isinstance(incoming, dict):
            _apply_config(current_value, incoming)
        else:
            setattr(cfg, key, _coerce_value(current_value, incoming))


def _apply_env_overrides(config: BackendConfig) -> None:
    """应用环境变量覆盖。仅对非空值生效，避免空字符串覆盖文件配置。"""
    env_model = os.getenv("LLM_MODEL", "").strip()
    if env_model:
        config.llm.model = env_model

    env_api_key = os.getenv("LLM_API_KEY", "").strip()
    if env_api_key:
        config.llm.api_key = env_api_key

    env_base_url = os.getenv("LLM_BASE_URL", "").strip()
    if env_base_url:
        config.llm.base_url = env_base_url


def load_config(path: Path | None = None) -> BackendConfig:
    """从 JSON 文件加载配置（仅支持新结构）

    Args:
        path: 配置文件路径，默认使用 SETTINGS_PATH

    Returns:
        BackendConfig 实例
    """
    path = path or SETTINGS_PATH
    config = BackendConfig()

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = None

        if isinstance(data, dict):
            _apply_config(config, data)

    _apply_env_overrides(config)

    return config


def save_config(config: BackendConfig, path: Path | None = None) -> None:
    """保存配置到 JSON 文件

    Args:
        config: BackendConfig 实例
        path: 配置文件路径，默认使用 SETTINGS_PATH
    """
    path = path or SETTINGS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    data = _dataclass_to_dict(config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# 全局配置实例（懒加载）
_backend_cfg: BackendConfig | None = None


def get_config() -> BackendConfig:
    """获取全局配置实例（单例）"""
    global _backend_cfg
    if _backend_cfg is None:
        _backend_cfg = load_config()
    return _backend_cfg


def reload_config() -> BackendConfig:
    """重新加载配置"""
    global _backend_cfg
    _backend_cfg = load_config()
    return _backend_cfg
