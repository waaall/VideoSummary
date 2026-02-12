"""API 依赖项模块。

为 FastAPI 路由提供可复用的依赖注入组件，包括：
- 请求来源解析：将 url / local 类型的请求统一解析为 ResolvedSource
- 请求频率限制：基于滑动窗口的内存级限流
- 路径参数校验：job_id、cache_key 的存在性验证
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request

from app.api.persistence import get_store
from app.api.schemas import CacheKeyPathParam, CacheLookupRequest, JobIdPathParam, SummaryRequest
from app.api.settings import get_rate_limit_settings, get_upload_settings
from app.api.uploads import FileNotFoundError as UploadFileNotFoundError
from app.api.uploads import get_file_storage
from app.cache import compute_file_hash
from app.cache.cache_key import compute_cache_key_from_source, normalize_url
from app.cache.cache_service import CacheEntry, get_cache_service


@dataclass
class ResolvedSource:
    """来源解析结果，是 _resolve_source 的返回值。

    将前端传入的 url/file_id/file_hash 等不同形式统一为一个确定性的结构，
    供后续缓存查找和摘要任务使用。
    """

    source_type: str  # "url" 或 "local"
    source_url: str | None  # 仅 url 类型有值
    source_ref: str  # 缓存定位标识：url 类型为规范化 URL，local 类型为 file_hash
    file_hash: str | None  # 文件内容 SHA-256，仅 local 类型有值
    cache_key: str  # 由 source_type + source_ref 计算得到的全局唯一缓存键
    source_name: str | None  # 原始文件名，用于前端展示


# ── 配置常量 ──────────────────────────────────────────────────────────
# 模块加载时从环境变量读取一次，避免每次请求重复解析

upload_settings = get_upload_settings()
rate_limit_settings = get_rate_limit_settings()

# 上传并发信号量，限制同时进行的上传数
UPLOAD_CONCURRENCY = upload_settings.concurrency
UPLOAD_SEMAPHORE = asyncio.Semaphore(UPLOAD_CONCURRENCY)

UPLOAD_RATE_LIMIT_PER_MINUTE = rate_limit_settings.upload_per_minute
SUMMARY_RATE_LIMIT_PER_MINUTE = rate_limit_settings.summary_per_minute

UPLOAD_CHUNK_SIZE = upload_settings.chunk_size
UPLOAD_READ_TIMEOUT_SECONDS = upload_settings.read_timeout_seconds
UPLOAD_WRITE_TIMEOUT_SECONDS = upload_settings.write_timeout_seconds
# 允许实际 body 超出 Content-Length 的宽容字节数
UPLOAD_CONTENT_LENGTH_GRACE_BYTES = upload_settings.content_length_grace_bytes


# ── 滑动窗口限流器 ────────────────────────────────────────────────────


class RateLimiter:
    """基于滑动窗口的内存级限流器。

    每个客户端标识（IP 或 API Key）维护一个时间戳队列，
    窗口内请求数超过阈值时拒绝新请求。线程安全。
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        # key → 请求时间戳队列
        self._buckets: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        """判断 key 是否允许通过。允许则记录时间戳并返回 True。"""
        now = time.time()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            # 清除窗口外的过期时间戳
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True


# 上传和摘要分别使用独立的限流器实例
upload_rate_limiter = RateLimiter(UPLOAD_RATE_LIMIT_PER_MINUTE, 60)
summary_rate_limiter = RateLimiter(SUMMARY_RATE_LIMIT_PER_MINUTE, 60)


def get_client_key(
    *,
    forwarded_for: str | None,
    client_host: str | None,
    api_key: str | None,
) -> str:
    """从请求上下文中提取客户端唯一标识，用于限流桶的 key。

    优先级：API Key > X-Forwarded-For 首个 IP > 直连 IP。
    """
    if api_key:
        return f"token:{api_key}"
    if forwarded_for:
        # X-Forwarded-For 可能包含多级代理，取最左侧的原始客户端 IP
        return f"ip:{forwarded_for.split(',')[0].strip()}"
    return f"ip:{client_host or 'unknown'}"


def _enforce_rate_limit(request: Request, limiter: RateLimiter) -> None:
    """通用限流检查，不通过则抛出 429。"""
    key = get_client_key(
        forwarded_for=request.headers.get("x-forwarded-for"),
        client_host=request.client.host if request.client else None,
        api_key=request.headers.get("x-api-key"),
    )
    if not limiter.allow(key):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


def enforce_upload_rate_limit(request: Request) -> None:
    """FastAPI 依赖项：对上传接口执行限流。"""
    _enforce_rate_limit(request, upload_rate_limiter)


def enforce_summary_rate_limit(request: Request) -> None:
    """FastAPI 依赖项：对摘要接口执行限流。"""
    _enforce_rate_limit(request, summary_rate_limiter)


