# VideoSummary

AI 驱动的视频字幕生成和摘要后端引擎。

## 功能特性

- ASR 语音转写（支持多种后端：Whisper, FasterWhisper, 剪映等）
- 字幕解析与验证
- 基于 LLM 的文本摘要
- 缓存优先的固定流水线（URL / 本地文件）

## 架构与工作流

VideoSummary 采用分层架构设计，旨在实现高效、异步的视频处理和摘要生成。

### 架构

- **API 层 (`app/api`)**: 基于 FastAPI 构建，处理请求、任务队列和缓存编排。
- **流水线层 (`app/pipeline`)**: 灵活的基于节点的系统，每个处理步骤（如下载、转写、摘要）都是一个 `PipelineNode`。节点通过 `PipelineContext` 共享状态。
- **核心层 (`app/core`)**: 实现具体能力：
  - **ASR**: 转写（Whisper, 剪映等）
  - **LLM**: 摘要和优化（OpenAI, DeepSeek 等）
  - **媒体**: 用于音视频处理的 FFmpeg 封装。
- **缓存层 (`app/cache`)**: 强大的缓存系统，存储结果和中间产物，确保对重复请求的即时响应。

### 工作流

1.  **请求**: 用户提交视频 URL 或文件。
2.  **缓存查询**: 系统检查结果是否存在。
3.  **任务执行**: 如果未缓存，后台 worker 执行流水线：
    - **下载**: 获取视频/音频内容。
    - **转写 (ASR)**: 将音频转换为文本（如果存在字幕则跳过）。
    - **处理**: 分割、优化和格式化脚本。
    - **摘要**: LLM 生成摘要。
4.  **完成**: 结果被缓存并返回。

## 快速开始

```bash
# 安装依赖
uv sync

# 启动 API 服务
uvicorn app.api.main:app --reload --port 8765
```

### LLM 环境变量加载

服务进程不会自动读取 `tests/.env`，需要显式加载：

```bash
# 方式1：启动时加载 env 文件
uvicorn app.api.main:app --reload --port 8765 --env-file tests/.env
```

或：

```bash
# 方式2：先导出再启动
set -a
source tests/.env
set +a
uvicorn app.api.main:app --reload --port 8765
```

## Docker 部署

### 1. 准备环境变量

`docker compose` 会读取项目根目录下的 `.env` 文件，也可以直接在当前 shell 中导出环境变量。至少建议配置以下变量：

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`

示例 `.env`：

```bash
LLM_BASE_URL=https://your-llm-endpoint/v1
LLM_API_KEY=your_api_key
LLM_MODEL=gpt-4o-mini
JOB_WORKER_COUNT=1
UPLOAD_CONCURRENCY=2
UPLOAD_RATE_LIMIT_PER_MINUTE=30
SUMMARY_RATE_LIMIT_PER_MINUTE=60
```

说明：如果 `LLM_BASE_URL` 或 `LLM_API_KEY` 为空，容器仍然可以启动并通过 `/health` 检查，但实际发起摘要任务时会失败。

### 2. 构建并后台启动

```bash
docker compose up --build -d
```

首次构建会拉取基础镜像并安装系统依赖、Python 依赖，耗时会明显长一些。

### 3. 查看服务状态

```bash
docker compose ps
docker compose logs -f videosummary-api
```

默认监听端口为 `8765`。

### 4. 健康检查

```bash
curl -s http://127.0.0.1:8765/health | python -m json.tool
```

### 5. 停止服务

```bash
docker compose down
```

### 6. 更新后重新构建

代码或 `resource/` 目录内容变更后，重新执行：

```bash
docker compose up --build -d
```

### 7. 数据目录说明

- `./AppData`：持久化日志、缓存、模型和运行配置。
- `./work-dir`：持久化任务处理过程中的工作目录。
- `resource/`：已打包进镜像，不再通过 `docker-compose.yml` 挂载；修改后需要重新构建镜像。

## API 端点

- `GET /health` - 健康检查
- `POST /api/uploads` - 上传本地文件
- `POST /api/cache/lookup` - 缓存查询（只读）
- `POST /api/summaries` - 创建/查询摘要（缓存优先）
- `GET /api/jobs/{job_id}` - 任务状态
- `GET /api/cache/{cache_key}` - 缓存条目详情
- `DELETE /api/cache/{cache_key}` - 删除缓存条目

说明：缓存相关响应会包含 `source_name` 字段（URL 标题或本地文件名）。

---

# Summary 服务测试指南

## 服务管理

### 启动服务

```bash
uvicorn app.api.main:app --reload --port 8765
```

### 关闭服务

```bash
pkill -f "uvicorn app.api.main:app"
```

### 重启服务

```bash
pkill -f "uvicorn app.api.main:app" || true
sleep 1
uvicorn app.api.main:app --reload --port 8765
```

## 测试用例

### 1. 健康检查

```bash
curl -s http://127.0.0.1:8765/health | python -m json.tool
```

### 2. URL 摘要（缓存优先）

```bash
curl -s -X POST http://127.0.0.1:8765/api/summaries   -H "Content-Type: application/json"   -d '{
    "source_type": "url",
    "source_url": "https://www.bilibili.com/video/BV1iApwzBEqZ/"
  }' | python -m json.tool
```

### 3. 任务状态查询

```bash
curl -s http://127.0.0.1:8765/api/jobs/<job_id> | python -m json.tool
```

### 4. 本地文件摘要

```bash
# 先上传文件
curl -s -X POST http://127.0.0.1:8765/api/uploads   -F "file=@/path/to/example.srt" | python -m json.tool

# 再创建摘要
curl -s -X POST http://127.0.0.1:8765/api/summaries   -H "Content-Type: application/json"   -d '{
    "source_type": "local",
    "file_id": "f_xxx"
  }' | python -m json.tool
```

### 5. 删除缓存

```bash
curl -s -X DELETE http://127.0.0.1:8765/api/cache/<cache_key> | python -m json.tool
```
