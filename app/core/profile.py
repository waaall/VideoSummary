from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict

from app.api.config import get_config
from app.config import PROFILE_VERSION, MODEL_PATH
from app.core.entities import (
    LANGUAGES,
    TranscribeConfig as CoreTranscribeConfig,
)


@dataclass(frozen=True)
class ProcessingProfile:
    """Fixed processing profile for cache identity and validation."""

    profile_version: str
    transcribe_config: CoreTranscribeConfig
    summary_params: Dict[str, object]


def build_transcribe_config() -> CoreTranscribeConfig:
    cfg = get_config()
    lang_key = cfg.transcribe.language.value
    language = LANGUAGES.get(lang_key, "")

    return CoreTranscribeConfig(
        transcribe_model=cfg.transcribe.model,
        transcribe_language=language,
        need_word_time_stamp=True,
        output_format=cfg.transcribe.output_format,
        whisper_model=cfg.whisper.model,
        whisper_api_key=cfg.whisper_api.api_key,
        whisper_api_base=cfg.whisper_api.api_base,
        whisper_api_model=cfg.whisper_api.model,
        whisper_api_prompt=cfg.whisper_api.prompt,
        faster_whisper_program=cfg.faster_whisper.program,
        faster_whisper_model=cfg.faster_whisper.model,
        faster_whisper_model_dir=cfg.faster_whisper.model_dir or str(MODEL_PATH),
        faster_whisper_device=cfg.faster_whisper.device,
        faster_whisper_vad_filter=cfg.faster_whisper.vad_filter,
        faster_whisper_vad_threshold=cfg.faster_whisper.vad_threshold,
        faster_whisper_vad_method=cfg.faster_whisper.vad_method,
        faster_whisper_ff_mdx_kim2=cfg.faster_whisper.ff_mdx_kim2,
        faster_whisper_one_word=cfg.faster_whisper.one_word,
        faster_whisper_prompt=cfg.faster_whisper.prompt,
    )


def build_summary_params() -> Dict[str, object]:
    model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    prompt = os.getenv("LLM_SUMMARY_PROMPT", "请总结以下视频内容的主要观点：")
    try:
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1000"))
    except (TypeError, ValueError):
        max_tokens = 1000
    try:
        max_input_chars = int(os.getenv("LLM_MAX_INPUT_CHARS", "8000"))
    except (TypeError, ValueError):
        max_input_chars = 8000

    return {
        "model": model,
        "max_tokens": max_tokens,
        "max_input_chars": max_input_chars,
        "prompt": prompt,
    }


def get_processing_profile() -> ProcessingProfile:
    return ProcessingProfile(
        profile_version=PROFILE_VERSION,
        transcribe_config=build_transcribe_config(),
        summary_params=build_summary_params(),
    )
