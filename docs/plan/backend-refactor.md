# 后端化整改方案（移除 Qt/UI 依赖）

本文面向把本项目作为“后端引擎”来用，保留转录/解析/下载等能力，删除 Qt UI 相关部分。

## 目标

- 提供可调用的后端管线，支持“可配置的分支逻辑”（而非固定的下载 → 抽音频 → 转录 → 解析字幕）。
- 移除 Qt 相关依赖与 UI 代码，确保纯后端可运行。
- 保留核心能力：ASR、字幕解析、翻译、优化、视频工具（ffmpeg）。

## 设计原则（针对本次整改）

1. 本次为全新后端设计，不需要兼容历史用户数据/配置；仅需要适配 `app/core` 中的现有代码能力。
2. “new” 之类的命名没有必要；在明确只支持新结构的前提下，这类命名是多余且易产生歧义，应使用中性命名。

## 评审结论（可执行性与补强点）

整体思路很稳，方向正确，尤其是把 **大文件 I/O 统一流式** 和 **API/Worker 解耦** 作为硬约束，这是这类系统最常见的坑。当前设计已具备“可落地 + 可扩展 + 抗 DoS”的骨架。

### 做得对的关键点

- **流式上传/下载 + 过程限额**：直接解决 `await file.read()` 的 OOM/DoS 风险。
- **Control Plane / Worker 解耦**：API 只做任务编排与状态查询，后续扩展到队列/多 worker 很顺畅。
- **产物（artifact）+ 状态机**：可恢复、可重试、可观测，进度监控天然可落地。

### 建议补强（落地更稳）

- **统一 ID 语义**：`job_id/run_id` 建议只保留一个，避免前后端混乱。
- **限制策略**：除流式限额外，还需补：
  - `Content-Length` 校验（有则提前拒）
  - 读/写超时
  - 速率限制（IP/Token）
  - 并发上限（上传/转码/转录）
- **存储一致性**：本地磁盘 + 元数据持久化（SQLite/Redis/JSON）确保重启后 `file_id` 可恢复。
- **流水线状态表**：每步 `started_at/ended_at/status/error/retryable` 统一入库（最小版 SQLite 足够）。

### 与现有代码的最小增量对齐

- `PipelineRunner` 保持逻辑，但执行放到 Worker。
- API 只负责：创建任务、入队、返回 `job_id`、查询状态。
- `/uploads` 改为流式写盘（chunked），写入过程内强制限额。
- `PipelineContext.trace` 直接落库，作为进度接口的数据源。

## 新增（已提供 FastAPI 骨架）

- `app/api/main.py`：FastAPI 应用入口（**对外只保留 `/pipeline/run` 作为统一入口**）
- `app/api/schemas.py`：DAG 配置与执行请求/响应模型

### 已包含接口（目标状态）

- `GET /health`：健康检查
- `POST /pipeline/run`：统一入口，按 DAG 配置执行流程

## 可配置管线（建议设计）

> 说明：该流程包含多分支与条件判断，建议采用 **DAG/任务编排** 作为设计框架。
> 节点实现统一放在 `app/pipeline/nodes/*`，不再使用 `app/api/pipeline.py`。
> **字幕下载与视频下载解耦**：URL 场景优先尝试字幕；视频只在需要抽音频/抽帧时再下载或拉流。

### DAG/任务编排设计（详细思路）

#### 设计目标

- 可配置：流程由配置文件定义，支持分支与跳转。
- 可扩展：新增节点不影响已有逻辑。
- 可观测：每个节点输入/输出/耗时/失败原因可追踪。
- 可复用：URL 流程与本地视频流程复用大部分节点。
- 可并发：允许并行执行可独立节点（如字幕下载与抽音频）。

#### 核心概念

- Node：单一职责处理步骤（输入 `Context` 输出 `Context`）。
- Edge：节点依赖关系（有向边）。
- Condition：决定分支走向（`when(ctx) -> bool`）。
- DAG：由节点 + 条件边构成。

#### Context（建议字段）

- `source_type`: `url | local`
- `source_url`
- `video_path`
- `subtitle_path`
- `audio_path`
- `video_duration`（来自元数据/时长探测）
- `subtitle_valid`
- `subtitle_coverage_ratio`
- `audio_rms`
- `transcript_token_count`
- `is_silent`
- `frames_paths`
- `summary_text`
- `trace`（节点执行轨迹）

