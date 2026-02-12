from __future__ import annotations

import uuid
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dependencies import (
    UPLOAD_CHUNK_SIZE,
    UPLOAD_CONTENT_LENGTH_GRACE_BYTES,
    UPLOAD_READ_TIMEOUT_SECONDS,
    UPLOAD_SEMAPHORE,
    UPLOAD_WRITE_TIMEOUT_SECONDS,
    ResolvedSource,
    enforce_summary_rate_limit,
    enforce_upload_rate_limit,
    resolve_cache_lookup_source,
    resolve_summary_source,
    valid_cache_entry,
    valid_cache_key,
    valid_job_id,
)
from app.api.schemas import (
    CacheDeleteResponse,
    CacheEntryResponse,
    CacheLookupRequest,
    CacheLookupResponse,
    ErrorResponse,
    JobStatusResponse,
    SummaryRequest,
    SummaryResponse,
    UploadResponse,
)
from app.api.settings import get_worker_settings
from app.api.uploads import (
    FileSizeError,
    FileTimeoutError,
    FileTypeError,
    get_file_storage,
)
from app.api.worker import CacheJob, get_job_queue
from app.cache import start_gc_background
from app.cache.cache_service import CacheEntry, get_cache_service
from app.core.utils.logger import setup_logger

APP_NAME = "VideoSummary API"
VERSION = "0.2.0"

app = FastAPI(title=APP_NAME, version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

COMMON_ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_408_REQUEST_TIMEOUT: {"model": ErrorResponse},
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"model": ErrorResponse},
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
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
    status_code: int,
    message: str,
    code: str,
    detail: Any = None,
    errors: Any = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message": message,
        "code": code,
        "status": status_code,
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
        status_code=exc.status_code,
        message=message,
        code=_error_code_for_status(exc.status_code),
        detail=detail if not isinstance(detail, str) else None,
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    payload = _build_error_payload(
        request=request,
        status_code=422,
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
        status_code=500,
        message="服务器内部错误",
        code="INTERNAL_SERVER_ERROR",
    )
    return JSONResponse(status_code=500, content=payload)


@app.on_event("startup")
def _startup() -> None:
    queue = get_job_queue(worker_count=get_worker_settings().worker_count)
    queue.start()
    start_gc_background()


@app.on_event("shutdown")
def _shutdown() -> None:
    queue = get_job_queue(worker_count=get_worker_settings().worker_count)
    queue.stop()


@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    description="Service health endpoint.",
)
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}


@app.post(
    "/api/uploads",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Uploads"],
    summary="Upload a local file",
    description="Upload a local video/audio/subtitle file and return a file_id.",
    responses=COMMON_ERROR_RESPONSES,
)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    _rate_limit: None = Depends(enforce_upload_rate_limit),
):
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
    except FileSizeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except FileTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except FileTimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc
    finally:
        try:
            await file.close()
        except Exception:
            pass


