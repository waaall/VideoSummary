# API 文档

VideoSummary 核心 API 接口文档。包含 HTTP 接口、缓存/任务接口、以及环境变量说明。

---

## 配置与环境变量（必读）

### 配置优先级
1. **`AppData/settings.json`**（后端全局默认配置）
2. **环境变量**（覆盖部分运行时配置）
3. **代码默认值**（兜底）

> 说明：请求体仅支持 `refresh` 控制是否重算，不支持按请求覆盖处理参数。

### settings.json（BackendConfig）
- **路径**：`AppData/settings.json`
- **读取逻辑**：`app/api/config.py`
- **枚举字段**：保存为 **枚举的 value 字符串**（大多为中文展示值）
- **环境变量覆盖**：`OPENAI_API_KEY` 会覆盖 `llm.openai_api_key`
- **自动流程实际读取**：`transcribe / whisper / faster_whisper / whisper_api / work_dir`（其余字段主要用于 UI/其它模块）

**默认结构（等同于未配置时的默认值）**：

```json
{
  "llm": {
    "service": "OpenAI 兼容",
    "openai_model": "gpt-4o-mini",
    "openai_api_key": "",
    "openai_api_base": "https://api.openai.com/v1",
    "silicon_cloud_model": "gpt-4o-mini",
    "silicon_cloud_api_key": "",
    "silicon_cloud_api_base": "https://api.siliconflow.cn/v1",
    "deepseek_model": "deepseek-chat",
    "deepseek_api_key": "",
    "deepseek_api_base": "https://api.deepseek.com/v1",
    "ollama_model": "llama2",
    "ollama_api_key": "ollama",
    "ollama_api_base": "http://localhost:11434/v1",
    "lm_studio_model": "qwen2.5:7b",
    "lm_studio_api_key": "lmstudio",
    "lm_studio_api_base": "http://localhost:1234/v1",
    "gemini_model": "gemini-pro",
    "gemini_api_key": "",
    "gemini_api_base": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "chatglm_model": "glm-4",
    "chatglm_api_key": "",
    "chatglm_api_base": "https://open.bigmodel.cn/api/paas/v4"
  },
  "translate": {
    "service": "微软翻译",
    "need_reflect_translate": false,
    "deeplx_endpoint": "",
    "batch_size": 10,
    "thread_num": 10
  },
  "transcribe": {
    "model": "B 接口",
    "output_format": "SRT",
    "language": "英语"
  },
  "whisper": {
    "model": "tiny"
  },
  "faster_whisper": {
    "program": "faster-whisper-xxl.exe",
    "model": "tiny",
    "model_dir": "",
    "device": "cuda",
    "vad_filter": true,
    "vad_threshold": 0.4,
    "vad_method": "silero_v4",
    "ff_mdx_kim2": false,
    "one_word": true,
    "prompt": ""
  },
  "whisper_api": {
    "api_base": "",
    "api_key": "",
    "model": "",
    "prompt": ""
  },
  "subtitle": {
    "need_optimize": false,
    "need_translate": false,
    "need_split": false,
    "target_language": "简体中文",
    "max_word_count_cjk": 28,
    "max_word_count_english": 20,
    "custom_prompt_text": ""
  },
  "video": {
    "soft_subtitle": false,
    "need_video": true,
    "quality": "中等质量",
    "use_subtitle_style": false
  },
  "subtitle_style": {
    "style_name": "default",
    "layout": "译文在上",
    "preview_image": "",
    "render_mode": "圆角背景",
    "rounded_bg_font_name": "LXGW WenKai",
    "rounded_bg_font_size": 52,
    "rounded_bg_color": "#191919C8",
    "rounded_bg_text_color": "#FFFFFF",
    "rounded_bg_corner_radius": 12,
    "rounded_bg_padding_h": 28,
    "rounded_bg_padding_v": 14,
    "rounded_bg_margin_bottom": 60,
    "rounded_bg_line_spacing": 10,
    "rounded_bg_letter_spacing": 0
  },
  "cache": {
    "enabled": true
  },
  "work_dir": "work-dir"
}
```

**字段说明（简版）**：
- `llm`：LLM 服务配置（字幕优化/翻译等模块使用；**HTTP 摘要节点使用 OPENAI_* 环境变量**）
- `translate`：翻译服务选择与并发参数
- `transcribe / whisper / faster_whisper / whisper_api`：转录/模型相关配置（自动流程读取）
- `subtitle`：字幕切分/翻译默认行为
- `video / subtitle_style`：视频合成与字幕样式（UI/离线流程使用）
- `cache`：缓存开关
- `work_dir`：工作目录