#### 节点划分（建议）

输入类：
- `InputNode`（统一入口，写入 `source_type` / `source_url` / `video_path`）
- `DownloadVideoNode`（URL **按需**下载）
- `UploadLocalNode`（本地上传）
- `FetchMetadataNode`（URL/本地时长探测、元数据获取）

字幕相关：
- `DownloadSubtitleNode`
- `ParseSubtitleNode`
- `ValidateSubtitleNode`

音频相关：
- `ExtractAudioNode`
- `DetectSilenceNode`

ASR/转录：
- `TranscribeNode`
- `SubtitleFromASRNode`

视觉理解（VLM）：
- `SampleFramesNode`
- `VlmSummarizeNode`

总结生成（LLM）：
- `TextSummarizeNode`
- `MergeSummaryNode`
- `ChunkedSummarizeNode`（长文本分块总结，可配置块大小）

#### 条件与分支（示例）

URL 流程：
- 下载字幕 → 解析字幕 → 校验字幕（**不依赖先下载视频**）
  - 若有效：直接总结
  - 若无效/无字幕：按需下载/拉流 → 抽音频 → 转录 → 无声判断

无声判断：
- `audio_rms < threshold` 或 `transcript_token_count / duration < threshold`
- 若无声：抽帧 → VLM 总结 → 合并总结
- 否则：文本总结

本地视频流程：
- 跳过下载，直接抽音频 → 转录 → 无声判断（通过 `source_type` 条件分支落地）

#### DAG 配置建议（YAML/JSON）

```yaml
nodes:
  - id: input
    type: InputNode
  - id: fetch_metadata
    type: FetchMetadataNode
  - id: download_subtitle
    type: DownloadSubtitleNode
  - id: upload_local
    type: UploadLocalNode
  - id: download_video
    type: DownloadVideoNode
  - id: parse_subtitle
    type: ParseSubtitleNode
  - id: validate_subtitle
    type: ValidateSubtitleNode
  - id: extract_audio
    type: ExtractAudioNode
  - id: transcribe
    type: TranscribeNode
  - id: detect_silence
    type: DetectSilenceNode
  - id: sample_frames
    type: SampleFramesNode
  - id: vlm_summary
    type: VlmSummarizeNode
  - id: text_summary
    type: TextSummarizeNode
  - id: merge_summary
    type: MergeSummaryNode

edges:
  - source: input
    target: fetch_metadata
    condition: "source_type in ['url','local']"
  - source: input
    target: download_subtitle
    condition: "source_type == 'url'"
  - source: input
    target: upload_local
    condition: "source_type == 'local'"
  - source: download_subtitle
    target: parse_subtitle
  - source: fetch_metadata
    target: validate_subtitle
  - source: parse_subtitle
    target: validate_subtitle
  - source: validate_subtitle
    target: text_summary
    condition: "subtitle_valid == true"
  - source: validate_subtitle
    target: download_video
    condition: "subtitle_valid == false and source_type == 'url'"
  - source: validate_subtitle
    target: extract_audio
    condition: "subtitle_valid == false and source_type == 'local'"
  - source: download_video
    target: extract_audio
  - source: extract_audio
    target: transcribe
  - source: transcribe
    target: detect_silence
  - source: detect_silence
    target: text_summary
    condition: "is_silent == false"
  - source: detect_silence
    target: sample_frames
    condition: "is_silent == true"
  - source: sample_frames
    target: vlm_summary
  - source: vlm_summary
    target: merge_summary
```

#### 执行模型（建议）

- 拓扑排序执行
- 支持并行节点（无依赖节点并发）
- 支持短路（已拿到最终总结时终止无关节点）
- 每个节点生成 `trace` 记录（耗时/异常/输出摘要）

#### 可靠性与缓存

- 节点级缓存：相同输入可复用（字幕解析、VLM、转录等）
- 失败重试：外部 API 节点支持重试策略
- 幂等性：节点输出可重复计算，不影响全局结果

#### 长文本总结策略（新增设计）

> 适配“字幕很长”的场景，避免仅截断前 8000 字符。

