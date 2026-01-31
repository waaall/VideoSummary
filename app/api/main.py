from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.auto_pipeline import build_local_auto_pipeline, build_url_auto_pipeline
from app.api.schemas import (
    AutoPipelineRunRequest,
    PipelineInputs,
    PipelineRunRequest,
    PipelineRunResponse,
)
from app.pipeline.context import PipelineContext
from app.pipeline.graph import PipelineGraph, CyclicDependencyError, InvalidGraphError
from app.pipeline.runner import PipelineRunner, PipelineExecutionError
from app.pipeline.registry import get_default_registry, NodeNotFoundError

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


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "ok", "version": VERSION}


def _run_pipeline(
    inputs: PipelineInputs,
    pipeline,
    thresholds=None,
) -> PipelineRunResponse:
    try:
        # 构建 DAG 图
        graph = PipelineGraph(pipeline)
    except CyclicDependencyError as e:
        raise HTTPException(status_code=400, detail=f"循环依赖: {e}")
    except InvalidGraphError as e:
        raise HTTPException(status_code=400, detail=f"图结构无效: {e}")

    try:
        # 创建执行上下文
        ctx = PipelineContext.from_inputs(inputs, thresholds)

        # 创建执行器并运行
        registry = get_default_registry()
        runner = PipelineRunner(graph, registry)
        ctx = runner.run(ctx)

        # 确定最终状态
        failed_nodes = [t for t in ctx.trace if t.status == "failed"]
        final_status = "failed" if failed_nodes else "completed"

        return PipelineRunResponse(
            run_id=ctx.run_id,
            status=final_status,
            summary_text=ctx.summary_text,
            context=ctx.to_dict(),
            trace=ctx.trace,
        )

    except NodeNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"节点类型未注册: {e}")
    except PipelineExecutionError:
        # 执行失败但仍返回部分结果
        return PipelineRunResponse(
            run_id=ctx.run_id,
            status="failed",
            summary_text=ctx.summary_text,
            context=ctx.to_dict(),
            trace=ctx.trace,
        )


@app.post("/pipeline/run", response_model=PipelineRunResponse)
def pipeline_run(req: PipelineRunRequest):
    """运行管道

    接收 DAG 配置和输入参数，执行管线并返回结果。
    """
    return _run_pipeline(req.inputs, req.pipeline, req.thresholds)


@app.post("/pipeline/auto/url", response_model=PipelineRunResponse)
def pipeline_auto_url(req: AutoPipelineRunRequest):
    """URL 自动流程（字幕优先）"""
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
    return _run_pipeline(inputs, pipeline, req.thresholds)


@app.post("/pipeline/auto/local", response_model=PipelineRunResponse)
def pipeline_auto_local(req: AutoPipelineRunRequest):
    """本地自动流程（字幕/音频/视频）"""
    if req.inputs.source_type and req.inputs.source_type != "local":
        raise HTTPException(
            status_code=400, detail="本地自动流程仅支持 source_type=local"
        )

    inputs = PipelineInputs(
        source_type="local",
        source_url=req.inputs.source_url,
        video_path=req.inputs.video_path,
        subtitle_path=req.inputs.subtitle_path,
        audio_path=req.inputs.audio_path,
        extra=req.inputs.extra,
    )
    pipeline = build_local_auto_pipeline(req.options)
    return _run_pipeline(inputs, pipeline, req.thresholds)


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
