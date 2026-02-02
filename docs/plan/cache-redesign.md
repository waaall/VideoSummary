# 同源去重与统一缓存存储重构方案

本设计文档针对“同 URL 只存一份、URL/视频/音频/字幕/总结在一起、提供缓存查询 API”的需求做整体整改。**不要求兼容现有接口/存储结构**，可直接采用最优方案。

## 目标

- **同源去重**：同 URL 或同本地文件只存一份产物。
- **统一存储**：URL/视频/音频/字幕/总结归档到同一个 bundle 目录。
- **缓存优先**：有成功且非空结果时，直接返回，不再重复执行全流程。
- **可追踪**：缓存命中/miss、任务状态、错误原因可查询。

## 非目标

- 不保留旧 API 兼容层。
- 不迁移旧数据（可直接清空旧 `work-dir`）。
- 不引入分布式存储或外部队列（先单机可用）。

## 现状问题（基于当前代码）

- URL 流程按 run_id 写入 `work-dir/downloads/<run_id>/...`、`work-dir/subtitles/<run_id>/...`，**同一视频重复下载与存储**。`app/pipeline/nodes/core.py`
- 总结落在 SQLite（`runs.summary_text`），字幕/视频在文件系统，**产物分散**。`app/api/persistence.py`
- 没有缓存查询 API，API 调用只能走“入队 → 执行 → 轮询”全流程。

## 新架构总览

引入 **Bundle（产物包）** + **Cache Entry（缓存元数据）**：

- **Bundle 目录**：按 `cache_key` 组织单一产物目录，包含视频/音频/字幕/总结等文件。
- **Cache Entry 表**：记录 cache_key、源信息、状态、摘要、路径等元数据。
- **Cache Lookup API**：统一入口，先查缓存；命中即直接返回。
- **Job API**：缓存 miss 时异步处理，并可查询执行状态。

## 存储与目录结构

推荐替换 `work-dir` 结构为：

```
work-dir/
  cache/
    url/
      <cache_key>/
        bundle.json
        source.json
        video.mp4
        audio.wav
        subtitle.vtt
        asr.json
        summary.json
    local/
      <cache_key>/
        bundle.json
        source.json
        video.mp4 (或 audio.*)
        subtitle.*
        asr.json
        summary.json
  tmp/
    <job_id>/... (临时下载/转码目录，完成后原子移动到 cache/)
  metadata.db
```

说明：
- **bundle.json**：该缓存条目的清单与状态（详见后文）。
- **source.json**：源信息（URL 或本地文件元数据/哈希）。
- 产物按固定命名保存（避免 run_id 引入重复）。

## Cache Key 规则

### URL

1. 对 URL 做规范化（去 fragment、统一 scheme、排序 query）。
2. 优先使用 `yt-dlp` 提供的 `(extractor, id)` 作为稳定指纹（可跨 URL 去重）。
3. 最终 `cache_key = sha256("url:" + normalized_url 或 extractor:id)`。

### Local

1. 对文件内容计算 SHA256（流式计算，避免全量加载）。
2. `cache_key = sha256("file:" + file_hash)`。

## Bundle 清单（bundle.json）

示例：

```
{
  "version": "v2",
  "cache_key": "...",
  "source_type": "url",
  "source_ref": "...",          // 规范化URL或文件hash
  "status": "completed",        // pending | running | completed | failed
  "created_at": 1730000000.0,
  "updated_at": 1730000123.0,
  "artifacts": {
    "video": {"path": "video.mp4", "size": 123456, "sha256": "..."},
    "audio": {"path": "audio.wav", "size": 23456, "sha256": "..."},
    "subtitle": {"path": "subtitle.vtt", "size": 3456, "sha256": "..."},
    "asr": {"path": "asr.json", "size": 4567, "sha256": "..."},
    "summary": {"path": "summary.json", "size": 567, "sha256": "..."}
  },
  "summary_text": "..."
}
```

bundle.json 用于快速判断缓存是否完整可用。

## 数据库设计（metadata.db）

替换现有 `runs` 表为新的缓存表（不兼容旧结构）。

### cache_entries

| 字段 | 说明 |
| --- | --- |
| cache_key (PK) | 唯一缓存键 |
| source_type | url / local |
| source_ref | 规范化 URL 或文件 hash |
| status | pending/running/completed/failed |
| summary_text | 摘要文本（方便直接返回） |
| bundle_path | bundle 目录路径 |
| error | 失败原因 |
| created_at / updated_at | 时间戳 |
| last_accessed | 最近访问 |

### cache_jobs

| 字段 | 说明 |
| --- | --- |
| job_id (PK) | 任务 ID |
| cache_key (FK) | 关联缓存条目 |
| status | pending/running/completed/failed |
| created_at / updated_at | 时间戳 |
| error | 失败原因 |