# ── 来源解析 ──────────────────────────────────────────────────────────


def _resolve_source(
    *,
    source_type: str,
    source_url: str | None,
    file_id: str | None,
    file_hash: str | None,
    persist_file_hash: bool,
) -> ResolvedSource:
    """将前端传入的来源参数统一解析为 ResolvedSource。

    处理两种来源类型：
    - url：对 URL 做规范化，以规范化 URL 作为 source_ref
    - local：根据 file_id 查找上传记录并获取/计算 file_hash，以 hash 作为 source_ref

    Args:
        persist_file_hash: 若为 True，当通过 file_id 首次计算出 file_hash 时，
                           将其回写到持久层，避免后续重复计算。
                           缓存查询场景为 False（只读），摘要提交场景为 True。
    """
    store = get_store()
    source_name: str | None = None
    resolved_file_hash = file_hash
    # 标记是否已通过 file_id 查询上传记录验证过文件存在性
    verified_by_file_id = False

    if source_type == "url":
        if not source_url:
            raise HTTPException(status_code=400, detail="source_type 为 url 时必须提供 source_url")
        source_ref = normalize_url(source_url)

    elif source_type == "local":
        # 场景一：前端传了 file_id 但没传 file_hash，需要从上传记录中获取
        if file_id and not resolved_file_hash:
            try:
                storage = get_file_storage()
                uploaded = storage.get(file_id)
            except UploadFileNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            source_name = uploaded.original_name
            if uploaded.file_hash:
                # 上传时已计算过 hash，直接复用
                resolved_file_hash = uploaded.file_hash
            else:
                # 上传时未计算 hash（大文件等情况），现在补算
                resolved_file_hash = compute_file_hash(str(uploaded.stored_path))
                if persist_file_hash:
                    store.update_upload_file_hash(file_id, resolved_file_hash)
                uploaded.file_hash = resolved_file_hash
            verified_by_file_id = True

        if not resolved_file_hash:
            raise HTTPException(status_code=400, detail="source_type 为 local 时必须提供 file_hash 或 file_id")

        # 场景二：前端直接传了 file_hash，需要验证该 hash 对应的上传记录是否存在
        if not verified_by_file_id:
            upload_record = store.get_upload_by_hash(resolved_file_hash)
            if not upload_record:
                raise HTTPException(status_code=404, detail="file_hash 不存在或已过期")
            source_name = upload_record.get("original_name")
        source_ref = resolved_file_hash
    else:
        raise HTTPException(status_code=400, detail=f"不支持的 source_type: {source_type}")

    # 根据来源类型和标识计算全局唯一的缓存键
    try:
        cache_key = compute_cache_key_from_source(source_type, source_url, resolved_file_hash)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ResolvedSource(
        source_type=source_type,
        source_url=source_url,
        source_ref=source_ref,
        file_hash=resolved_file_hash,
        cache_key=cache_key,
        source_name=source_name,
    )


def resolve_cache_lookup_source(req: CacheLookupRequest) -> ResolvedSource:
    """FastAPI 依赖项：为缓存查询接口解析来源。不回写 file_hash。"""
    return _resolve_source(
        source_type=req.source_type.value,
        source_url=str(req.source_url) if req.source_url is not None else None,
        file_id=req.file_id,
        file_hash=req.file_hash,
        persist_file_hash=False,
    )


def resolve_summary_source(req: SummaryRequest) -> ResolvedSource:
    """FastAPI 依赖项：为摘要提交接口解析来源。首次计算的 file_hash 会回写持久层。"""
    return _resolve_source(
        source_type=req.source_type.value,
        source_url=str(req.source_url) if req.source_url is not None else None,
        file_id=req.file_id,
        file_hash=req.file_hash,
        persist_file_hash=True,
    )


# ── 路径参数校验依赖项 ────────────────────────────────────────────────


def valid_job_id(job_id: JobIdPathParam) -> dict[str, Any]:
    """校验路径中的 job_id 是否存在，存在则返回完整的任务记录。"""
    cache_service = get_cache_service()
    job = cache_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id 不存在")
    return job


def valid_cache_entry(cache_key: CacheKeyPathParam) -> CacheEntry:
    """校验路径中的 cache_key 是否存在，存在则返回完整的缓存条目。"""
    cache_service = get_cache_service()
    entry = cache_service.get_entry(cache_key)
    if not entry:
        raise HTTPException(status_code=404, detail="cache_key 不存在")
    return entry


def valid_cache_key(cache_entry: CacheEntry = Depends(valid_cache_entry)) -> str:
    """依赖 valid_cache_entry，仅提取并返回 cache_key 字符串。"""
    return cache_entry.cache_key
