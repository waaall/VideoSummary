# VideoSummary Frontend

智能视频摘要生成前端应用，支持 URL 与本地文件输入，缓存优先并以异步 Job 轮询获取结果。

## 概述

VideoSummary Frontend 是一个 React 前端应用，为视频内容自动生成摘要。支持通过 URL 或本地上传两种方式处理视频；提交后若缓存命中直接返回摘要，否则创建 Job 并轮询 `/api/jobs/{job_id}` 获取状态与结果。历史任务页可查看任务进度、缓存信息与摘要内容。

**当前版本**: 0.1.0 (Beta 1)

**技术栈**:
- React (>19.2) + TypeScript + Vite 7
- Ant Design 6 组件库
- Zustand 状态管理
- Axios HTTP 客户端

## 功能特性

- **URL 处理流程**: 输入视频 URL，创建摘要任务（缓存优先）
- **本地上传流程**: 上传字幕/音频/视频文件生成摘要
- **任务状态轮询**: pending/running/completed/failed
- **执行监控详情**: 查看任务进度、缓存信息与摘要结果
- **结果操作**: 复制摘要、导出 Markdown
- **缓存删除**: 删除记录时先请求后端删除缓存，成功后再移除本地历史
- **设置持久化**: API 地址、Bearer Token、轮询间隔、请求超时、上传限制
- **深色/浅色主题**: 支持系统跟随

## 快速开始

### 环境要求

- Node.js >= 18.0.0
- npm >= 9.0.0
- 后端服务运行在 `http://localhost:8765`

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd VideoSummaryFrontend

# 进入前端目录
cd web

# 安装依赖
npm install
```

### 配置

推荐直接使用按模式拆分的环境文件：

- `web/.env.development`：开发配置（默认 `standalone`）
- `web/.env.production`：生产配置（固定 `portal`：`/apps/video`）

可配置项：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VITE_BASE_PATH` | `/` | Vite 构建资源前缀（子路径部署） |
| `VITE_ROUTER_BASENAME` | `/` | React Router basename |
| `VITE_EMBEDDED` | `false` | 是否作为 Portal iframe 子应用 |
| `VITE_STORAGE_NS` | `video` | localStorage 命名空间前缀 |
| `VITE_COOKIE_PATH` | `/` | Cookie Path 隔离 |
| `VITE_API_BASE_URL` | 开发 `http://localhost:8765` / 生产 `/apps/video` | API 基础地址（最终请求 = `baseUrl + /api/*`） |
| `VITE_API_AUTH_TOKEN` | `` | 可选 Bearer Token |
| `VITE_API_TIMEOUT` | `300000` | 请求超时 (ms) |
| `VITE_POLLING_INTERVAL` | `2000` | 轮询间隔 (ms) |
| `VITE_MAX_FILE_SIZE` | `524288000` | 最大上传文件大小 (500MB) |

常见模式配置：

| 模式 | `VITE_BASE_PATH` | `VITE_ROUTER_BASENAME` | `VITE_EMBEDDED` | `VITE_STORAGE_NS` | `VITE_COOKIE_PATH` |
|------|------------------|------------------------|-----------------|-------------------|--------------------|
| standalone | `/` | `/` | `false` | `video` | `/` |
| portal | `/apps/video/` | `/apps/video` | `true` | `video` | `/apps/video/` |

### 运行

```bash
# 开发模式
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview

# 代码检查
npm run lint
```

开发服务器默认运行在 `http://localhost:3000`。

## nginx

`nginx.conf` 配置文件如下：

```nginx
worker_processes  1;

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    charset utf-8;

    sendfile        on;
    keepalive_timeout  65;
    client_max_body_size 600m;

    gzip on;
    gzip_min_length 1k;
    gzip_types
        text/plain
        text/css
        text/javascript
        application/javascript
        application/json
        application/xml
        image/svg+xml;

    access_log  logs/access.log;
    error_log   logs/error.log warn;

    server {
        listen       5678;
        server_name  _;

        root   D:\dev_software\apps\zx_code\video-summary\frontend;
        index  index.html;

        location = / {
            return 302 /apps/video/;
        }

        location /apps/video/api/ {
            proxy_pass http://127.0.0.1:8765/api/;
            proxy_http_version 1.1;

            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_connect_timeout 60s;
            proxy_send_timeout 600s;
            proxy_read_timeout 600s;
            proxy_request_buffering off;
        }

        location /apps/video/assets/ {
            expires 7d;
            add_header Cache-Control "public, max-age=604800, immutable";
            try_files $uri =404;
        }

        location /apps/video/ {
            try_files $uri $uri/ /apps/video/index.html;
        }

        error_page   500 502 503 504  /50x.html;
        location = /50x.html {
            root   html;
        }
    }
}
```

windows 测试的运行指令如下：
```powershell
Start-Process -FilePath "D:\dev_software\apps\nginx\nginx.exe" -ArgumentList '-p D:\dev_software\apps\nginx\' -WorkingDirectory 'D:\dev_software\apps\nginx'
Stop-Process -Name nginx -Force
```


## 项目结构

