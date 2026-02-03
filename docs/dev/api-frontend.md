# API 文档（前端版）

面向前端/集成的精简版，只包含 UI/调用需要知道的内容。

---

## 基本说明

- API 默认无鉴权；可选 `x-api-key` 仅用于区分限流。
- 摘要请求为**异步**：`/summaries` 未命中时返回 `job_id`，前端需轮询 `/jobs/{job_id}`。
- 缓存命中时会直接返回 `summary_text`，无需轮询。

---

## 配置方式与生效时机

### 启动时配置（需重启后端）
以下配置不会在运行中自动刷新，修改后需要重启后端进程生效：

- **环境变量**（服务启动前设置）：
  - LLM 摘要/翻译：`OPENAI_BASE_URL`、`OPENAI_API_KEY`、`LLM_MODEL`
  - 翻译服务：`DEEPLX_ENDPOINT`
  - 运行与限流：`JOB_WORKER_COUNT`、`UPLOAD_CONCURRENCY`、`SUMMARY_RATE_LIMIT_PER_MINUTE` 等（详见 `docs/dev/api.md`）
- **`AppData/settings.json`**（后端默认配置）：
  - 作为全局默认值来源（LLM / whisper / faster_whisper / whisper_api / work_dir 等）
  - 进程启动后不会自动重载，修改需重启后端

> 说明：当前 API 不支持在请求体中设置 `OPENAI_BASE_URL` / `OPENAI_API_KEY`，只能通过环境变量配置。

---

## HTTP 接口

### 健康检查

```http
GET /health
```

**响应**:
```json
{"status": "ok", "version": "0.1.0"}
```

---

### 文件上传

```http
POST /uploads
```

**请求**: `multipart/form-data`
- 字段名: `file`
- 可选头: `x-api-key`

**支持格式**:
- 视频: mp4, mkv, webm, mov, avi, flv, wmv
- 音频: mp3, wav, flac, aac, m4a, ogg, wma
- 字幕: srt, vtt, ass, ssa, sub

**响应**:
```json
{
  "file_id": "f_xxx",
  "original_name": "demo.mp4",
  "size": 123456,
  "mime_type": "video/mp4",
  "file_type": "video",
  "file_hash": "sha256..."
}
```

**常见错误**:
- `413` 文件过大
- `415` 文件类型不支持
- `408` 读写超时
- `429` 请求过于频繁

---

### 缓存查询

```http
POST /cache/lookup
```

**请求体（URL）**:
```json
{"source_type": "url", "source_url": "https://www.youtube.com/watch?v=..."}
```

**请求体（本地）**:
```json
{"source_type": "local", "file_id": "f_xxx"}
```

---

### 创建/查询摘要（缓存优先）

```http
POST /summaries
```

**请求体**:
```json
{
  "source_type": "url",
  "source_url": "https://www.youtube.com/watch?v=...",
  "refresh": false
}
```

**响应（命中）**:
```json
{"status": "completed", "cache_key": "...", "summary_text": "..."}
```

**响应（未命中/处理中）**:
```json
{"status": "pending", "cache_key": "...", "job_id": "j_xxx"}
```

---

### 任务状态

```http
GET /jobs/{job_id}
```

**响应**:
```json
{
  "job_id": "j_xxx",
  "cache_key": "...",
  "status": "running",
  "cache_status": "running",
  "summary_text": null
}
```

---

### 缓存详情

```http
GET /cache/{cache_key}
```

**响应**: `CacheEntryResponse`

---

### 缓存删除

```http
DELETE /cache/{cache_key}
```

**响应**:
```json
{"cache_key": "...", "deleted": true}
```

**常见错误**:
- `404` cache_key 不存在
