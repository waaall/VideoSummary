from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, List, Optional, Union

import requests

from ..utils.logger import setup_logger
from .asr_data import ASRDataSeg
from .base import BaseASR

logger = setup_logger("whisper_service")


class WhisperServiceASR(BaseASR):
    """HTTP Whisper service ASR implementation.

    Uses a custom HTTP endpoint that returns SRT text.
    """

    def __init__(
        self,
        audio_input: Union[str, bytes],
        base_url: str,
        language: str = "",
        prompt: str = "",
        encode: bool = True,
        task: str = "transcribe",
        vad_filter: bool = False,
        word_timestamps: bool = False,
        output: str = "srt",
        use_cache: bool = False,
    ) -> None:
        super().__init__(audio_input, use_cache)

        self.base_url = base_url.strip().rstrip("/")
        if not self.base_url:
            logger.error("WhisperService init failed: base_url is empty")
            raise ValueError("Whisper service base_url must be set")

        self.language = language
        self.prompt = prompt
        self.encode = encode
        self.task = task
        self.vad_filter = vad_filter
        self.word_timestamps = word_timestamps
        self.output = (output or "srt").strip().lower()

        if self.output != "srt":
            raise ValueError(
                "WhisperServiceASR only supports output=srt in current adapter"
            )

        self._file_ext = self._infer_ext(audio_input)

    def _infer_ext(self, audio_input: Union[str, bytes]) -> str:
        if isinstance(audio_input, str):
            ext = Path(audio_input).suffix.lower().lstrip(".")
            if ext in {"wav", "mp3", "m4a", "flac"}:
                return ext
        # ChunkedASR exports MP3 bytes
        return "mp3"

    def _make_segments(self, resp_data: str) -> List[ASRDataSeg]:
        from .asr_data import ASRData

        asr_data = ASRData.from_srt(resp_data)
        return asr_data.segments

    def _get_key(self) -> str:
        return (
            f"{self.crc32_hex}-{self.language}-{self.prompt}-"
            f"{self.encode}-{self.task}-{self.vad_filter}-"
            f"{self.word_timestamps}-{self.output}"
        )

    def _submit(self) -> str:
        url = self.base_url
        if not url.endswith("/asr"):
            url = f"{url}/asr"

        params = {
            "encode": str(self.encode).lower(),
            "task": self.task,
            "vad_filter": str(self.vad_filter).lower(),
            "word_timestamps": str(self.word_timestamps).lower(),
            "output": self.output,
        }
        if self.language:
            params["language"] = self.language
        if self.prompt:
            params["initial_prompt"] = self.prompt

        content_type = {
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "m4a": "audio/mp4",
            "flac": "audio/flac",
        }.get(self._file_ext, "application/octet-stream")

        files = {
            "audio_file": (
                f"audio.{self._file_ext}",
                self.file_binary or b"",
                content_type,
            )
        }

        logger.info(
            "WhisperService request: url=%s, task=%s, language=%s, vad=%s, word_ts=%s",
            url,
            self.task,
            self.language or "auto",
            self.vad_filter,
            self.word_timestamps,
        )

        resp = None
        try:
            resp = requests.post(url, params=params, files=files, timeout=180)
            resp.raise_for_status()
            return resp.text
        except Exception:
            status_code = resp.status_code if resp is not None else None
            resp_text = resp.text if resp is not None else None
            if resp_text and len(resp_text) > 500:
                resp_text = resp_text[:500] + "..."
            logger.exception(
                "WhisperService request failed: url=%s, status=%s, response=%s",
                url,
                status_code,
                resp_text,
            )
            raise

    def _run(
        self, callback: Optional[Callable[[int, str], None]] = None, **kwargs: Any
    ) -> str:
        return self._submit()