@app.post(
    "/api/cache/lookup",
    response_model=CacheLookupResponse,
    tags=["Cache"],
    summary="Lookup cache by source",
    description="Lookup cache state by URL or local file identity.",
    responses=COMMON_ERROR_RESPONSES,
)
def cache_lookup(
    request: Request,
    req: CacheLookupRequest,
    source: ResolvedSource = Depends(resolve_cache_lookup_source),
    _rate_limit: None = Depends(enforce_summary_rate_limit),
):
    request_id = _get_or_create_request_id(request)
    logger.info(
        "cache_lookup start request_id=%s source_type=%s cache_key=%s",
        request_id,
        req.source_type.value,
        source.cache_key,
    )

    cache_service = get_cache_service()
    result = cache_service.lookup(
        source_type=source.source_type,
        source_url=source.source_url,
        file_hash=source.file_hash,
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
    return CacheLookupResponse.model_validate(result.to_dict())


@app.post(
    "/api/summaries",
    response_model=SummaryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Summary"],
    summary="Create summary job (cache first)",
    description="Return cached summary or enqueue a new summary job.",
    responses={
        **COMMON_ERROR_RESPONSES,
        status.HTTP_200_OK: {"model": SummaryResponse},
        status.HTTP_202_ACCEPTED: {"model": SummaryResponse},
    },
)
def create_summary(
    request: Request,
    response: Response,
    req: SummaryRequest,
    source: ResolvedSource = Depends(resolve_summary_source),
    _rate_limit: None = Depends(enforce_summary_rate_limit),
):
    request_id = _get_or_create_request_id(request)
    cache_service = get_cache_service()

    logger.info(
        "summary request start request_id=%s source_type=%s cache_key=%s",
        request_id,
        req.source_type.value,
        source.cache_key,
    )

    if not req.refresh:
        result = cache_service.lookup(
            source_type=source.source_type,
            source_url=source.source_url,
            file_hash=source.file_hash,
            strict=True,
            touch=True,
        )

        if result.hit and result.status == "completed":
            response.status_code = status.HTTP_200_OK
            logger.info("summary cache hit request_id=%s cache_key=%s", request_id, source.cache_key)
            return SummaryResponse(
                status=result.status,
                cache_key=source.cache_key,
                summary_text=result.summary_text,
                source_name=result.source_name,
                created_at=result.created_at,
            )

        if result.status in ("running", "pending"):
            response.status_code = status.HTTP_202_ACCEPTED
            logger.info(
                "summary cache running request_id=%s cache_key=%s job_id=%s",
                request_id,
                source.cache_key,
                result.job_id,
            )
            return SummaryResponse(
                status=result.status,
                cache_key=source.cache_key,
                job_id=result.job_id,
                source_name=result.source_name,
                created_at=result.created_at,
            )

    entry = cache_service.get_or_create_entry(
        source.cache_key,
        source.source_type,
        source.source_ref,
        source_name=source.source_name,
    )
    if req.refresh:
        cache_service.bundle_manager.delete_bundle(source.cache_key, entry.source_type)
        cache_service.store.update_cache_entry(
            source.cache_key,
            status="pending",
            summary_text="",
            error="",
        )

    job_id = cache_service.create_job(source.cache_key)
    queue = get_job_queue(worker_count=get_worker_settings().worker_count)
    queue.enqueue(
        CacheJob(
            job_id=job_id,
            cache_key=source.cache_key,
            source_type=req.source_type.value,
            source_url=str(req.source_url) if req.source_url is not None else None,
            file_hash=source.file_hash,
            request_id=request_id,
        )
    )
    cache_service.update_status(source.cache_key, "pending")

    response.status_code = status.HTTP_202_ACCEPTED
    logger.info(
        "summary job enqueued request_id=%s cache_key=%s job_id=%s",
        request_id,
        source.cache_key,
        job_id,
    )
    return SummaryResponse(
        status="pending",
        cache_key=source.cache_key,
        job_id=job_id,
        source_name=source.source_name,
        created_at=entry.created_at,
    )


@app.get(
    "/api/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["Jobs"],
    summary="Get job status",
    description="Query a summary job status by job_id.",
    responses=COMMON_ERROR_RESPONSES,
)
def get_job_status(job: dict[str, Any] = Depends(valid_job_id)):
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


@app.get(
    "/api/cache/{cache_key}",
    response_model=CacheEntryResponse,
    tags=["Cache"],
    summary="Get cache entry",
    description="Get full cache entry detail by cache_key.",
    responses=COMMON_ERROR_RESPONSES,
)
def get_cache_entry(entry: CacheEntry = Depends(valid_cache_entry)):
    cache_service = get_cache_service()
    cache_service.store.touch_cache_entry(entry.cache_key)
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


@app.delete(
    "/api/cache/{cache_key}",
    response_model=CacheDeleteResponse,
    tags=["Cache"],
    summary="Delete cache entry",
    description="Delete cache entry and bundle by cache_key.",
    responses=COMMON_ERROR_RESPONSES,
)
def delete_cache_entry(
    cache_key: str = Depends(valid_cache_key),
    _rate_limit: None = Depends(enforce_summary_rate_limit),
):
    cache_service = get_cache_service()
    deleted = cache_service.delete_entry(cache_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="cache_key 不存在")
    return CacheDeleteResponse(cache_key=cache_key, deleted=True)


def run_server(host: str = "0.0.0.0", port: int = 8765, reload: bool = False) -> None:
    import uvicorn

    uvicorn.run("app.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_server()
