# 无 DAG 的全量重构设计（缓存优先、固定 URL/Local 流程）

本设计文档定义 **完全重构** 的目标架构：移除 DAG 设计与旧接口/旧数据结构，仅保留两条固定流程（URL / Local），并以“缓存优先 + 同源只存一份”为核心。

> 本文不保留任何旧兼容，不提供迁移策略；切换即清空旧结构。

## 目标

- **无 DAG**：仅保留两条固定流程（URL / Local）。
- **缓存优先**：同源只存一份；命中直接返回。
- **严格有效性判断**：没有生成**最终有效总结**的缓存，不视为命中。
- **异步执行**：API 即时返回 job_id；后台完成。
- **模块化与高可读性**：清晰分层与职责。
- **日志可追踪**：全链路标识、节点耗时与错误可溯源。

## 非目标

- 不保留旧接口（如 `/pipeline/*`）。
- 不保留旧数据结构（如 `runs`、`run_nodes`）。
- 不兼容旧存储路径（如 `work-dir/downloads`, `work-dir/subtitles`）。

## 总体架构

```
API Layer  ->  Cache Layer  ->  Job Queue  ->  Worker
                                   |
                              Fixed Pipelines
                                   |
                             Bundle Storage
                                   |
                               Metadata DB
```

### 分层职责

- **API 层**：鉴权、限流、参数校验、缓存命中判断、任务入队。
- **Cache 层**：计算 cache_key、查询/更新缓存条目、有效性判断。
- **Job 队列**：异步调度，不做业务逻辑。
- **Worker**：执行固定流程，产物写入 bundle。
- **存储层**：bundle 目录 + SQLite 元数据。

## 接口设计（仅保留新接口）

### 1) 创建/查询摘要（缓存优先）

`POST /summaries`

请求：
```
{
  "source_type": "url" | "local",
  "source_url": "...",       // url 模式
  "file_id": "...",          // local 模式（上传返回）
  "file_hash": "...",        // local 模式（可直接传）
  "refresh": false
}
```

响应：
- 命中：`status=completed` + `summary_text`
- 处理中：`status=pending|running` + `job_id`
- 未命中：`status=pending` + `job_id`

### 2) 缓存查询（只读）

`POST /cache/lookup`

请求同 `/summaries`，无副作用。

### 3) 任务状态

`GET /jobs/{job_id}`

### 4) 缓存详情

`GET /cache/{cache_key}`

## 固定流程定义（无 DAG）

### URL 流程

1. 输入校验（source_url 必填）
2. **字幕优先**：下载字幕 → 解析 → 校验有效性
3. 若无有效字幕：下载视频 → 抽音频 → 转录
4. 总结
5. 写入 bundle + 更新 cache_entry

### Local 流程

1. 输入校验（file_id 或 file_hash 必填）
2. **字幕优先**：若提供字幕文件 → 解析 → 校验
3. 否则若提供音频：转录
4. 否则若提供视频：抽音频 → 转录
5. 总结
6. 写入 bundle + 更新 cache_entry

## 缓存策略（同源只存一份）

### cache_key 规则

- **URL**：规范化 URL 或 yt-dlp (extractor, id) → sha256
- **Local**：文件内容 hash → sha256

**cache_key 仅与 source 相关**，不因请求参数变化而分叉。

### 严格有效性判断（命中判定）

命中必须满足：
- cache_entry.status == `completed`
- `summary_text` 非空且通过有效性校验
- bundle.json 中 `summary.json` 存在且结构完整
- bundle.json 的 `profile_version` == 当前服务版本

不满足任一条件 → 视为未命中，触发重算或 `refresh`。

### 配置与版本策略

为保证“同源只存一份”，处理参数必须固定：
- **服务端固定 profile**（转录模型、语言、总结策略等）
- 请求参数仅允许非语义配置（例如：返回字段选择）
- 若请求提供与 profile 不一致的参数 → 直接 400

当处理策略变更时：
- 提升 `profile_version`
- 旧缓存视为无效并覆盖重算

## 数据模型（新结构）

### cache_entries

| 字段 | 说明 |
| --- | --- |
| cache_key (PK) | 缓存键 |
| source_type | url / local |
| source_ref | 规范化 URL 或文件 hash |
| status | pending / running / completed / failed |
| summary_text | 摘要文本 |
| bundle_path | bundle 目录 |
| error | 失败原因 |
| profile_version | 处理策略版本 |
| created_at / updated_at | 时间戳 |
| last_accessed | 最近访问 |

### cache_jobs

| 字段 | 说明 |
| --- | --- |
| job_id (PK) | 任务 ID |
| cache_key (FK) | 关联缓存键 |
| status | pending / running / completed / failed |
| error | 错误原因 |
| created_at / updated_at | 时间戳 |

## 存储布局

```
work-dir/
  cache/
    url/<cache_key>/
      bundle.json
      source.json
      video.mp4
      audio.wav
      subtitle.vtt
      asr.json
      summary.json
    local/<cache_key>/
      bundle.json
      source.json
      ...
  tmp/<job_id>/...
  metadata.db
```

### bundle.json（示例字段）

```
{
  "version": "v2",
  "profile_version": "2025-02-02",
  "cache_key": "...",
  "source_type": "url",
  "source_ref": "...",
  "status": "completed",
  "created_at": 0,
  "updated_at": 0,
  "artifacts": {
    "video": {"path": "video.mp4", "size": 0, "sha256": "..."},
    "audio": {"path": "audio.wav", "size": 0, "sha256": "..."},
    "subtitle": {"path": "subtitle.vtt", "size": 0, "sha256": "..."},
    "asr": {"path": "asr.json", "size": 0},
    "summary": {"path": "summary.json", "size": 0}
  },
  "summary_text": "...",
  "error": null
}
```

## 异步执行流程

1. API 计算 cache_key
2. cache_entries 命中 → 直接返回
3. 未命中 → 创建 cache_entry + job → 入队
4. Worker 执行固定流程，所有产物写入 tmp 目录
5. 成功 → 原子 move tmp → cache/<cache_key>
6. 更新 cache_entry 与 job 状态

## 失败处理策略

- 任一关键步骤失败 → job.status=failed, cache_entry.status=failed
- **失败不算缓存命中**
- refresh=true 强制重算并覆盖旧缓存

## 日志与追踪

每个请求/任务必须携带：

- `request_id`
- `job_id`
- `cache_key`
- `source_type`

日志需覆盖：
- 缓存命中/未命中
- 下载、转码、转录、总结耗时
- 失败原因与异常堆栈

## GC 与清理

提供后台 GC：
- TTL 清理
- 总大小上限清理（LRU）
- failed 条目短期清理

## 必须删除的旧设计

- `/pipeline/*` 所有端点
- `runs` / `run_nodes` 表与相关代码
- `work-dir/downloads` / `work-dir/subtitles` 旧路径
- 任意旧流程的“回退/兼容”分支

## 实施顺序（建议）

1. 清理旧接口与旧表结构（强制切换）
2. 新建 cache_entries / cache_jobs 模型
3. 实现 cache_key 与严格有效性判定
4. 实现固定 URL/Local 流程 worker
5. bundle 原子落盘与 profile_version
6. 日志与 GC

