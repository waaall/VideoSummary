# coding:utf-8
"""后端专用配置模块（无 Qt 依赖）

提供与 app/common/config.py 相同的配置项，但使用纯 Python 实现。
配置从 JSON 文件读取，支持环境变量覆盖。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import SETTINGS_PATH, WORK_PATH
from app.core.entities import (
    FasterWhisperModelEnum,
    LLMServiceEnum,
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
    """LLM 服务配置"""

    service: LLMServiceEnum = LLMServiceEnum.OPENAI

    # OpenAI
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"

    # SiliconCloud
    silicon_cloud_model: str = "gpt-4o-mini"
    silicon_cloud_api_key: str = ""
    silicon_cloud_api_base: str = "https://api.siliconflow.cn/v1"

    # DeepSeek
    deepseek_model: str = "deepseek-chat"
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com/v1"

    # Ollama
    ollama_model: str = "llama2"
    ollama_api_key: str = "ollama"
    ollama_api_base: str = "http://localhost:11434/v1"

    # LM Studio
    lm_studio_model: str = "qwen2.5:7b"
    lm_studio_api_key: str = "lmstudio"
    lm_studio_api_base: str = "http://localhost:1234/v1"

    # Gemini
    gemini_model: str = "gemini-pro"
    gemini_api_key: str = ""
    gemini_api_base: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # ChatGLM
    chatglm_model: str = "glm-4"
    chatglm_api_key: str = ""
    chatglm_api_base: str = "https://open.bigmodel.cn/api/paas/v4"


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
    language: TranscribeLanguageEnum = TranscribeLanguageEnum.ENGLISH


@dataclass
class WhisperConfig:
    """Whisper Cpp 配置"""

    model: WhisperModelEnum = WhisperModelEnum.TINY


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


def load_config(path: Path | None = None) -> BackendConfig:
    """从 JSON 文件加载配置

    Args:
        path: 配置文件路径，默认使用 SETTINGS_PATH

    Returns:
        BackendConfig 实例
    """
    path = path or SETTINGS_PATH
    config = BackendConfig()

    if not path.exists():
        return config

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return config

    # 映射旧配置键到新结构
    _apply_llm_config(config.llm, data)
    _apply_translate_config(config.translate, data)
    _apply_transcribe_config(config.transcribe, data)
    _apply_whisper_config(config.whisper, data)
    _apply_faster_whisper_config(config.faster_whisper, data)
    _apply_whisper_api_config(config.whisper_api, data)
    _apply_subtitle_config(config.subtitle, data)
    _apply_video_config(config.video, data)
    _apply_subtitle_style_config(config.subtitle_style, data)
    _apply_cache_config(config.cache, data)

    # work_dir
    if "Save" in data and "Work_Dir" in data["Save"]:
        config.work_dir = Path(data["Save"]["Work_Dir"])

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


# --- 配置映射辅助函数 ---


def _apply_llm_config(cfg: LLMConfig, data: dict) -> None:
    """应用 LLM 配置"""
    llm = data.get("LLM", {})
    if "LLMService" in llm:
        try:
            cfg.service = LLMServiceEnum(llm["LLMService"])
        except ValueError:
            pass
    cfg.openai_model = llm.get("OpenAI_Model", cfg.openai_model)
    cfg.openai_api_key = os.environ.get("OPENAI_API_KEY", llm.get("OpenAI_API_Key", cfg.openai_api_key))
    cfg.openai_api_base = llm.get("OpenAI_API_Base", cfg.openai_api_base)
    cfg.silicon_cloud_model = llm.get("SiliconCloud_Model", cfg.silicon_cloud_model)
    cfg.silicon_cloud_api_key = llm.get("SiliconCloud_API_Key", cfg.silicon_cloud_api_key)
    cfg.silicon_cloud_api_base = llm.get("SiliconCloud_API_Base", cfg.silicon_cloud_api_base)
    cfg.deepseek_model = llm.get("DeepSeek_Model", cfg.deepseek_model)
    cfg.deepseek_api_key = llm.get("DeepSeek_API_Key", cfg.deepseek_api_key)
    cfg.deepseek_api_base = llm.get("DeepSeek_API_Base", cfg.deepseek_api_base)
    cfg.ollama_model = llm.get("Ollama_Model", cfg.ollama_model)
    cfg.ollama_api_key = llm.get("Ollama_API_Key", cfg.ollama_api_key)
    cfg.ollama_api_base = llm.get("Ollama_API_Base", cfg.ollama_api_base)
    cfg.lm_studio_model = llm.get("LmStudio_Model", cfg.lm_studio_model)
    cfg.lm_studio_api_key = llm.get("LmStudio_API_Key", cfg.lm_studio_api_key)
    cfg.lm_studio_api_base = llm.get("LmStudio_API_Base", cfg.lm_studio_api_base)
    cfg.gemini_model = llm.get("Gemini_Model", cfg.gemini_model)
    cfg.gemini_api_key = llm.get("Gemini_API_Key", cfg.gemini_api_key)
    cfg.gemini_api_base = llm.get("Gemini_API_Base", cfg.gemini_api_base)
    cfg.chatglm_model = llm.get("ChatGLM_Model", cfg.chatglm_model)
    cfg.chatglm_api_key = llm.get("ChatGLM_API_Key", cfg.chatglm_api_key)
    cfg.chatglm_api_base = llm.get("ChatGLM_API_Base", cfg.chatglm_api_base)


def _apply_translate_config(cfg: TranslateConfig, data: dict) -> None:
    """应用翻译配置"""
    tr = data.get("Translate", {})
    if "TranslatorServiceEnum" in tr:
        try:
            cfg.service = TranslatorServiceEnum(tr["TranslatorServiceEnum"])
        except ValueError:
            pass
    cfg.need_reflect_translate = tr.get("NeedReflectTranslate", cfg.need_reflect_translate)
    cfg.deeplx_endpoint = tr.get("DeeplxEndpoint", cfg.deeplx_endpoint)
    cfg.batch_size = tr.get("BatchSize", cfg.batch_size)
    cfg.thread_num = tr.get("ThreadNum", cfg.thread_num)


def _apply_transcribe_config(cfg: TranscribeConfig, data: dict) -> None:
    """应用转录配置"""
    tc = data.get("Transcribe", {})
    if "TranscribeModel" in tc:
        try:
            cfg.model = TranscribeModelEnum(tc["TranscribeModel"])
        except ValueError:
            pass
    if "OutputFormat" in tc:
        try:
            cfg.output_format = TranscribeOutputFormatEnum(tc["OutputFormat"])
        except ValueError:
            pass
    if "TranscribeLanguage" in tc:
        try:
            cfg.language = TranscribeLanguageEnum(tc["TranscribeLanguage"])
        except ValueError:
            pass


def _apply_whisper_config(cfg: WhisperConfig, data: dict) -> None:
    """应用 Whisper 配置"""
    ws = data.get("Whisper", {})
    if "WhisperModel" in ws:
        try:
            cfg.model = WhisperModelEnum(ws["WhisperModel"])
        except ValueError:
            pass


def _apply_faster_whisper_config(cfg: FasterWhisperConfig, data: dict) -> None:
    """应用 Faster Whisper 配置"""
    fw = data.get("FasterWhisper", {})
    cfg.program = fw.get("Program", cfg.program)
    if "Model" in fw:
        try:
            cfg.model = FasterWhisperModelEnum(fw["Model"])
        except ValueError:
            pass
    cfg.model_dir = fw.get("ModelDir", cfg.model_dir)
    cfg.device = fw.get("Device", cfg.device)
    cfg.vad_filter = fw.get("VadFilter", cfg.vad_filter)
    cfg.vad_threshold = fw.get("VadThreshold", cfg.vad_threshold)
    if "VadMethod" in fw:
        try:
            cfg.vad_method = VadMethodEnum(fw["VadMethod"])
        except ValueError:
            pass
    cfg.ff_mdx_kim2 = fw.get("FfMdxKim2", cfg.ff_mdx_kim2)
    cfg.one_word = fw.get("OneWord", cfg.one_word)
    cfg.prompt = fw.get("Prompt", cfg.prompt)


def _apply_whisper_api_config(cfg: WhisperAPIConfig, data: dict) -> None:
    """应用 Whisper API 配置"""
    wa = data.get("WhisperAPI", {})
    cfg.api_base = wa.get("WhisperApiBase", cfg.api_base)
    cfg.api_key = wa.get("WhisperApiKey", cfg.api_key)
    cfg.model = wa.get("WhisperApiModel", cfg.model)
    cfg.prompt = wa.get("WhisperApiPrompt", cfg.prompt)


def _apply_subtitle_config(cfg: SubtitleConfig, data: dict) -> None:
    """应用字幕配置"""
    sub = data.get("Subtitle", {})
    cfg.need_optimize = sub.get("NeedOptimize", cfg.need_optimize)
    cfg.need_translate = sub.get("NeedTranslate", cfg.need_translate)
    cfg.need_split = sub.get("NeedSplit", cfg.need_split)
    if "TargetLanguage" in sub:
        try:
            cfg.target_language = TargetLanguage(sub["TargetLanguage"])
        except ValueError:
            pass
    cfg.max_word_count_cjk = sub.get("MaxWordCountCJK", cfg.max_word_count_cjk)
    cfg.max_word_count_english = sub.get("MaxWordCountEnglish", cfg.max_word_count_english)
    cfg.custom_prompt_text = sub.get("CustomPromptText", cfg.custom_prompt_text)


def _apply_video_config(cfg: VideoConfig, data: dict) -> None:
    """应用视频配置"""
    vid = data.get("Video", {})
    cfg.soft_subtitle = vid.get("SoftSubtitle", cfg.soft_subtitle)
    cfg.need_video = vid.get("NeedVideo", cfg.need_video)
    if "VideoQuality" in vid:
        try:
            cfg.quality = VideoQualityEnum(vid["VideoQuality"])
        except ValueError:
            pass
    cfg.use_subtitle_style = vid.get("UseSubtitleStyle", cfg.use_subtitle_style)


def _apply_subtitle_style_config(cfg: SubtitleStyleConfig, data: dict) -> None:
    """应用字幕样式配置"""
    ss = data.get("SubtitleStyle", {})
    cfg.style_name = ss.get("StyleName", cfg.style_name)
    if "Layout" in ss:
        try:
            cfg.layout = SubtitleLayoutEnum(ss["Layout"])
        except ValueError:
            pass
    cfg.preview_image = ss.get("PreviewImage", cfg.preview_image)
    if "RenderMode" in ss:
        try:
            cfg.render_mode = SubtitleRenderModeEnum(ss["RenderMode"])
        except ValueError:
            pass

    # 圆角背景样式
    rb = data.get("RoundedBgStyle", {})
    cfg.rounded_bg_font_name = rb.get("FontName", cfg.rounded_bg_font_name)
    cfg.rounded_bg_font_size = rb.get("FontSize", cfg.rounded_bg_font_size)
    cfg.rounded_bg_color = rb.get("BgColor", cfg.rounded_bg_color)
    cfg.rounded_bg_text_color = rb.get("TextColor", cfg.rounded_bg_text_color)
    cfg.rounded_bg_corner_radius = rb.get("CornerRadius", cfg.rounded_bg_corner_radius)
    cfg.rounded_bg_padding_h = rb.get("PaddingH", cfg.rounded_bg_padding_h)
    cfg.rounded_bg_padding_v = rb.get("PaddingV", cfg.rounded_bg_padding_v)
    cfg.rounded_bg_margin_bottom = rb.get("MarginBottom", cfg.rounded_bg_margin_bottom)
    cfg.rounded_bg_line_spacing = rb.get("LineSpacing", cfg.rounded_bg_line_spacing)
    cfg.rounded_bg_letter_spacing = rb.get("LetterSpacing", cfg.rounded_bg_letter_spacing)


def _apply_cache_config(cfg: CacheConfig, data: dict) -> None:
    """应用缓存配置"""
    cache = data.get("Cache", {})
    cfg.enabled = cache.get("CacheEnabled", cfg.enabled)


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