设计思路：
- 将 `asr_data` 拼接文本按块切分，逐块调用 LLM 生成 **chunk summary**。
- 最后对所有 chunk summary 做一次 **merge summary**（可复用 `MergeSummaryNode` 或在 `TextSummarizeNode` 内部完成）。
- **分块大小可配置**，通过节点参数传入（例如 `chunk_size_chars`）。

建议参数：
- `chunk_size_chars`：单块最大字符数（必配）
- `chunk_overlap_chars`：相邻块重叠字符数（可选，默认 0）
- `chunk_max_count`：最大块数（可选，防止极端超长）
- `merge_prompt`：合并总结提示词（可选）

可选落地方式：
1) 在 `TextSummarizeNode` 内部实现“分块 → 合并”逻辑（单节点）
2) 新增 `ChunkedSummarizeNode` 专职分块；输出 `chunk_summaries`，由 `MergeSummaryNode` 合并（双节点）

#### 可观测性

- `trace`：节点执行日志
- 统一日志结构：`node_id` / `status` / `elapsed_ms` / `error`

### 业务分支规则（摘要）

1) 网址输入（URL）
- 优先下载字幕并校验有效性
- 字幕有效：直接 LLM 总结
- 字幕无效：按需下载/拉流 → 抽音频 → 转录 → 无声判断
- 无声：VLM 抽帧总结 → 合并总结

2) 本地视频（Upload）
- 跳过下载，直接抽音频 → 转录 → 无声判断
- 无声：VLM 抽帧总结 → 合并总结

### 关键判定建议（可配置）

- 字幕有效性：
  - `coverage_ratio = subtitle_time_span / video_duration`
  - `coverage_ratio >= 0.8` 为有效（默认值，可配置）
  - 可叠加字幕密度/字数阈值，避免“覆盖率够但内容过少”
- 无声视频判定：
  - `audio_rms < threshold` 或 `transcript_token_count / duration < threshold`
  - 阈值建议做成配置项，按内容类型可调整

### 建议新增/扩展接口

- `POST /pipeline/run`：**对外单入口**，按 DAG 配置执行
- `POST /vlm/summarize` / `POST /llm/summarize`：如需独立调试可作为**内网/内部服务**保留；不对外公开则仅作为节点内部调用
- `POST /uploads`：本地文件上传（前端先上传再触发流程）
- `GET /pipeline/run/{run_id}`：执行状态查询（轮询）
- `GET /pipeline/run/{run_id}/events`：进度事件流（SSE，可选）

### 新增设计（优先级：上传 > 异步/进度）

> 执行入口仍统一为 `/pipeline/run`（或现有 `/pipeline/auto/*`），
> `/uploads` 与 `/pipeline/run/{run_id}` 为前端配套能力，不改变主入口定位。

#### 1) 本地文件上传（优先）

前端无法直接传递本机路径给服务端，本地流程需先上传文件并拿到服务端可引用的 `file_id`。

**接口**
```
POST /uploads
Content-Type: multipart/form-data
```

**请求体（multipart）**
- `file`: 单文件（视频 / 音频 / 字幕）

**响应（建议）**
```json
{
  "file_id": "f_abc123",
  "original_name": "video.mp4",
  "size": 12345678,
  "mime_type": "video/mp4",
  "stored_path": "/work-dir/uploads/f_abc123/video.mp4"
}
```

> 对外可不返回 `stored_path`，仅返回 `file_id`（推荐）；服务端内部通过 `file_id` 解析真实路径。

**实现要点**
- 文件类型白名单（视频/音频/字幕），扩展名 + MIME 双校验。
- 文件大小上限与前端一致（统一配置）。
- 统一存储目录（建议 `WORK_PATH/uploads/`），避免 `/tmp` 丢失。
- 安全处理文件名与路径，防目录穿越。
- 过期清理策略（TTL / 定时任务）。

**与流程的衔接**
- `POST /pipeline/auto/local` 支持 `video_file_id` / `audio_file_id` / `subtitle_file_id`
  或统一 `file_id` + `file_type`，由后端解析为 `video_path/subtitle_path/audio_path`。

#### 2) 执行监控（异步与进度更新）

前端需要轮询或订阅执行状态，最小要求是轮询。

**轮询接口**
```
GET /pipeline/run/{run_id}
```

