"""Concurrency limits for heavy pipeline stages."""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Optional


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


TRANSCODE_CONCURRENCY = max(1, _env_int("TRANSCODE_CONCURRENCY", 2))
TRANSCRIBE_CONCURRENCY = max(1, _env_int("TRANSCRIBE_CONCURRENCY", 2))
PIPELINE_STAGE_WAIT_SECONDS = _env_float("PIPELINE_STAGE_WAIT_SECONDS", 300.0)


class ConcurrencyLimiter:
    def __init__(self, max_inflight: int, name: str) -> None:
        self._sem = threading.Semaphore(max_inflight)
        self.name = name

    @contextmanager
    def acquire(self, timeout: Optional[float] = None):
        wait_seconds = timeout if timeout is not None else PIPELINE_STAGE_WAIT_SECONDS
        acquired = self._sem.acquire(timeout=wait_seconds)
        if not acquired:
            raise RuntimeError(f"{self.name} 并发已达上限")
        try:
            yield
        finally:
            self._sem.release()


transcode_limiter = ConcurrencyLimiter(TRANSCODE_CONCURRENCY, "transcode")
transcribe_limiter = ConcurrencyLimiter(TRANSCRIBE_CONCURRENCY, "transcribe")