### 环境变量一览
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JOB_WORKER_COUNT` | `1` | 后台 worker 数量 |
| `UPLOAD_CONCURRENCY` | `2` | 并发上传数量 |
| `UPLOAD_RATE_LIMIT_PER_MINUTE` | `30` | 上传接口每分钟限流 |
| `SUMMARY_RATE_LIMIT_PER_MINUTE` | `60` | Summary 接口每分钟限流 |
| `UPLOAD_CHUNK_SIZE` | `8*1024*1024` | 上传读写 chunk 大小（字节） |
| `UPLOAD_READ_TIMEOUT_SECONDS` | `30` | 上传读取超时（秒） |
| `UPLOAD_WRITE_TIMEOUT_SECONDS` | `30` | 上传写入超时（秒） |
| `UPLOAD_CONTENT_LENGTH_GRACE_BYTES` | `10*1024*1024` | 允许 `Content-Length` 超出上限的冗余字节 |
| `TRANSCODE_CONCURRENCY` | `2` | 音频抽取并发 |
| `TRANSCRIBE_CONCURRENCY` | `2` | 转录并发 |
| `PIPELINE_STAGE_WAIT_SECONDS` | `300` | 并发等待超时（秒） |
| `SUBTITLE_MAX_SIZE_MB` | `50` | URL 字幕下载最大大小（MB） |
| `SUBTITLE_DOWNLOAD_CHUNK_SIZE` | `262144` | URL 字幕下载 chunk 大小（字节） |
| `SUBTITLE_DOWNLOAD_TIMEOUT` | `30` | URL 字幕下载超时（秒） |
| `VIDEO_MAX_SIZE_MB` | `4096` | URL 视频下载最大大小（MB） |
| `VIDEO_DOWNLOAD_RATE_LIMIT` | `0` | URL 视频下载限速（字节/秒，0=不限速） |
| `LLM_MODEL` | `gpt-3.5-turbo` | TextSummarizeNode 默认模型 |
| `OPENAI_BASE_URL` | *空* | **LLM 摘要/翻译**使用（OpenAI 兼容 Base URL） |
| `OPENAI_API_KEY` | *空* | **LLM 摘要/翻译**使用 |
| `DEEPLX_ENDPOINT` | `https://api.deeplx.org/translate` | DeepLX 翻译服务地址 |

### 其他文件型配置
- `AppData/cookies.txt`：URL 下载（yt-dlp）时用于高质量视频/字幕下载

---

## HTTP API 接口

> 说明：API 默认不做鉴权；限流以 **IP / `x-api-key` 头**区分。
> 约定：业务接口统一走 `/api/*`，仅健康检查保留为 `GET /health`。

### 统一请求头（建议）

- `Content-Type: application/json`（上传除外）
- `X-Request-Id: <uuid>`（建议每次请求传入；服务端会在响应头回传 `x-request-id`）
- `X-Client-Platform: web | desktop`（建议）
- `Authorization: Bearer <token>`（若启用 token 鉴权）
- `x-api-key: <key>`（仅用于限流区分，可选）

### 统一错误响应

错误返回为 JSON：

```json
{
  "message": "错误描述",
  "code": "ERROR_CODE",
  "status": 400,
  "request_id": "req_xxx"
}
```

可选字段：`detail`、`errors`。

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
POST /api/uploads
```

上传本地文件，返回 `file_id` 供本地自动流程使用。

**请求**: `multipart/form-data`

- 字段名: `file`
- 可选请求头: `Authorization`、`X-Request-Id`、`X-Client-Platform`、`x-api-key`

**支持的文件类型**:
- 视频: mp4, mkv, webm, mov, avi, flv, wmv
- 音频: mp3, wav, flac, aac, m4a, ogg, wma
- 字幕: srt, vtt, ass, ssa, sub

**限制**:
- 最大 2GB
- 默认保留 24 小时后自动清理
- 并发/超时/限流可通过环境变量调整（见上文）

**响应**: `UploadResponse`

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
POST /api/cache/lookup
```

根据 `source_type` + `source_url/file_id/file_hash` 查询缓存状态。

**请求体**:
```json
{"source_type": "url", "source_url": "https://www.youtube.com/watch?v=..."}
```

**响应（命中）**:
```json
{
  "hit": true,
  "status": "completed",
  "cache_key": "...",
  "source_name": "video-title-or-filename",
  "summary_text": "..."
}
```

**响应（未命中）**:
```json
{"hit": false, "status": "not_found", "cache_key": "..."}
```

**响应（处理中）**:
```json
{"hit": false, "status": "running", "cache_key": "...", "job_id": "j_xxx", "source_name": "video-title-or-filename"}
```

---

### 创建/查询摘要（缓存优先）

```http
POST /api/summaries
```

**请求体**:
```json
{
  "source_type": "local",
  "file_id": "f_xxx",
  "refresh": false
}
```

**响应（缓存命中）**:
```json
{"status": "completed", "cache_key": "...", "summary_text": "...", "source_name": "video-title-or-filename"}
```

**响应（未命中/处理中）**:
```json
{"status": "pending", "cache_key": "...", "job_id": "j_xxx", "source_name": "video-title-or-filename"}
```

---

### 任务状态

```http
GET /api/jobs/{job_id}
```

**响应**:
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

---

### 缓存详情

```http
GET /api/cache/{cache_key}
```

**响应**: `CacheEntryResponse`

```json
{
  "cache_key": "...",
  "source_type": "url",
  "source_ref": "https://example.com/...",
  "source_name": "video-title-or-filename",
  "status": "completed",
  "profile_version": "v1",
  "summary_text": "...",
  "bundle_path": "/path/to/cache/...",
  "error": null,
  "created_at": 0,
  "updated_at": 0,
  "last_accessed": 0
}
```

---

### 缓存删除

```http
DELETE /api/cache/{cache_key}
```

删除缓存条目及其 bundle，同时清理关联的缓存任务记录。

**响应**:
```json
{"cache_key": "...", "deleted": true}
```

**常见错误**:
- `404` cache_key 不存在

---

## 常见调用示例（curl）

### URL 摘要（缓存优先）

```bash
curl -X POST http://localhost:8765/api/summaries \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "url",
    "source_url": "https://youtube.com/watch?v=..."
  }'
```

### 任务状态查询

```bash
curl -s http://127.0.0.1:8765/api/jobs/<job_id> | python -m json.tool
```

---

相关文档：
- [架构设计](/dev/architecture)
- [贡献指南](/dev/contributing)