**响应（示例）**
```json
{
  "run_id": "r_abc123",
  "status": "running",
  "summary_text": null,
  "context": {"source_type": "url"},
  "trace": [
    {"node_id": "input", "status": "completed", "elapsed_ms": 120}
  ],
  "updated_at": "2026-01-31T10:20:30Z"
}
```

**最小落地**
- `POST /pipeline/auto/*` 返回 `run_id + status=running`，后台异步执行。
- 运行态存储（内存/Redis/DB），支持 `run_id -> status/trace/summary` 查询。

**可选增强（SSE）**
```
GET /pipeline/run/{run_id}/events
```
事件字段建议包含：`run_id`、`event_type`（trace_update/status_update/completed/failed）、`payload`。

## DAG 实现中的复用点与必要改动（避免重复造轮子）

### 可直接复用（无需修改）

- **ASR 转录入口**：`app/core/asr/transcribe.py::transcribe()`
  负责 ASR 模型选择与执行，是 `TranscribeNode` 的核心调用。
- **字幕数据结构与解析**：`app/core/asr/asr_data.py::ASRData`
  提供 `from_subtitle_file()` / `to_json()` 等，供 `ParseSubtitleNode` / 输出使用。
- **音视频工具**：`app/core/utils/video_utils.py::video2audio()`
  抽音频逻辑直接复用，用于 `ExtractAudioNode`。
- **LLM 调用封装**：`app/core/llm/client.py::call_llm()`
  作为 `TextSummarizeNode` 的统一 LLM 接口。
- **缓存与日志**：`app/core/utils/cache.py`、`app/core/utils/logger.py`
  节点结果缓存与 trace 记录可直接复用。
- **翻译/优化模块**（可选节点）：`app/core/translate/*`、`app/core/optimize/*`

### 需要迁移/改造（从 UI/线程抽离）

- **下载视频/字幕逻辑**
  现有实现集中在 `app/thread/video_download_thread.py`（含 PyQt 信号）。
  需要将 **下载逻辑抽成纯函数** 或重写为 `DownloadVideoNode` / `DownloadSubtitleNode`。
  *注意：不能直接复用 `QThread` 类。*

- **转录流程编排**
  现有流程在 `app/thread/transcript_thread.py`（含 PyQt 信号）。
  需要把“临时音频 → 转录 → 保存”的编排迁移为 `TranscribeNode` 内部逻辑。

- **配置路径与资源**
  `app/config.py` 含 UI 资源路径与目录创建逻辑。
  建议保留核心路径（`APPDATA_PATH`/`MODEL_PATH`/`WORK_PATH`），
  删除或弱化 UI 资源相关常量（字体/样式）以避免无效依赖。

### 新增实现（原项目没有的）

- **DAG 编排层**：`PipelineGraph` / `PipelineRunner` / `NodeRegistry`
  原项目没有 DAG 执行机制，需要新增。
- **条件评估与阈值规则**
  字幕有效性、无声判断等需要可配置的规则执行器。
- **VLM 抽帧与视觉摘要**
  抽帧节点 + VLM 摘要节点，需要新实现或接入现有服务。

### 复用优先级建议

1. 直接复用 `transcribe()` / `ASRData` / `video2audio()`
2. 抽离线程类中的“业务逻辑”（下载、转录编排）
3. 新增 DAG 编排与条件系统
4. 最后接入 VLM 与总结节点

## 建议的删除与保留清单

### 删除（UI + Qt 相关）

目录级：
- `app/view/`
- `app/components/`
- `resource/`（仅 UI 资源，如字体/图标/样式。若字幕样式仍需，保留 `resource/subtitle_style`）
- `main.py`（Qt 入口）

代码级（Qt 线程）：
- `app/thread/`（包含 `QThread`、UI 事件信号）

依赖级（pyproject.toml）：
- `PyQt5`
- `PyQt-Fluent-Widgets`

### 保留（后端核心能力）

- `app/core/asr/`：转录
- `app/core/translate/`：翻译
- `app/core/optimize/`：优化
- `app/core/split/`：断句
- `app/core/utils/`：ffmpeg/缓存/日志
- `app/core/llm/`：LLM 统一调用
- `app/core/entities.py`：数据结构
- `app/config.py`：路径/环境配置（注意：包含 UI 资源路径，但可保留）

## 具体整改步骤（建议顺序）

