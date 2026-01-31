from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.api.auto_pipeline import build_local_auto_pipeline, build_url_auto_pipeline
from app.api.schemas import (
    AutoPipelineRunRequest,
    LocalPipelineRunRequest,
    PipelineInputs,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineRunCreateResponse,
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
    pipeline_rate_limiter,
    upload_rate_limiter,
)
from app.api.worker import PipelineJob, generate_run_id, get_job_queue

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


def _model_to_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _enforce_rate_limit(request: Request, limiter) -> None:
    key = get_client_key(
        forwarded_for=request.headers.get("x-forwarded-for"),
        client_host=request.client.host if request.client else None,
        api_key=request.headers.get("x-api-key"),
    )
    if not limiter.allow(key):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


def _enqueue_pipeline(
    *,
    pipeline,
    inputs,
    thresholds,
    options,
) -> PipelineRunCreateResponse:
    run_id = generate_run_id()
    store = get_store()
    store.create_run(
        run_id,
        "queued",
        pipeline=_model_to_dict(pipeline),
        inputs=_model_to_dict(inputs),
        thresholds=_model_to_dict(thresholds) if thresholds is not None else None,
        options=options or {},
    )
    queue = get_job_queue(worker_count=int(os.getenv("PIPELINE_WORKER_COUNT", "1")))
    queue.enqueue(
        PipelineJob(
            run_id=run_id,
            pipeline=pipeline,
            inputs=inputs,
            thresholds=thresholds,
            options=options or {},
        )
    )
    return PipelineRunCreateResponse(run_id=run_id, status="queued", queued_at=time.time())


@app.on_event("startup")
def _startup() -> None:
    queue = get_job_queue(worker_count=int(os.getenv("PIPELINE_WORKER_COUNT", "1")))
    queue.start()


@app.on_event("shutdown")
def _shutdown() -> None:
    queue = get_job_queue(worker_count=int(os.getenv("PIPELINE_WORKER_COUNT", "1")))
    queue.stop()


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "ok", "version": VERSION}


# ============ 文件上传 ============


@app.post("/uploads", response_model=UploadResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    """上传本地文件

    支持的文件类型：
    - 视频: mp4, mkv, webm, mov, avi, flv, wmv
    - 音频: mp3, wav, flac, aac, m4a, ogg, wma
    - 字幕: srt, vtt, ass, ssa, sub

    上传后返回 file_id，可用于 /pipeline/auto/local 接口。
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

@app.post("/pipeline/run", response_model=PipelineRunCreateResponse, status_code=202)
def pipeline_run(request: Request, req: PipelineRunRequest):
    """运行管道

    接收 DAG 配置和输入参数，执行管线并返回结果。
    """
    _enforce_rate_limit(request, pipeline_rate_limiter)
    return _enqueue_pipeline(
        pipeline=req.pipeline,
        inputs=req.inputs,
        thresholds=req.thresholds,
        options=req.options,
    )


@app.post("/pipeline/auto/url", response_model=PipelineRunCreateResponse, status_code=202)
def pipeline_auto_url(request: Request, req: AutoPipelineRunRequest):
    """URL 自动流程（字幕优先）"""
    _enforce_rate_limit(request, pipeline_rate_limiter)
    if req.inputs.source_type and req.inputs.source_type != "url":
        raise HTTPException(status_code=400, detail="URL 自动流程仅支持 source_type=url")

    inputs = PipelineInputs(
        source_type="url",
        source_url=req.inputs.source_url,
        video_path=req.inputs.video_path,
        subtitle_path=req.inputs.subtitle_path,
        audio_path=req.inputs.audio_path,
        extra=req.inputs.extra,
    )
    pipeline = build_url_auto_pipeline(req.options)
    return _enqueue_pipeline(
        pipeline=pipeline,
        inputs=inputs,
        thresholds=req.thresholds,
        options=req.options,
    )


@app.post("/pipeline/auto/local", response_model=PipelineRunCreateResponse, status_code=202)
def pipeline_auto_local(request: Request, req: LocalPipelineRunRequest):
    """本地自动流程（字幕/音频/视频）

    支持两种输入方式：
    1. file_id 方式（推荐）：先通过 POST /uploads 上传文件，获得 file_id 后传入
    2. path 方式：直接传入服务端本地路径（仅内部调试用）

    如果同时提供 file_id 和 path，优先使用 file_id。
    """
    _enforce_rate_limit(request, pipeline_rate_limiter)
    # 解析 file_id 为实际路径
    video_path = req.inputs.video_path
    audio_path = req.inputs.audio_path
    subtitle_path = req.inputs.subtitle_path

    try:
        storage = get_file_storage()
        resolved = storage.resolve_file_ids(
            video_file_id=req.inputs.video_file_id,
            audio_file_id=req.inputs.audio_file_id,
            subtitle_file_id=req.inputs.subtitle_file_id,
        )

        # file_id 优先于 path
        if resolved["video_path"]:
            video_path = resolved["video_path"]
        if resolved["audio_path"]:
            audio_path = resolved["audio_path"]
        if resolved["subtitle_path"]:
            subtitle_path = resolved["subtitle_path"]

    except UploadFileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileTypeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    inputs = PipelineInputs(
        source_type="local",
        source_url=None,
        video_path=video_path,
        subtitle_path=subtitle_path,
        audio_path=audio_path,
        extra=req.inputs.extra,
    )
    pipeline = build_local_auto_pipeline(req.options)
    return _enqueue_pipeline(
        pipeline=pipeline,
        inputs=inputs,
        thresholds=req.thresholds,
        options=req.options,
    )


@app.get("/pipeline/run/{run_id}", response_model=PipelineRunResponse)
def pipeline_run_status(run_id: str):
    """查询运行状态"""
    store = get_store()
    record = store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="run_id 不存在")

    nodes = store.list_run_nodes(run_id)
    trace = []
    for node in nodes:
        trace.append(
            {
                "node_id": node["node_id"],
                "status": node["status"],
                "elapsed_ms": node.get("elapsed_ms"),
                "error": node.get("error"),
                "output_keys": node.get("output_keys"),
                "started_at": node.get("started_at"),
                "ended_at": node.get("ended_at"),
                "retryable": node.get("retryable"),
            }
        )

    return PipelineRunResponse(
        run_id=record["run_id"],
        status=record["status"],
        summary_text=record.get("summary_text"),
        context=record.get("context") or {},
        trace=trace,
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
        started_at=record.get("started_at"),
        ended_at=record.get("ended_at"),
        error=record.get("error"),
    )


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
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
