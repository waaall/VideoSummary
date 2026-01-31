from __future__ import annotations

from typing import Any, Dict, Optional

from app.api.config import get_config
from app.api.schemas import PipelineConfig, PipelineEdgeConfig, PipelineNodeConfig
from app.config import MODEL_PATH
from app.core.entities import (
    LANGUAGES,
    FasterWhisperModelEnum,
    TranscribeConfig as CoreTranscribeConfig,
    TranscribeModelEnum,
    TranscribeOutputFormatEnum,
    VadMethodEnum,
    WhisperModelEnum,
)


def _coerce_enum(enum_cls, value):
    if isinstance(value, enum_cls):
        return value
    if value is None:
        return None
    try:
        return enum_cls(value)
    except Exception:
        pass
    if isinstance(value, str):
        try:
            return enum_cls[value]
        except Exception:
            return None
    return None


def _apply_transcribe_overrides(
    config: CoreTranscribeConfig, overrides: Dict[str, Any]
) -> CoreTranscribeConfig:
    for key, value in overrides.items():
        if not hasattr(config, key):
            continue
        if key == "transcribe_model":
            value = _coerce_enum(TranscribeModelEnum, value) or config.transcribe_model
        elif key == "output_format":
            value = (
                _coerce_enum(TranscribeOutputFormatEnum, value) or config.output_format
            )
        elif key == "whisper_model":
            value = _coerce_enum(WhisperModelEnum, value) or config.whisper_model
        elif key == "faster_whisper_model":
            value = (
                _coerce_enum(FasterWhisperModelEnum, value)
                or config.faster_whisper_model
            )
        elif key == "faster_whisper_vad_method":
            value = _coerce_enum(VadMethodEnum, value) or config.faster_whisper_vad_method
        elif key == "transcribe_language":
            if isinstance(value, str) and value in LANGUAGES:
                value = LANGUAGES[value]
        setattr(config, key, value)
    return config


