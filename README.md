# VideoSummary

AI 驱动的视频字幕生成与摘要应用，由 FastAPI 后端引擎与 React 前端界面组成。

## 功能特性

- ASR 语音转写（支持多种后端：Whisper, FasterWhisper, 剪映等）
- 字幕解析与验证
- 基于 LLM 的文本摘要
- 缓存优先的固定流水线（URL / 本地文件）
- Web 前端：URL / 本地文件提交、任务轮询、历史记录、结果复制与导出

## 仓库结构

本仓库为前后端一体的 monorepo：

```
VideoSummary/
├── app/                  # 后端：FastAPI 服务、流水线、ASR/LLM 核心、缓存
├── web/                  # 前端：React + TypeScript + Vite 应用
├── resource/             # 后端运行所需资源（打包进镜像）
├── docs/                 # 后端开发文档
├── tests/                # 后端测试
├── Dockerfile            # 后端容器镜像构建文件
└── docker-compose.yml    # 后端容器编排
```

- 后端说明见下文「后端」章节。
- 前端说明见下文「前端」章节，完整文档见 [web/FRONTEND_README.md](web/FRONTEND_README.md)。

---

# 后端

VideoSummary 后端采用分层架构设计，旨在实现高效、异步的视频处理和摘要生成。

## 架构与工作流

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

> 说明：Docker 部署仅包含后端服务。前端需单独构建并由 nginx 托管，详见「前端」章节。

### 1. 准备网络与配置

后端容器通过 Docker 网络 `llm-net` 按容器别名访问 Whisper / vLLM 服务（与二者同处一台宿主机时无需固定 IP）。该网络通常已由 Whisper / vLLM 的 compose 创建，若不存在则手动创建：

```bash
docker network create llm-net
```

LLM 与 Whisper 的连接地址在 `AppData/settings.json` 中配置（通过卷挂载持久化，修改后重启容器生效）：

- `llm.base_url` / `llm.model` / `llm.api_key`：LLM 服务；本地 vLLM 无鉴权时 `api_key` 填任意非空值（如 `EMPTY`）
- `whisper_service.base_url`：Whisper 服务地址
- `transcribe.model` 设为 `Whisper Service` 以启用该转录后端

与 Whisper / vLLM 同主机时，直接用容器别名即可：

```json
"llm":             { "base_url": "http://vllm:8000/v1", "model": "Qwen3.6-35B-A3B-FP8", "api_key": "EMPTY" },
"whisper_service": { "base_url": "http://whisper-asr:9000" }
```

可选：`docker compose` 会读取根目录 `.env`，可设置 `JOB_WORKER_COUNT` / `UPLOAD_*` / `RATE_LIMIT_*` 等运行参数。`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 若显式设置会覆盖 `settings.json` 中对应项（留空则以 JSON 为准）。

说明：如果 LLM 或 Whisper 地址未配置，容器仍可启动并通过 `/health` 检查，但实际发起摘要任务时会失败。

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

后端数据按读写特征分两类挂载，便于把大文件单独放到机械盘：

- `./AppData` → `/app/AppData`：运行配置、日志、SQLite 数据库（`metadata.db`）。文件小、需快速随机读写，建议与代码同处固态盘。
- 大块数据目录 → `/app/work-dir`：视频、上传文件、处理缓存、bundle 产物、本地 ASR 模型等。文件大，建议放机械盘——宿主机目录直接写在 `docker-compose.yml` 的卷映射里（默认 `/mnt/hdd/agent_resources/videosummary_cache`），换盘时改那一行即可。
- `resource/`：已打包进镜像，不再通过 `docker-compose.yml` 挂载；修改后需要重新构建镜像。

> 原生部署（非 Docker）：在 `AppData/settings.json` 的 `storage.data_root` 填大块数据目录的绝对路径，留空则用项目内 `work-dir`。

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

# 前端

前端是一个 React 应用，为视频内容自动生成摘要：支持 URL 与本地文件两种输入，缓存优先并以异步 Job 轮询获取结果。

**技术栈**: React 19 + TypeScript + Vite 7 + Ant Design 6 + Zustand。

### 环境要求

- Node.js >= 18.0.0
- npm >= 9.0.0
- 后端服务已运行（默认 `http://localhost:8765`）

### 快速开始

```bash
cd web

# 安装依赖
npm install

# 启动开发服务器（默认 http://localhost:3000）
npm run dev
```

### 生产构建

```bash
cd web
npm run build      # 产物输出到 web/dist
```

构建产物为静态文件，由 nginx 托管并反向代理 `/api/*` 到后端服务。

环境变量、Portal 双模式（standalone / portal）、子路径部署、nginx 配置、页面路由等完整说明见 [web/FRONTEND_README.md](web/FRONTEND_README.md)。

---

# 后端服务测试指南

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
