# API 文档（Pydantic v2 重构版）

本版本是直接替换 `/api/*` 的重构版本，不提供向后兼容层。
详细不兼容项请见：`docs/dev/api-breaking-changes.md`。

## 1. 基础信息

- 服务名：`VideoSummary API`
- 版本号：`0.2.0`
- OpenAPI：`/openapi.json`
- 交互文档：`/docs`

## 2. 统一约定

### 2.1 统一错误响应

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

- `detail`、`errors` 为可选字段。
- 响应头始终包含 `x-request-id`。

### 2.2 枚举与格式

- `source_type`: `url | local`
- `file_type`: `video | audio | subtitle`
- `cache/status`: `completed | running | pending | failed | not_found`
- `summary/status`: `completed | running | pending | failed`
- `job/status`: `pending | running | completed | failed`

字段格式约束：

- `file_id`: `^f_[0-9a-f]{32}$`
- `job_id`: `^j_[0-9a-f]{32}$`
- `file_hash`: `^[0-9a-f]{64}$`
- `cache_key`: `^[0-9a-f]{64}$`
- `source_url`: 必须是合法 `http/https` URL

### 2.3 source 参数校验规则

`source_type=url`：

- 必须提供 `source_url`
- 不能提供 `file_id`、`file_hash`

`source_type=local`：

- `file_id` 与 `file_hash` 必须且只能提供一个
- 不能提供 `source_url`

## 3. 配置（BaseSettings 拆分）

### 3.1 上传配置（`app/api/settings.py`）

默认读取前缀：`UPLOAD_`

- `UPLOAD_CONCURRENCY`（默认 2）
- `UPLOAD_CHUNK_SIZE`（默认 `8*1024*1024`）
- `UPLOAD_READ_TIMEOUT_SECONDS`（默认 30）
- `UPLOAD_WRITE_TIMEOUT_SECONDS`（默认 30）
- `UPLOAD_CONTENT_LENGTH_GRACE_BYTES`（默认 `10*1024*1024`）

### 3.2 限流配置（`app/api/settings.py`）

- 新前缀：`RATE_LIMIT_`
- 兼容读取旧变量名：`UPLOAD_RATE_LIMIT_PER_MINUTE`、`SUMMARY_RATE_LIMIT_PER_MINUTE`

变量：

- `RATE_LIMIT_UPLOAD_PER_MINUTE`（默认 30）
- `RATE_LIMIT_SUMMARY_PER_MINUTE`（默认 60）

### 3.3 Worker 配置（`app/api/settings.py`）

默认读取前缀：`JOB_`

- `JOB_WORKER_COUNT`（默认 1，允许 0）

## 4. 接口列表

## 4.1 健康检查

### GET `/health`

响应：

```json
{"status":"ok","version":"0.2.0"}
```

## 4.2 上传文件

### POST `/api/uploads`

- `multipart/form-data`
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

常见错误：

- `408` 读写超时
- `413` 文件过大
- `415` 文件类型不支持
- `429` 限流
- `422` 参数校验失败

## 4.3 查询缓存

### POST `/api/cache/lookup`

成功状态码：`200`

请求示例（URL）：

```json
{
  "source_type": "url",
  "source_url": "https://example.com/video"
}
```

请求示例（本地）：