def build_transcribe_config(overrides: Optional[Dict[str, Any]] = None) -> CoreTranscribeConfig:
    cfg = get_config()
    lang_key = cfg.transcribe.language.value
    language = LANGUAGES.get(lang_key, "")

    config = CoreTranscribeConfig(
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

    if overrides:
        config = _apply_transcribe_overrides(config, overrides)

    return config


def _build_summary_params(options: Dict[str, Any]) -> Dict[str, Any]:
    summary_params: Dict[str, Any] = {}
    summary_cfg = options.get("summary", {})

    if isinstance(summary_cfg, dict):
        if summary_cfg.get("model"):
            summary_params["model"] = summary_cfg["model"]
        if summary_cfg.get("max_tokens"):
            summary_params["max_tokens"] = summary_cfg["max_tokens"]
        if summary_cfg.get("prompt"):
            summary_params["prompt"] = summary_cfg["prompt"]

    return summary_params


def build_url_auto_pipeline(options: Dict[str, Any]) -> PipelineConfig:
    work_dir = options.get("work_dir")
    audio_track_index = options.get("audio_track_index")
    summary_params = _build_summary_params(options)
    transcribe_config = build_transcribe_config(options.get("transcribe_config"))

    download_params: Dict[str, Any] = {}
    if work_dir:
        download_params["work_dir"] = work_dir
    download_overrides = options.get("download")
    if isinstance(download_overrides, dict):
        if download_overrides.get("max_filesize_mb") is not None:
            download_params["max_filesize_mb"] = download_overrides["max_filesize_mb"]
        if download_overrides.get("rate_limit") is not None:
            download_params["rate_limit"] = download_overrides["rate_limit"]

    extract_audio_params: Dict[str, Any] = {}
    if audio_track_index is not None:
        extract_audio_params["audio_track_index"] = audio_track_index

    return PipelineConfig(
        version="v1",
        nodes=[
            PipelineNodeConfig(id="input", type="InputNode", params={}),
            PipelineNodeConfig(id="meta", type="FetchMetadataNode", params={}),
            PipelineNodeConfig(
                id="download_sub", type="DownloadSubtitleNode", params=download_params
            ),
            PipelineNodeConfig(id="parse", type="ParseSubtitleNode", params={}),
            PipelineNodeConfig(id="validate", type="ValidateSubtitleNode", params={}),
            PipelineNodeConfig(
                id="summary", type="TextSummarizeNode", params=summary_params
            ),
            PipelineNodeConfig(
                id="download_video", type="DownloadVideoNode", params=download_params
            ),
            PipelineNodeConfig(
                id="extract_audio", type="ExtractAudioNode", params=extract_audio_params
            ),
            PipelineNodeConfig(
                id="transcribe", type="TranscribeNode", params={"config": transcribe_config}
            ),
            PipelineNodeConfig(id="detect_silence", type="DetectSilenceNode", params={}),
            PipelineNodeConfig(id="sample_frames", type="SampleFramesNode", params={}),
            PipelineNodeConfig(id="vlm_summary", type="VlmSummarizeNode", params={}),
            PipelineNodeConfig(id="merge_summary", type="MergeSummaryNode", params={}),
        ],
        edges=[
            PipelineEdgeConfig(source="input", target="meta"),
            PipelineEdgeConfig(source="input", target="download_sub"),
            PipelineEdgeConfig(source="download_sub", target="parse"),
            PipelineEdgeConfig(source="parse", target="validate"),
            PipelineEdgeConfig(source="meta", target="validate"),
            PipelineEdgeConfig(
                source="validate", target="summary", condition="subtitle_valid == True"
            ),
            PipelineEdgeConfig(
                source="validate",
                target="download_video",
                condition="subtitle_valid == False",
            ),
            PipelineEdgeConfig(source="download_video", target="extract_audio"),
            PipelineEdgeConfig(source="extract_audio", target="transcribe"),
            PipelineEdgeConfig(source="transcribe", target="detect_silence"),
            PipelineEdgeConfig(
                source="detect_silence",
                target="summary",
                condition="is_silent == False",
            ),
            PipelineEdgeConfig(
                source="detect_silence",
                target="sample_frames",
                condition="is_silent == True",
            ),
            PipelineEdgeConfig(source="sample_frames", target="vlm_summary"),
            PipelineEdgeConfig(source="vlm_summary", target="merge_summary"),
        ],
    )


def build_local_auto_pipeline(options: Dict[str, Any]) -> PipelineConfig:
    audio_track_index = options.get("audio_track_index")
    summary_params = _build_summary_params(options)
    transcribe_config = build_transcribe_config(options.get("transcribe_config"))
    warning_message = options.get("silent_warning", "无有效信息")

    extract_audio_params: Dict[str, Any] = {}
    if audio_track_index is not None:
        extract_audio_params["audio_track_index"] = audio_track_index

    return PipelineConfig(
        version="v1",
        nodes=[
            PipelineNodeConfig(id="input", type="InputNode", params={}),
            PipelineNodeConfig(id="meta", type="FetchMetadataNode", params={}),
            PipelineNodeConfig(id="parse", type="ParseSubtitleNode", params={}),
            PipelineNodeConfig(
                id="summary", type="TextSummarizeNode", params=summary_params
            ),
            PipelineNodeConfig(
                id="extract_audio", type="ExtractAudioNode", params=extract_audio_params
            ),
            PipelineNodeConfig(
                id="transcribe", type="TranscribeNode", params={"config": transcribe_config}
            ),
            PipelineNodeConfig(id="detect_silence", type="DetectSilenceNode", params={}),
            PipelineNodeConfig(
                id="warning",
                type="WarningNode",
                params={"message": warning_message},
            ),
            PipelineNodeConfig(id="sample_frames", type="SampleFramesNode", params={}),
            PipelineNodeConfig(id="vlm_summary", type="VlmSummarizeNode", params={}),
            PipelineNodeConfig(id="merge_summary", type="MergeSummaryNode", params={}),
        ],
        edges=[
            PipelineEdgeConfig(
                source="input",
                target="parse",
                condition="local_input_type == 'subtitle'",
            ),
            PipelineEdgeConfig(
                source="parse",
                target="summary",
                condition="local_input_type == 'subtitle'",
            ),
            PipelineEdgeConfig(
                source="input",
                target="meta",
                condition="local_input_type in ['audio','video']",
            ),
            PipelineEdgeConfig(
                source="meta",
                target="extract_audio",
                condition="local_input_type == 'video'",
            ),
            PipelineEdgeConfig(
                source="meta",
                target="transcribe",
                condition="local_input_type == 'audio'",
            ),
            PipelineEdgeConfig(
                source="extract_audio",
                target="transcribe",
                condition="local_input_type == 'video'",
            ),
            PipelineEdgeConfig(
                source="transcribe",
                target="detect_silence",
                condition="local_input_type in ['audio','video']",
            ),
            PipelineEdgeConfig(
                source="detect_silence",
                target="warning",
                condition="local_input_type == 'audio' and is_silent == True",
            ),
            PipelineEdgeConfig(
                source="detect_silence",
                target="summary",
                condition="local_input_type == 'audio' and is_silent == False",
            ),
            PipelineEdgeConfig(
                source="detect_silence",
                target="sample_frames",
                condition="local_input_type == 'video' and is_silent == True",
            ),
            PipelineEdgeConfig(
                source="detect_silence",
                target="summary",
                condition="local_input_type == 'video' and is_silent == False",
            ),
            PipelineEdgeConfig(source="sample_frames", target="vlm_summary"),
            PipelineEdgeConfig(source="vlm_summary", target="merge_summary"),
        ],
    )
