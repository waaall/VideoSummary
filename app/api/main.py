from __future__ import annotations

import os
import uuid

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.schemas import (
    CacheEntryResponse,
    CacheDeleteResponse,
    CacheLookupRequest,
    CacheLookupResponse,
    JobStatusResponse,
    SummaryRequest,
    SummaryResponse,
    UploadResponse,
)
from app.api.persistence import get_store
from app.api.uploads import (
    FileNotFoundError as UploadFileNotFoundError,
    FileSizeError,
    FileTimeoutError,
    FileTypeError,
    get_file_storage,
)
from app.api.limits import (
    UPLOAD_CONTENT_LENGTH_GRACE_BYTES,
    UPLOAD_READ_TIMEOUT_SECONDS,
    UPLOAD_SEMAPHORE,
    UPLOAD_WRITE_TIMEOUT_SECONDS,
    UPLOAD_CHUNK_SIZE,
    get_client_key,
    summary_rate_limiter,
    upload_rate_limiter,
)
from app.api.worker import CacheJob, get_job_queue
from app.cache import compute_file_hash, start_gc_background
from app.cache.cache_key import compute_cache_key_from_source, normalize_url
from app.cache.cache_service import get_cache_service
from app.core.utils.logger import setup_logger

APP_NAME = "VideoSummary API"
VERSION = "0.1.0"

app = FastAPI(title=APP_NAME, version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # 若 allow_credentials=True，allow_origins 不能为 "*"（浏览器会拒绝）。
    # 公开 API 默认关闭凭证。
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger = setup_logger("api")


_STATUS_ERROR_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    408: "REQUEST_TIMEOUT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_SERVER_ERROR",
}


def _error_code_for_status(status_code: int) -> str:
    return _STATUS_ERROR_CODE_MAP.get(status_code, f"HTTP_{status_code}")


def _get_or_create_request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    if existing:
        return existing

    request_id = request.headers.get("x-request-id")
    if request_id:
        request.state.request_id = request_id
        return request_id

    request_id = f"req_{uuid.uuid4().hex}"
    request.state.request_id = request_id
    return request_id