```
web/
├── index.html                    # Vite HTML 入口（包含 #root 和主题预初始化脚本）
├── src/
│   ├── api/                      # API 通信层
│   │   ├── client.ts             # Axios 实例配置
│   │   ├── summaries.ts          # 摘要/任务/缓存 API
│   │   └── upload.ts             # 文件上传 API
│   │
│   ├── stores/                   # Zustand 状态管理
│   │   ├── summaryJobStore.ts    # 任务状态
│   │   ├── historyStore.ts       # 历史记录
│   │   └── settingsStore.ts      # 用户设置 (持久化)
│   │
│   ├── features/                 # 功能模块
│   │   ├── QuickStart/           # 快速开始 (URL/本地流程)
│   │   ├── History/              # 历史任务 (结果查看)
│   │   └── Settings/             # 设置页面
│   │
│   ├── components/               # 通用组件
│   │   ├── Layout/               # 布局组件
│   │   └── common/               # 公共组件
│   │
│   ├── hooks/                    # 自定义 Hooks
│   │   ├── useSummaryJob.ts
│   │   └── usePolling.ts
│   │
│   ├── types/                    # TypeScript 类型定义
│   │   ├── history.ts
│   │   ├── summary.ts
│   │   └── upload.ts
│   ├── config/                   # 配置文件
│   ├── utils/                    # 工具函数
│   └── styles/                   # 全局样式
│
├── package.json
├── vite.config.ts
└── tsconfig.json
```

### 入口说明

- `web/index.html` 是该项目的前端入口 HTML（并非 CRA 的 `public/index.html` 结构）。
- React 在 `web/src/main.tsx` 中通过 `createRoot(#root)` 挂载到 `index.html`。
- 主题初始化脚本读取 `localStorage` 的 `${VITE_STORAGE_NS}:video-summary-settings`；其中 `VITE_STORAGE_NS` 由 `web/vite.config.ts` 在构建时注入，默认值为 `video`。

## 页面路由

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | QuickStartPage | 快速开始，URL/本地上传入口 |
| `/history` | HistoryPage | 历史任务列表 |
| `/history/:jobId` | HistoryPage | 任务详情 |
| `/settings` | SettingsPage | 应用设置 |

## API 接口

前端与后端通过 RESTful API 通信，主要接口：

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/uploads` | 文件上传 |
| `POST` | `/api/summaries` | 创建摘要（缓存优先） |
| `GET` | `/api/jobs/{job_id}` | 查询任务状态 |
| `POST` | `/api/cache/lookup` | 缓存预查（可选） |
| `GET` | `/api/cache/{cache_key}` | 缓存详情 |
| `DELETE` | `/api/cache/{cache_key}` | 删除缓存 |

关键契约约束：

- `source_type=url`：必须提供 `source_url`，且不能提供 `file_id/file_hash`
- `source_type=local`：`file_id` 与 `file_hash` 必须且只能提供一个
- `file_id/job_id/cache_key/file_hash` 均为固定格式字符串，前端会先做格式校验

关键响应语义：

- `POST /api/uploads` 成功响应包含 `file_hash`
- `POST /api/cache/lookup` 返回 `hit:boolean` 与 `status: completed|running|pending|failed|not_found`
- `POST /api/summaries`：
  - `HTTP 200` 仅对应 `status=completed`
  - `HTTP 202` 仅对应 `status=pending|running`，前端需保存 `job_id` 并轮询
- 轮询 `/api/jobs/{job_id}` 在 `status=completed|failed` 时停止

详细 API 文档见 [docs/api/api.md](docs/api/api.md)。

## 状态管理

### SummaryJobStore

管理摘要任务状态：

```typescript
interface SummaryJobState {
  jobId: string | null;
  status: 'idle' | 'pending' | 'running' | 'completed' | 'failed';
  cacheKey: string | null;
  cacheStatus: string | null;
  summaryText: string | null;
  error: string | null;
  createdAt: number | null;
  updatedAt: number | null;
}
```

### 历史记录行为

- `job_id` 表示一次“尝试/执行”，**不是**缓存身份。
- `cache_key` 表示缓存结果身份，**同一输入会复用同一个 `cache_key`**。
- 若任务失败后重新提交，后端可能返回**新的 `job_id` + 相同 `cache_key`**。
- 历史列表以 `cache_key` 作为去重依据，仅保留最新一次尝试记录（时间更新较新的记录覆盖旧记录）。
- 删除历史记录时，会先调用 `DELETE /api/cache/{cache_key}`，成功后再移除本地持久化。

### SettingsStore

管理用户设置（持久化到 localStorage）：

```typescript
interface SettingsState {
  themeMode: 'light' | 'dark' | 'system';
  apiBaseUrl: string;
  authToken: string;
  pollingInterval: number;
  requestTimeout: number;
  uploadMaxFileSizeMb: number;
}
```

## 支持的文件格式

| 类型 | 格式 |
|------|------|
| 视频 | mp4, mkv, avi, mov, webm, flv |
| 音频 | mp3, wav, m4a, aac, flac, ogg |
| 字幕 | srt, ass, vtt, ssa |

上传限制：单文件最大 500MB（可配置）。

## 开发指南

### 代码规范

- 使用 TypeScript 严格模式
- 遵循 ESLint 规则
- 组件使用函数式组件 + Hooks
- 状态管理使用 Zustand selector 避免不必要渲染

### 添加新功能模块

1. 在 `src/features/` 下创建模块目录
2. 创建页面组件和子组件
3. 在 `src/App.tsx` 添加路由
4. 如需全局状态，在 `src/stores/` 添加 store

### 类型定义

- 摘要/任务相关类型放在 `src/types/summary.ts`
- 上传相关类型放在 `src/types/upload.ts`
- 组件 Props 类型在组件文件内定义

## 项目设计

- [设计方案](docs/plan/design-plan.md) - 运行态留在快速开始，完成后进入“结果中心”，左侧历史列表 + 右侧结果展示
- [API 文档](docs/api/api.md) - 后端接口规范
- [Portal 双模式实现与部署](docs/api/portal-dual-mode.md) - standalone/portal 双模式、子路径部署、发布回滚流程
- [需求文档](docs/demand/整体需求.md) - 项目需求说明
