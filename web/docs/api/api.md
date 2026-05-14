# API 文档（前端联调版，v0.2）

本文件用于前端（Web/Tauri）与后端联调。
当前 API 已完成破坏式重构，按 `/api/*` 新契约调用，不支持旧参数宽松模式。

## 1. URL 组装规则

- 业务接口统一使用 `/api/*`
- 健康检查使用 `GET /health`
- 最终请求 URL 统一为 `joinUrl(apiBaseUrl, endpoint)`

环境变量建议：

| 变量 | Web（同域网关） | App（Tauri） |
|---|---|---|
| `VITE_API_BASE_URL` | `""` 或 `/apps/video`（由网关决定） | `https://<video-backend-domain>` |
| `VITE_API_TIMEOUT` | 按业务默认 | 按业务默认 |

示例：

- endpoint = `/api/summaries`
- Web（`apiBaseUrl=/apps/video`）=> `/apps/video/api/summaries`
- App（`apiBaseUrl=https://video-api.example.com`）=> `https://video-api.example.com/api/summaries`

## 2. 请求头规范

统一请求头：

- `Content-Type: application/json`（上传除外）
- `X-Request-Id: <uuid>`（建议每次请求都带）
- `X-Client-Platform: web | desktop`（建议）

可选头：

- `Authorization: Bearer <token>`（若启用鉴权）
- `x-api-key: <key>`（仅用于限流区分）

## 3. 统一错误响应

```json
{
  "message": "错误描述",
  "code": "ERROR_CODE",
  "status": 422,
  "request_id": "req_xxx",
  "detail": {},
  "errors": []
}
```

- `detail` / `errors` 可能不存在
- `detail` 可能是字符串或对象
- `errors` 可能是数组或对象
- 前端提示优先级：`message` -> `detail` -> fallback 文案

## 4. 关键参数格式（前端必须校验）

- `file_id`: `^f_[0-9a-f]{32}$`
- `job_id`: `^j_[0-9a-f]{32}$`
- `file_hash`: `^[0-9a-f]{64}$`
- `cache_key`: `^[0-9a-f]{64}$`
- `source_url`: 必须为合法 `http/https` URL

`source_type` 规则：

- `source_type = "url"`：
  - 必须带 `source_url`
  - 不能带 `file_id`、`file_hash`
- `source_type = "local"`：
  - `file_id` 和 `file_hash` 必须且只能传一个
  - 不能带 `source_url`

不符合以上规则时会直接返回 `422`。

## 5. HTTP 接口

### 5.1 健康检查

```http
GET /health
```

响应：

```json
{"status":"ok","version":"0.2.0"}
```

### 5.2 文件上传

```http
POST /api/uploads
```

- 请求：`multipart/form-data`
- 字段名：`file`
- 成功状态码：`201`

成功响应：

```json
{
  "file_id": "f_0123456789abcdef0123456789abcdef",
  "original_name": "demo.mp4",
  "size": 123456,
  "mime_type": "video/mp4",
  "file_type": "video",
  "file_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

常见错误：`408`、`413`、`415`、`422`、`429`

### 5.3 缓存查询

```http
POST /api/cache/lookup
```

请求（URL）：

```json
{
  "source_type": "url",
  "source_url": "https://example.com/video"
}
```

请求（本地）：

```json
{
  "source_type": "local",
  "file_id": "f_0123456789abcdef0123456789abcdef"
}
```

或：

```json
{
  "source_type": "local",
  "file_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

成功状态码：`200`

响应（未命中）：

```json
{
  "hit": false,
  "status": "not_found",
  "cache_key": "fa9e..."
}
```

响应（命中完成）：

```json
{
  "hit": true,
  "status": "completed",
  "cache_key": "fa9e...",
  "source_name": "demo.srt",
  "summary_text": "..."
}
```

响应（命中处理中）：

```json
{
  "hit": true,
  "status": "running",
  "cache_key": "fa9e...",
  "job_id": "j_0123456789abcdef0123456789abcdef"
}
```

### 5.4 创建摘要（缓存优先）

```http
POST /api/summaries
```

请求示例：

```json
{
  "source_type": "local",
  "file_id": "f_0123456789abcdef0123456789abcdef",
  "refresh": false
}
```

状态码语义：

- `200`：缓存命中（`status=completed`）
- `202`：处理中或新任务入队（`status=pending/running`）

状态与状态码组合约束（前端应按此分支）：

- `HTTP 200` 仅允许 `status=completed`
- `HTTP 202` 仅允许 `status=pending` 或 `status=running`

响应（命中）：

```json
{
  "status": "completed",
  "cache_key": "fa9e...",
  "summary_text": "...",
  "source_name": "demo.srt"
}
```

响应（处理中/入队）：

```json
{
  "status": "running",
  "cache_key": "fa9e...",
  "job_id": "j_0123456789abcdef0123456789abcdef",
  "source_name": "demo.srt"
}
```

说明：

- `source_type=local` 支持二选一：`file_id` 或 `file_hash`
- 前端默认提交 `file_id`；当只有 `file_hash` 可用时可回退提交 `file_hash`

### 5.5 查询任务状态

```http
GET /api/jobs/{job_id}
```

- `job_id` 格式不合法会直接 `422`

响应：

```json
{
  "job_id": "j_0123456789abcdef0123456789abcdef",
  "cache_key": "fa9e...",
  "status": "running",
  "cache_status": "running",
  "summary_text": null,
  "source_name": "demo.srt"
}
```

### 5.6 查询缓存详情

```http
GET /api/cache/{cache_key}
```

- `cache_key` 格式不合法会直接 `422`

### 5.7 删除缓存

```http
DELETE /api/cache/{cache_key}
```

成功响应：

```json
{
  "cache_key": "fa9e...",
  "deleted": true
}
```

常见错误：`404`（不存在）、`422`（格式非法）、`429`（限流）

## 6. 前端状态机建议

1. 调用 `/api/summaries`
2. 若 `200` 且 `status=completed`，直接展示摘要
3. 若 `202` 且 `status=pending/running`，保存 `job_id` 并轮询 `/api/jobs/{job_id}`
4. 当 job 进入 `completed/failed` 时停止轮询