```json
{
  "source_type": "local",
  "file_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

响应示例：

```json
{
  "hit": false,
  "status": "not_found",
  "cache_key": "fa9e...",
  "source_name": null,
  "summary_text": null,
  "bundle_path": null,
  "job_id": null,
  "error": null,
  "created_at": null,
  "updated_at": null
}
```

## 4.4 创建摘要任务（缓存优先）

### POST `/api/summaries`

成功状态码：

- `200`：缓存命中且 `completed`
- `202`：`running/pending` 或新任务已入队

请求示例：

```json
{
  "source_type": "local",
  "file_id": "f_0123456789abcdef0123456789abcdef",
  "refresh": false
}
```

响应示例（命中）：

```json
{
  "status": "completed",
  "cache_key": "fa9e...",
  "job_id": null,
  "summary_text": "摘要内容",
  "source_name": "demo.srt",
  "error": null,
  "created_at": 1739334600.12
}
```

响应示例（排队）：

```json
{
  "status": "pending",
  "cache_key": "fa9e...",
  "job_id": "j_0123456789abcdef0123456789abcdef",
  "summary_text": null,
  "source_name": "demo.srt",
  "error": null,
  "created_at": 1739334600.12
}
```

## 4.5 查询任务状态

### GET `/api/jobs/{job_id}`

- `job_id` 必须匹配 `^j_[0-9a-f]{32}$`
- 成功状态码：`200`

响应示例：

```json
{
  "job_id": "j_0123456789abcdef0123456789abcdef",
  "cache_key": "fa9e...",
  "status": "running",
  "created_at": 1739334600.12,
  "updated_at": 1739334605.50,
  "error": null,
  "cache_status": "running",
  "summary_text": null,
  "source_name": "demo.srt"
}
```

## 4.6 获取缓存条目

### GET `/api/cache/{cache_key}`

- `cache_key` 必须匹配 `^[0-9a-f]{64}$`
- 成功状态码：`200`

## 4.7 删除缓存条目

### DELETE `/api/cache/{cache_key}`

- `cache_key` 必须匹配 `^[0-9a-f]{64}$`
- 成功状态码：`200`

响应：

```json
{
  "cache_key": "fa9e...",
  "deleted": true
}
```

## 5. 开发与测试

执行 API 相关测试：

```bash
pytest tests/test_api -q
```

当前覆盖重点：

- Pydantic v2 条件校验与正则校验
- 路由 path 参数格式校验（422）
- 限流行为（429）
- 本地资源不存在（404）
- 上传/摘要状态码语义（201/200/202）


# API Breaking Changes（`/api` 直接替换）

本文档记录本次 Pydantic v2 重构引入的不兼容变更，供调用方升级参考。

## 1. 变更摘要

- 重构范围：`/api/*` 全量接口
- 兼容策略：无兼容层，旧请求格式可能直接返回 `422` 或 `404`
- 主要变化：
  - 请求参数强类型化（枚举、URL、regex）
  - `source` 组合规则收紧（`local` 必须且只能 `file_id/file_hash` 二选一）
  - 状态码语义调整（上传 `201`，摘要 `200/202`）
  - 路由 path 参数强校验（`job_id/cache_key`）

## 2. Old vs New 对照

## 2.1 请求字段类型

- `source_type`
  - 旧：任意字符串（运行时再判断）
  - 新：枚举 `url | local`

- `source_url`
  - 旧：`str`，格式校验弱
  - 新：`AnyHttpUrl`，非法 URL 直接 `422`

- `file_id`
  - 旧：任意字符串
  - 新：必须匹配 `^f_[0-9a-f]{32}$`

- `file_hash`
  - 旧：任意字符串
  - 新：必须匹配 `^[0-9a-f]{64}$`

- `job_id`（path）
  - 旧：任意字符串，通常业务层 404
  - 新：先做 regex 校验，不匹配直接 `422`

- `cache_key`（path）
  - 旧：任意字符串，通常业务层 404
  - 新：先做 regex 校验，不匹配直接 `422`

## 2.2 source 组合规则

- `source_type=url`：
  - 新增要求：必须提供 `source_url`
  - 新增限制：不能携带 `file_id`/`file_hash`

- `source_type=local`：
  - 新增要求：`file_id` 与 `file_hash` 必须且只能提供一个
  - 新增限制：不能携带 `source_url`

## 2.3 状态码变化

- `POST /api/uploads`
  - 旧：`200`
  - 新：`201`

- `POST /api/summaries`
  - 旧：通常 `200`
  - 新：
    - 命中 `completed` 返回 `200`
    - 处理中/新入队返回 `202`

## 3. 错误行为变化

- 过去可能进入业务逻辑后报错（400/404）的输入，现在会在 Pydantic 校验阶段直接 `422`。
- 对于 `local` 资源：
  - 格式合法但资源不存在：`404`
  - 格式非法：`422`

## 4. 升级建议

1. 升级请求构造逻辑，确保满足 `source` 组合约束。
2. 对 `file_id/job_id/cache_key` 按新正则提前校验，避免无效请求。
3. 客户端按新状态码处理摘要流程：
   - `200` 直接展示结果
   - `202` 进入轮询
4. 若此前依赖宽松 URL 解析，改为标准 `http/https` URL。
5. 更新接口测试基线，至少覆盖：
   - 参数校验失败 `422`
   - 资源不存在 `404`
   - 限流 `429`
   - 上传 `201`
   - 摘要 `200/202`
