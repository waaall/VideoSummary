# API 文档（前后端对齐版）

本文件用于 Video 子应用与后端联调，按统一规范约束 URL、请求头、错误结构与接口路径。

## 1. URL 组装规则（强制）

- 子应用 endpoint 统一使用 `/api/*`。
- 最终请求 URL 统一为 `joinUrl(apiBaseUrl, endpoint)`。
- 健康检查为后端根路径 `GET /health`（不走 `/api`）。

环境变量建议值：

| 变量 | Web（同域网关） | App（Tauri） |
|---|---|---|
| `VITE_API_BASE_URL` | `""` 或 `/apps/video`（取决于网关路由） | `https://<video-backend-domain>` |
| `VITE_API_TIMEOUT` | 按业务默认 | 按业务默认 |

示例：

- endpoint = `/api/summaries`
- Web（`apiBaseUrl=/apps/video`）=> `/apps/video/api/summaries`
- App（`apiBaseUrl=https://video-api.example.com`）=> `https://video-api.example.com/api/summaries`

## 2. 请求头规范

统一请求头：

- `Content-Type: application/json`（上传除外）
- `X-Request-Id: <uuid>`（每次请求必带）
- `X-Client-Platform: web | desktop`（建议）
- `Authorization: Bearer <token>`（若启用 token 鉴权）

兼容头（可选）：

- `x-api-key: <key>`（仅用于限流区分时保留）

## 3. 错误响应规范

后端错误统一返回 JSON：

```json
{
  "message": "错误描述",
  "code": "ERROR_CODE",
  "status": 400
}
```

补充字段（可选）：`request_id`、`detail`、`errors`。
前端应优先读取 `message`，其次 `detail`。

## 4. HTTP 接口

### 4.1 健康检查

```http
GET /health
```

响应：

```json
{"status": "ok", "version": "0.1.0"}
```

### 4.2 文件上传

```http
POST /api/uploads
```

请求：`multipart/form-data`

- 字段名：`file`
- 可选头：`Authorization`、`X-Request-Id`、`X-Client-Platform`、`x-api-key`

支持格式：

- 视频：mp4, mkv, webm, mov, avi, flv, wmv
- 音频：mp3, wav, flac, aac, m4a, ogg, wma
- 字幕：srt, vtt, ass, ssa, sub

响应：

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

常见错误：`413`、`415`、`408`、`429`

### 4.3 缓存查询

```http
POST /api/cache/lookup
```

请求体（URL）：

```json
{"source_type": "url", "source_url": "https://www.youtube.com/watch?v=..."}
```

请求体（本地）：

```json
{"source_type": "local", "file_id": "f_xxx"}
```

### 4.4 创建摘要（缓存优先）

```http
POST /api/summaries
```

请求体：

```json
{
  "source_type": "url",
  "source_url": "https://www.youtube.com/watch?v=...",
  "refresh": false
}
```

响应（命中）：

```json
{"status": "completed", "cache_key": "...", "summary_text": "...", "source_name": "video-title-or-filename"}
```

响应（未命中/处理中）：

```json
{"status": "pending", "cache_key": "...", "job_id": "j_xxx", "source_name": "video-title-or-filename"}
```

### 4.5 任务状态

```http
GET /api/jobs/{job_id}
```

响应：

```json
{
  "job_id": "j_xxx",
  "cache_key": "...",
  "status": "running",
  "cache_status": "running",
  "summary_text": null,
  "source_name": "video-title-or-filename"
}
```

### 4.6 缓存详情

```http
GET /api/cache/{cache_key}
```

响应：`CacheEntryResponse`（含 `source_name`）

### 4.7 缓存删除

```http
DELETE /api/cache/{cache_key}
```

响应：

```json
{"cache_key": "...", "deleted": true}
```

常见错误：`404`（cache_key 不存在）