约束：
- cache_key 唯一，避免并发重复生成。
- 如果 cache_entry 正在 running，后续请求直接返回 job_id。

## API 设计（新接口）

### 1) 缓存查询

`POST /cache/lookup`

请求：
```
{
  "source_type": "url",
  "source_url": "...",           // url 模式
  "file_hash": "...",            // local 模式（或上传后返回的 hash）
  "allow_stale": false
}
```

响应（命中）：
```
{
  "hit": true,
  "status": "completed",
  "cache_key": "...",
  "summary_text": "...",
  "bundle": { ... }
}
```

响应（miss）：
```
{
  "hit": false,
  "status": "not_found"
}
```

### 2) 统一执行入口（缓存优先）

`POST /summaries`

请求同 `/cache/lookup`，可加：
- `refresh: true` 强制重新生成
- `options`: transcribe_config / summary 参数

响应：
- **缓存命中**：直接返回 `status=completed + summary_text`
- **未命中**：返回 `202 + job_id + cache_key`

### 3) 任务状态

`GET /jobs/{job_id}` → 任务状态与 trace（可选）

### 4) 直接获取缓存

`GET /cache/{cache_key}` → bundle + summary

## 处理流程（URL/Local 统一）

1. API 入口计算 cache_key。
2. 查询 cache_entries：
   - `status=completed` 且 summary_text 非空 → 直接返回。
   - `status=running/pending` → 返回 job_id。
   - `status=failed` → 默认返回失败；若 `refresh=true` 则重跑。
3. Miss：创建 cache_entry（pending）与 job，入队。
4. Worker 执行 pipeline：
   - 下载字幕 → 解析 → 校验
   - 必要时下载视频 → 抽音频 → 转录
   - 总结（LLM）
5. 产物全部写入 bundle 目录并更新 bundle.json / cache_entries。

## Pipeline 调整点（指向现有代码）

需要重构的关键位置：

- `app/api/main.py`：旧 `/pipeline/auto/*` 改为 `/summaries` 和 `/cache/lookup`。
- `app/api/persistence.py`：替换 `runs` 表，新增 `cache_entries`、`cache_jobs`。
- `app/api/worker.py`：队列任务以 cache_key 为核心。
- `app/pipeline/context.py`：新增 `cache_key`, `bundle_dir` 等字段。
- `app/pipeline/nodes/core.py`：所有产物写入 `bundle_dir` 内，禁止 run_id 目录。
- `app/api/uploads.py`：本地文件在上传后立即计算 hash，复用已有 bundle。

## 去重策略与一致性

- **URL**：规范化 + extractor/id，避免同源重复。
- **Local**：文件内容 hash，避免重复存储。
- **一致性**：下载与转码先写 `tmp/<job_id>`，成功后 `rename` 到 `cache/<cache_key>`。

## 清理策略

新增 GC 机制（可配置）：

- `CACHE_MAX_BYTES`：超限时按 `last_accessed` 清理。
- `CACHE_TTL_DAYS`：超时清理。
- `FAILED_TTL_HOURS`：失败条目快速清理。

## 观察性与日志

- 日志统一输出 `cache_key`、`job_id`、`status`。
- 记录 cache hit/miss 与节省时长指标。

## 测试计划

- 单元测试：
  - URL 规范化与 cache_key 一致性
  - 文件 hash 计算
- 集成测试：
  - 同 URL 连续请求：只下载一次，第二次直接命中
  - 失败重试逻辑（refresh）

## 实施步骤（计划）

1. **数据模型与存储**：新增 cache_entries / cache_jobs，定义 bundle.json 结构。
2. **Cache Key 计算**：URL 规范化 + extractor/id + 本地 hash 计算。
3. **API 重构**：新增 `/cache/lookup` 与 `/summaries`。
4. **Pipeline 产物归档**：全部写到 bundle_dir。
5. **去重与锁**：cache_key 唯一约束 + running 状态复用。
6. **GC 清理**：新增定期清理任务。
7. **测试与压测**：验证命中率、存储占用与速度。

---

如需进一步细化（表结构 SQL、API schema、bundle.json 的精确字段定义），我可以在这个文档基础上继续展开。*** End Patch"}">No, that's wrong. I'll redo. Let me correctly format apply_patch. The tool expects freeform. I must provide correct patch. Let's redo properly. We'll re-run apply_patch with correct format. We need to ensure no extra quoting or JSON. Let's redo. We'll remove the previous attempt. Currently no file added. So apply patch with correct. We'll craft patch again. Ensure no extra trailing. We'll not include backticks? We'll keep code blocks. Also ensure ascii. The doc will contain only ascii? It has Chinese characters; ok, but instruction says default ascii unless file already uses non-ascii. docs already include Chinese; so okay. We'll do correct patch. Let's re-run. We'll include patch content accordingly. Let's ensure it's not too long. It's fine. We'll do proper apply_patch. We'll add file. Let's do. 