def _build_error_payload(
    *,
    request: Request,
    status: int,
    message: str,
    code: str,
    detail=None,
    errors=None,
) -> dict:
    payload = {
        "message": message,
        "code": code,
        "status": status,
        "request_id": _get_or_create_request_id(request),
    }
    if detail is not None:
        payload["detail"] = detail
    if errors is not None:
        payload["errors"] = errors
    return payload


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = _get_or_create_request_id(request)
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    message = detail if isinstance(detail, str) else "请求失败"
    payload = _build_error_payload(
        request=request,
        status=exc.status_code,
        message=message,
        code=_error_code_for_status(exc.status_code),
        detail=detail if not isinstance(detail, str) else None,
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    payload = _build_error_payload(
        request=request,
        status=422,
        message="请求参数校验失败",
        code="VALIDATION_ERROR",
        errors=exc.errors(),
    )
    return JSONResponse(status_code=422, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = _get_or_create_request_id(request)
    logger.exception("unhandled_exception request_id=%s", request_id, exc_info=exc)
    payload = _build_error_payload(
        request=request,
        status=500,
        message="服务器内部错误",
        code="INTERNAL_SERVER_ERROR",
    )
    return JSONResponse(status_code=500, content=payload)


def _enforce_rate_limit(request: Request, limiter) -> None:
    key = get_client_key(
        forwarded_for=request.headers.get("x-forwarded-for"),
        client_host=request.client.host if request.client else None,
        api_key=request.headers.get("x-api-key"),
    )
    if not limiter.allow(key):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


def _generate_request_id(request: Request) -> str:
    return _get_or_create_request_id(request)


def _resolve_source(
    *,
    source_type: str,
    source_url: str | None,
    file_id: str | None,
    file_hash: str | None,
    persist_file_hash: bool = True,
) -> tuple[str, str | None, str, str | None]:
    """Resolve source_ref, file_hash, cache_key for URL/local inputs."""
    store = get_store()
    source_name: str | None = None

    resolved_file_hash = file_hash
    verified_by_file_id = False
    if source_type == "url":
        if not source_url:
            raise HTTPException(status_code=400, detail="source_type 为 url 时必须提供 source_url")
        source_ref = normalize_url(source_url)
    elif source_type == "local":
        if file_id and not resolved_file_hash:
            try:
                storage = get_file_storage()
                uploaded = storage.get(file_id)
                source_name = uploaded.original_name
                if uploaded.file_hash:
                    resolved_file_hash = uploaded.file_hash
                else:
                    resolved_file_hash = compute_file_hash(str(uploaded.stored_path))
                    if persist_file_hash:
                        store.update_upload_file_hash(file_id, resolved_file_hash)
                    uploaded.file_hash = resolved_file_hash
                verified_by_file_id = True
            except UploadFileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
        if not resolved_file_hash:
            raise HTTPException(status_code=400, detail="source_type 为 local 时必须提供 file_hash 或 file_id")
        if not verified_by_file_id:
            upload_record = store.get_upload_by_hash(resolved_file_hash)
            if not upload_record:
                raise HTTPException(status_code=404, detail="file_hash 不存在或已过期")
            source_name = upload_record.get("original_name")
        source_ref = resolved_file_hash
    else:
        raise HTTPException(status_code=400, detail=f"不支持的 source_type: {source_type}")

    try:
        cache_key = compute_cache_key_from_source(source_type, source_url, resolved_file_hash)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return source_ref, resolved_file_hash, cache_key, source_name


@app.on_event("startup")
def _startup() -> None:
    queue = get_job_queue(worker_count=int(os.getenv("JOB_WORKER_COUNT", "1")))
    queue.start()
    # 启动缓存 GC
    start_gc_background()


@app.on_event("shutdown")
def _shutdown() -> None:
    queue = get_job_queue(worker_count=int(os.getenv("JOB_WORKER_COUNT", "1")))
    queue.stop()


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "ok", "version": VERSION}


# ============ 文件上传 ============


@app.post("/api/uploads", response_model=UploadResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    """上传本地文件

    支持的文件类型：
    - 视频: mp4, mkv, webm, mov, avi, flv, wmv
    - 音频: mp3, wav, flac, aac, m4a, ogg, wma
    - 字幕: srt, vtt, ass, ssa, sub

    上传后返回 file_id，可用于 /api/summaries (source_type=local) 接口。
    文件默认保留 24 小时后自动清理。
    """
    _enforce_rate_limit(request, upload_rate_limiter)
    storage = get_file_storage()

    try:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_val = int(content_length)
                if length_val > storage.max_file_size_bytes + UPLOAD_CONTENT_LENGTH_GRACE_BYTES:
                    raise HTTPException(status_code=413, detail="文件大小超过限制")
            except ValueError:
                pass

        async with UPLOAD_SEMAPHORE:
            uploaded = await storage.save_stream(
                read_chunk=file.read,
                original_name=file.filename or "unknown",
                content_type=file.content_type,
                chunk_size=UPLOAD_CHUNK_SIZE,
                read_timeout=UPLOAD_READ_TIMEOUT_SECONDS,
                write_timeout=UPLOAD_WRITE_TIMEOUT_SECONDS,
            )

        return UploadResponse(
            file_id=uploaded.file_id,
            original_name=uploaded.original_name,
            size=uploaded.size,
            mime_type=uploaded.mime_type,
            file_type=uploaded.file_type,
            file_hash=uploaded.file_hash,
        )

    except FileSizeError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except FileTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except FileTimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))
    finally:
        try:
            await file.close()
        except Exception:
            pass


# ============ 缓存 API ============


@app.post("/api/cache/lookup", response_model=CacheLookupResponse)
def cache_lookup(request: Request, req: CacheLookupRequest):
    """缓存查询

    根据 source_type 和 source_url/file_hash 查询缓存状态。
    - 命中: hit=true, status=completed, 返回 summary_text
    - 处理中: hit=false, status=running/pending, 返回 job_id
    - 失败/未找到: hit=false, status=failed/not_found
    """
    _enforce_rate_limit(request, summary_rate_limiter)
    request_id = _generate_request_id(request)

    _source_ref, resolved_hash, cache_key, _source_name = _resolve_source(
        source_type=req.source_type,
        source_url=req.source_url,
        file_id=req.file_id,
        file_hash=req.file_hash,
        persist_file_hash=False,
    )

    logger.info(
        "cache_lookup start request_id=%s source_type=%s cache_key=%s",
        request_id,
        req.source_type,
        cache_key,
    )

    cache_service = get_cache_service()
    result = cache_service.lookup(
        source_type=req.source_type,
        source_url=req.source_url,
        file_hash=resolved_hash,
        strict=True,
        touch=False,
    )

    logger.info(
        "cache_lookup done request_id=%s cache_key=%s status=%s hit=%s",
        request_id,
        result.cache_key,
        result.status,
        result.hit,
    )

    return CacheLookupResponse(**result.to_dict())


