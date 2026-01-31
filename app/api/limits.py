"""API rate limiting and concurrency controls."""
from __future__ import annotations

import asyncio
import os
import threading
import time
from collections import deque
from typing import Deque, Dict, Optional


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


UPLOAD_CONCURRENCY = max(1, _env_int("UPLOAD_CONCURRENCY", 2))
UPLOAD_SEMAPHORE = asyncio.Semaphore(UPLOAD_CONCURRENCY)

UPLOAD_RATE_LIMIT_PER_MINUTE = max(1, _env_int("UPLOAD_RATE_LIMIT_PER_MINUTE", 30))
PIPELINE_RATE_LIMIT_PER_MINUTE = max(1, _env_int("PIPELINE_RATE_LIMIT_PER_MINUTE", 60))

UPLOAD_CHUNK_SIZE = max(1024 * 1024, _env_int("UPLOAD_CHUNK_SIZE", 8 * 1024 * 1024))
UPLOAD_READ_TIMEOUT_SECONDS = _env_float("UPLOAD_READ_TIMEOUT_SECONDS", 30.0)
UPLOAD_WRITE_TIMEOUT_SECONDS = _env_float("UPLOAD_WRITE_TIMEOUT_SECONDS", 30.0)
UPLOAD_CONTENT_LENGTH_GRACE_BYTES = _env_int(
    "UPLOAD_CONTENT_LENGTH_GRACE_BYTES", 10 * 1024 * 1024
)


class RateLimiter:
    """Simple in-memory sliding-window limiter."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._buckets: Dict[str, Deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True


upload_rate_limiter = RateLimiter(UPLOAD_RATE_LIMIT_PER_MINUTE, 60)
pipeline_rate_limiter = RateLimiter(PIPELINE_RATE_LIMIT_PER_MINUTE, 60)


def get_client_key(
    *,
    forwarded_for: Optional[str],
    client_host: Optional[str],
    api_key: Optional[str],
) -> str:
    if api_key:
        return f"token:{api_key}"
    if forwarded_for:
        return f"ip:{forwarded_for.split(',')[0].strip()}"
    return f"ip:{client_host or 'unknown'}"
