# 流程框架设计（DAG Pipeline）

本文描述后端“流程框架”的设计目标、核心概念、数据模型与执行规则，并给出 URL / 本地视频的推荐流程模板。

> 该文档聚焦“框架设计与运行规则”，业务节点可逐步替换为真实实现。

## 目标与边界

- 目标：提供可配置的 DAG 执行框架，支持条件分支、可观测 trace，并能承载 URL 与本地视频两类主流程。
- 边界：框架不直接绑定业务实现，节点业务逻辑可按阶段替换（Mock → 真实节点）。

## 核心概念

- **Node（节点）**：最小执行单元，读取 `PipelineContext` 并写入输出字段。
- **Edge（边）**：节点依赖关系，可携带条件表达式。
- **Graph（图）**：由节点 + 边构成的有向无环图（DAG）。
- **Context（上下文）**：贯穿流程的全局状态与 trace。
- **Registry（注册表）**：节点类型名 → 节点类，用于实例化。

## 数据模型（Schema）

### PipelineConfig

- `version`: 配置版本（预留）
- `entrypoint`: 可选入口节点 ID
- `nodes`: 节点列表
- `edges`: 边列表（source → target）

### PipelineInputs

输入参数，主要包含：

- `source_type`: `url` | `local`
- `source_url`, `video_path`, `subtitle_path`, `audio_path`
- `extra`: 业务扩展字段（可选）

### PipelineThresholds

判定阈值（用于条件表达式）：

- `subtitle_coverage_min`
- `transcript_token_per_min_min`
- `audio_rms_max_for_silence`

### TraceEvent

每个节点执行会生成 trace：

- `node_id`, `status`, `elapsed_ms`
- `error`, `output_keys`

## 执行模型

1. 解析 `PipelineConfig` 生成 DAG，检测循环依赖。
2. 拓扑排序执行节点。
3. 每个节点执行前，依据入边条件判断是否执行：
   - 无前驱：执行
   - 前驱均跳过：跳过
   - 前驱已执行且存在任一条件满足（或无条件）：执行
4. 每个节点生成 trace 记录；节点异常会标记失败并返回部分结果。

### 条件表达式规则

- 表达式语法接近 Python（支持比较、布尔、算术、`in` 等）。
- 使用 **`True/False`**（大写）表示布尔常量。
- 可引用 `PipelineContext.to_eval_namespace()` 中的字段（含阈值与 `extra`）。

## 核心流程模板

### URL 流程（推荐）

1. 下载字幕 → 解析字幕 → 校验字幕（不依赖先下载视频）
2. 若字幕有效：直接文本总结
3. 若无效/无字幕：按需下载/拉流 → 抽音频 → 转录 → 无声判断

### 无声判断规则（推荐）

无声判定建议基于以下任一条件成立：

- `audio_rms <= audio_rms_max_for_silence`
- `transcript_token_count / video_duration < transcript_token_per_min_min`

### 长文本总结策略（推荐）

字幕很长时，单次提示会被截断；推荐采用“分块摘要 → 合并摘要”的方式。

建议策略：
- 按字符数切分 `asr_data` 拼接后的全文，逐块生成 **chunk summary**。
- 将所有 chunk summary 合并为最终摘要（可复用 `MergeSummaryNode`）。

建议参数（节点配置）：
- `chunk_size_chars`：单块最大字符数（必配）
- `chunk_overlap_chars`：相邻块重叠字符数（可选，默认 0）
- `chunk_max_count`：最大块数（可选）
- `merge_prompt`：合并总结提示词（可选）

落地方式：
1) 在 `TextSummarizeNode` 内部实现分块与合并（单节点）
2) 新增 `ChunkedSummarizeNode` 负责分块摘要，再由 `MergeSummaryNode` 合并（双节点）

### 字幕覆盖率计算（校验规则）

字幕覆盖率按“所有字幕片段时长求和 / 视频总时长”计算，避免用最早开始到最晚结束的跨度导致稀疏字幕被高估。

### URL 视频下载落地路径（实现细节）

当使用 yt-dlp 下载 URL 视频时，最终文件路径以 `requested_downloads[].filepath` 或 `prepare_filename` 返回值为准；如未命中，则回退扫描下载目录中常见视频格式文件。

### 本地视频流程（推荐）

1. 跳过下载，直接抽音频 → 转录 → 无声判断
2. 若无声：抽帧 → VLM 总结 → 合并总结
3. 否则：文本总结

## 条件分支示例（片段）

> 条件表达式示例使用 `True/False`。

```yaml
edges:
  - source: input
    target: download_subtitle
    condition: "source_type == 'url'"
  - source: input
    target: extract_audio
    condition: "source_type == 'local'"
  - source: validate_subtitle
    target: text_summary
    condition: "subtitle_valid == True"
  - source: detect_silence
    target: sample_frames
    condition: "is_silent == True"
```

## 可靠性与可观测性

- **trace**：每节点记录 `status/elapsed_ms/error/output_keys`，便于排查。
- **容错**：节点失败时仍返回上下文与 trace，保留可观测性。

## 后续扩展建议

- 并发执行无依赖节点
- 节点级缓存与失败重试
- 短路策略（已有最终结果时跳过后续）