1. **新增后端入口**
   - 入口：`app/api/main.py`
   - 运行方式：`uvicorn app.api.main:app --host 0.0.0.0 --port 8000`

2. **移除 Qt/UI 目录**
   - 删除 `app/view/`、`app/components/`、`app/thread/`
   - 删除 `main.py` 或仅保留但不再使用

3. **清理依赖**
   - 在 `pyproject.toml` 中移除 `PyQt5` 和 `PyQt-Fluent-Widgets`
   - 新增 FastAPI/uvicorn 依赖：
     - `fastapi>=0.110`
     - `uvicorn>=0.23`
     - `python-multipart>=0.0.9`（上传文件）

4. **调整配置路径**
   - `app/config.py` 中包含 UI 资源路径（`resource/`）。如果删掉 `resource/`，需要：
     - 删除对 `SUBTITLE_STYLE_PATH` / `FONTS_PATH` 的引用
     - 或保留 `resource/subtitle_style` 以兼容字幕保存

5. **替换 UI 线程逻辑**
   - 不再使用 `app/thread/*`
   - 统一通过 `app/pipeline/*` 的 DAG 编排与节点调用

6. **测试关键流程**
   - 下载 → 抽音频 → 转录
   - 直接解析字幕文件

## 项目结构调整清单 + 文件职责说明

### 结构调整清单（建议）

新增目录与文件（DAG 编排层）：
- `app/pipeline/context.py`：定义 `PipelineContext`，统一上下文数据结构
- `app/pipeline/node_base.py`：定义 `PipelineNode` 抽象基类
- `app/pipeline/nodes/`：节点实现集合
  - `download.py`：下载相关节点（URL/字幕）
  - `subtitle.py`：字幕解析与校验节点
  - `audio.py`：抽音频、静音检测节点
  - `asr.py`：转录节点
  - `vlm.py`：多帧抽取与视觉摘要节点
  - `summarize.py`：LLM 总结/合并节点
- `app/pipeline/conditions.py`：条件函数库（`subtitle_valid`、`is_silent` 等）
- `app/pipeline/graph.py`：`PipelineGraph`（DAG 结构定义）
- `app/pipeline/runner.py`：`PipelineRunner`（执行器：拓扑排序 + 分支 + 短路 + trace）
- `app/pipeline/registry.py`：节点注册表（节点名 → 类映射）
- `app/pipeline/config_loader.py`：读取 YAML/JSON → `PipelineGraph`

API 层新增/调整：
- `app/api/main.py`：新增 `POST /pipeline/run`
- `app/api/schemas.py`：新增 DAG 配置/执行请求/响应模型
- `app/api/pipeline.py`：删除（节点逻辑迁移到 `app/pipeline/nodes/*`）

### 文件职责说明（核心）

- `app/pipeline/context.py`
  - 统一保存视频/字幕/音频/指标/trace 等字段，作为 DAG 全局状态
- `app/pipeline/node_base.py`
  - 所有节点的抽象基类，统一 `run(ctx)` 接口
- `app/pipeline/nodes/*`
  - 每个文件只负责一类节点逻辑，保持单一职责
- `app/pipeline/graph.py`
  - 只关心 DAG 数据结构（节点、边、条件）
- `app/pipeline/runner.py`
  - 负责执行：依赖解析、条件分支、并行调度、短路终止
- `app/pipeline/registry.py`
  - 集中管理节点名称到类的映射，便于配置驱动
- `app/pipeline/config_loader.py`
  - 将 YAML/JSON 配置解析成 `PipelineGraph`
- `app/api/main.py`
  - 仅负责请求入口与结果返回，不做业务逻辑


## 迁移后的目录结构（推荐）

```
app/
  api/
    main.py
    schemas.py
  core/
  config.py
  common/
  ...
```

## 注意事项

- `video2audio()` 依赖系统 `ffmpeg`，部署机器必须可调用。
- Whisper 本地模型路径/工具路径仍使用 `app/config.py` 的 `APPDATA_PATH`/`BIN_PATH`。
- yt-dlp 下载依赖网络，建议部署时配置代理/证书。

## 可选增强

- 把转录结果存数据库、对象存储
- 加任务队列（Celery/RQ）支持长视频
- 增加鉴权、速率限制、上传大小限制
