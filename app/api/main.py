from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.schemas import PipelineRunRequest, PipelineRunResponse

APP_NAME = "VideoCaptioner API"
VERSION = "0.1.0"

app = FastAPI(title=APP_NAME, version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "ok", "version": VERSION}


@app.post("/pipeline/run", response_model=PipelineRunResponse)
def pipeline_run(req: PipelineRunRequest):
    """运行管道（尚未实现）"""
    raise HTTPException(status_code=501, detail="Pipeline runner not implemented yet")


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