@app.post("/api/summaries", response_model=SummaryResponse, status_code=200)
def create_summary(request: Request, req: SummaryRequest):
    """统一摘要入口（缓存优先）

    流程:
    1. 计算 cache_key
    2. 查询缓存:
       - completed: 直接返回摘要
       - running/pending: 返回 job_id
       - failed/not_found 或 refresh=true: 创建新任务
    """
    _enforce_rate_limit(request, summary_rate_limiter)
    request_id = _generate_request_id(request)

    cache_service = get_cache_service()

    source_ref, resolved_hash, cache_key, source_name = _resolve_source(
        source_type=req.source_type,
        source_url=req.source_url,
        file_id=req.file_id,
        file_hash=req.file_hash,
    )

    logger.info(
        "summary request start request_id=%s source_type=%s cache_key=%s",
        request_id,
        req.source_type,
        cache_key,
    )

    # 查询缓存（非 refresh 模式）
    if not req.refresh:
        result = cache_service.lookup(
            source_type=req.source_type,
            source_url=req.source_url,
            file_hash=resolved_hash,
            strict=True,
            touch=True,
        )

        # 缓存命中
        if result.hit and result.status == "completed":
            logger.info(
                "summary cache hit request_id=%s cache_key=%s",
                request_id,
                cache_key,
            )
            return SummaryResponse(
                status="completed",
                cache_key=cache_key,
                summary_text=result.summary_text,
                source_name=result.source_name,
                created_at=result.created_at,
            )

        # 正在处理中
        if result.status in ("running", "pending"):
            logger.info(
                "summary cache running request_id=%s cache_key=%s job_id=%s",
                request_id,
                cache_key,
                result.job_id,
            )
            return SummaryResponse(
                status=result.status,
                cache_key=cache_key,
                job_id=result.job_id,
                source_name=result.source_name,
                created_at=result.created_at,
            )

    # 创建或更新缓存条目
    entry = cache_service.get_or_create_entry(
        cache_key, req.source_type, source_ref, source_name=source_name
    )

    if req.refresh:
        cache_service.bundle_manager.delete_bundle(cache_key, entry.source_type)
        cache_service.store.update_cache_entry(
            cache_key,
            status="pending",
            summary_text="",
            error="",
        )

    # 创建任务
    job_id = cache_service.create_job(cache_key)

    # 入队执行
    queue = get_job_queue(worker_count=int(os.getenv("JOB_WORKER_COUNT", "1")))
    queue.enqueue(
        CacheJob(
            job_id=job_id,
            cache_key=cache_key,
            source_type=req.source_type,
            source_url=req.source_url,
            file_hash=resolved_hash,
            request_id=request_id,
        )
    )

    # 更新状态为 pending
    cache_service.update_status(cache_key, "pending")

    logger.info(
        "summary job enqueued request_id=%s cache_key=%s job_id=%s",
        request_id,
        cache_key,
        job_id,
    )

    return SummaryResponse(
        status="pending",
        cache_key=cache_key,
        job_id=job_id,
        source_name=source_name,
        created_at=entry.created_at,
    )


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """查询任务状态"""
    cache_service = get_cache_service()
    job = cache_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="job_id 不存在")

    cache_entry = job.get("cache_entry", {})

    return JobStatusResponse(
        job_id=job["job_id"],
        cache_key=job["cache_key"],
        status=job["status"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        error=job.get("error"),
        cache_status=cache_entry.get("status"),
        summary_text=cache_entry.get("summary_text"),
        source_name=cache_entry.get("source_name"),
    )


@app.get("/api/cache/{cache_key}", response_model=CacheEntryResponse)
def get_cache_entry(cache_key: str):
    """获取缓存条目详情"""
    cache_service = get_cache_service()
    entry = cache_service.get_entry(cache_key)

    if not entry:
        raise HTTPException(status_code=404, detail="cache_key 不存在")

    # 更新访问时间
    cache_service.store.touch_cache_entry(cache_key)

    return CacheEntryResponse(
        cache_key=entry.cache_key,
        source_type=entry.source_type,
        source_ref=entry.source_ref,
        source_name=entry.source_name,
        status=entry.status,
        profile_version=entry.profile_version,
        summary_text=entry.summary_text,
        bundle_path=entry.bundle_path,
        error=entry.error,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        last_accessed=entry.last_accessed,
    )


@app.delete("/api/cache/{cache_key}", response_model=CacheDeleteResponse)
def delete_cache_entry(request: Request, cache_key: str):
    """删除缓存条目及其 bundle"""
    _enforce_rate_limit(request, summary_rate_limiter)
    cache_service = get_cache_service()
    deleted = cache_service.delete_entry(cache_key)

    if not deleted:
        raise HTTPException(status_code=404, detail="cache_key 不存在")

    return CacheDeleteResponse(cache_key=cache_key, deleted=True)


def run_server(host: str = "0.0.0.0", port: int = 8765, reload: bool = False) -> None:
    """启动 API 服务器

    Args:
        host: 监听地址
        port: 监听端口
        reload: 是否启用热重载（开发模式）
    """
    import uvicorn

    uvicorn.run("app.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_server()
