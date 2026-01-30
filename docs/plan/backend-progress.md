# 后端化整改进度文档（4 个阶段）

结论：按"风险/依赖递增"的节奏，拆成 4 个阶段最合适。每阶段都有可验收的成果，避免一次性大改。

时间单位：以工作日估算，实际可按人力缩放。

## 设计原则（针对本次整改）

1. 本次为全新后端设计，不需要兼容历史用户数据/配置；仅需要适配 `app/core` 中的现有代码能力。
2. “new” 之类的命名没有必要；在明确只支持新结构的前提下，这类命名是多余且易产生歧义，应使用中性命名。

## 阶段 1：准备与清理 ✅ 已完成

**状态：已完成**
**完成日期：2026-01-30**

目标：建立后端运行骨架，移除 UI/Qt 依赖，为后续改造清障。

### 完成内容

#### 1. 清理依赖（pyproject.toml）
- [x] 移除 `PyQt5==5.15.11`
- [x] 移除 `PyQt-Fluent-Widgets==1.8.4`
- [x] 移除 Qt 平台特定配置（`tool.uv.environments`、`override-dependencies`）
- [x] 移除 Qt classifiers（`Environment :: X11 Applications :: Qt`）
- [x] 新增后端依赖：`fastapi>=0.110`、`uvicorn>=0.23`、`python-multipart>=0.0.9`、`pyyaml>=6.0`
- [x] 更新 CLI 入口：`videocaptioner-api = "app.api.main:run_server"`

#### 2. 保留/确认 FastAPI 入口
- [x] `app/api/main.py`：健康检查端点 `GET /health` 正常
- [x] 添加 `run_server()` 函数支持 CLI 启动
- [x] `app/api/schemas.py`：无 Qt 依赖

#### 3. 新增后端专用配置模块
- [x] `app/api/config.py`：纯 Python 实现的配置管理
  - 使用 dataclass 替代 Qt 的 QConfig
  - 支持从 JSON 文件加载配置（兼容原有 settings.json 格式）
  - 支持环境变量覆盖（如 `OPENAI_API_KEY`）
  - 提供 `get_config()` 单例接口

#### 4. 弱化 UI 资源路径（app/config.py）
- [x] 核心路径保留：`APPDATA_PATH`、`WORK_PATH`、`MODEL_PATH`、`CACHE_PATH`、`LOG_PATH`
- [x] UI 资源路径标记为可选：`FONTS_PATH`、`TRANSLATIONS_PATH`、`ASSETS_PATH`
- [x] 移除 VLC 环境变量设置
- [x] BIN_PATH 检查存在性后再添加到 PATH

#### 5. 删除 UI 相关目录和文件
已删除：
- `app/view/`：UI 界面（11 个文件）
- `app/components/`：UI 组件（15 个文件）
- `app/common/`：Qt 配置和信号总线
- `main.py`：Qt 入口
- `resource/assets/`：UI 图标/图片
- `resource/translations/`：UI 多语言文件
- `resource/fonts/`：UI 字体文件
- `scripts/run.bat`、`scripts/run.sh`：Qt 启动脚本
- `scripts/trans-*.sh`、`scripts/translate_llm.py`：Qt 翻译工具

保留作为迁移参考：
- `app/thread/`：Qt 线程（10 个文件），阶段3迁移到 pipeline nodes
- `app/core/task_factory.py`：任务工厂（已注释 Qt 导入），阶段3迁移参考

保留使用：
- `resource/subtitle_style/`：字幕样式模板

### 验收结果
- [x] ✅ `uvicorn app.api.main:app` 启动成功
- [x] ✅ `curl http://127.0.0.1:8765/health` 返回 `{"status":"ok","version":"0.1.0"}`
- [x] ✅ `uv sync` 不再安装 PyQt5 相关包

### 核心模块状态
- `app/core/`：无 Qt 依赖，可直接复用
- `app/api/`：后端 API 层，已就绪

---

## 阶段 2：DAG 编排层落地 ✅ 已完成

**状态：已完成**
**完成日期：2026-01-30**

目标：建立可配置管线的"骨架"，具备最小可执行能力（串行+条件分支），使用 mock 节点验证。

### 完成内容

#### 1. 新增 app/pipeline/ 目录
```
app/pipeline/
├── __init__.py
├── context.py        # PipelineContext 上下文
├── node_base.py      # PipelineNode 抽象基类
├── condition.py      # ConditionEvaluator 条件评估
├── graph.py          # PipelineGraph DAG 结构
├── registry.py       # NodeRegistry 节点注册表
├── runner.py         # PipelineRunner 执行器
└── nodes/
    ├── __init__.py
    └── mock.py       # 8 个 Mock 节点
```

#### 2. 核心类实现
- [x] **PipelineContext**：管线执行上下文，承载全局状态
  - 字段：run_id, source_type, video_path, subtitle_valid, is_silent, summary_text 等
  - 方法：from_inputs(), add_trace(), to_dict(), to_eval_namespace()
- [x] **PipelineNode**：抽象基类，统一节点接口
  - 方法：run(ctx), get_output_keys()
- [x] **PipelineGraph**：DAG 结构解析
  - 方法：topological_sort(), get_predecessors(), get_successors()
  - 循环依赖检测（DFS）
- [x] **PipelineRunner**：按拓扑顺序执行节点
  - 条件分支评估（前驱边条件）
  - trace 记录（node_id, status, elapsed_ms, error, output_keys）
- [x] **NodeRegistry**：节点类型到类的映射
  - 单例模式 get_default_registry()
- [x] **ConditionEvaluator**：安全的条件表达式评估
  - 基于 AST 解析，禁止危险操作
  - 白名单变量：source_type, subtitle_valid, is_silent 等

#### 3. Mock 节点（8个）
| 节点类型 | 输出字段 |
|---------|---------|
| InputNode | source_type |
| FetchMetadataNode | video_duration |
| DownloadSubtitleNode | subtitle_path |
| ValidateSubtitleNode | subtitle_valid, subtitle_coverage_ratio |
| ExtractAudioNode | audio_path |
| TranscribeNode | transcript_token_count |
| DetectSilenceNode | is_silent, audio_rms |
| TextSummarizeNode | summary_text |

#### 4. API 端点更新
- [x] `app/api/main.py`：实现 `/pipeline/run` 端点
  - 解析 PipelineRunRequest
  - 构建 PipelineGraph 和 PipelineContext
  - 创建 PipelineRunner 执行
  - 返回 PipelineRunResponse（含 trace）

#### 5. 测试文档
- [x] `docs/dev/pipeline-testing.md`：服务管理和测试用例

### 验收结果
- [x] ✅ 简单 DAG 能跑通（mock 节点）
- [x] ✅ 条件分支正确执行/跳过
- [x] ✅ trace 结构完整（node_id, status, elapsed_ms, output_keys）
- [x] ✅ 循环依赖能检测并报错

### 风险与缓解
- 并发/短路先不做，留到阶段 4

---

## 阶段 3：核心节点迁移与流程贯通 ✅ 已完成

**状态：已完成**
**完成日期：2026-01-30**

目标：满足"URL 字幕优先 / 本地跳过下载 / 无声判断"的业务闭环。

### 完成内容

#### 1. 新增核心节点实现 `app/pipeline/nodes/core.py`

| 节点类型 | 复用模块 | 输出字段 |
|---------|---------|---------|
| InputNode | - | source_type |
| FetchMetadataNode | `video_utils.get_video_info()` / yt-dlp | video_duration |
| DownloadSubtitleNode | yt-dlp | subtitle_path |
| DownloadVideoNode | yt-dlp | video_path |
| ParseSubtitleNode | `ASRData.from_subtitle_file()` | asr_data, subtitle_segment_count |
| ValidateSubtitleNode | - | subtitle_valid, subtitle_coverage_ratio |
| ExtractAudioNode | `video_utils.video2audio()` | audio_path |
| TranscribeNode | `asr.transcribe()` | transcript_token_count, asr_data |
| DetectSilenceNode | - | is_silent, audio_rms |
| TextSummarizeNode | `llm.client.call_llm()` | summary_text |
| SampleFramesNode | (阶段4) | frames_paths |
| VlmSummarizeNode | (阶段4) | vlm_summary |
| MergeSummaryNode | (阶段4) | summary_text |

#### 2. 更新节点注册表
- [x] `app/pipeline/registry.py`：注册 13 个节点类型
- [x] `app/pipeline/nodes/__init__.py`：导出核心节点

#### 3. 新增测试用例 `tests/test_pipeline/`
```
tests/test_pipeline/
├── __init__.py
├── conftest.py         # 共享 fixtures
├── test_nodes.py       # 节点单元测试（19 个）
└── test_pipeline_run.py # 流程集成测试（10 个）
```

#### 4. 测试覆盖
- [x] InputNode：输入验证（5 个测试）
- [x] ParseSubtitleNode：SRT 解析（3 个测试）
- [x] ValidateSubtitleNode：覆盖率校验（3 个测试）
- [x] DetectSilenceNode：静音检测（2 个测试）
- [x] PipelineGraph：拓扑排序、循环检测（3 个测试）
- [x] PipelineRunner：条件分支执行/跳过（4 个测试）
- [x] 本地视频流程：跳过下载节点（1 个测试）
- [x] URL 字幕优先流程：有效字幕跳过视频下载（1 个测试）
- [x] 阈值配置：自定义覆盖率阈值（1 个测试）

### 验收结果
- [x] ✅ 29 个测试全部通过
- [x] ✅ URL：字幕有效时不下载视频
- [x] ✅ Local：不触发下载节点
- [x] ✅ 条件分支正确执行/跳过

### 待阶段4完成
- VLM 抽帧与视觉总结节点（已预留占位）
- 并发执行与短路策略

---

## 阶段 4：增强与稳定化
目标：提升可靠性与可观测性，接入可选能力。
范围/任务：
- VLM 抽帧与视觉总结节点（可选/可开关）
- 长字幕分块总结（可配置分块大小），分块摘要合并策略
- 节点缓存、失败重试、幂等性策略
- 并发执行与短路策略
- 关键测试样例与文档完善
交付物：
- 稳定的可配置后端引擎
- 流程文档与示例配置
验收标准：
- 关键路径有测试或可复现实例
- trace 明确，失败可定位
风险与缓解：
- 外部服务不稳定：降级路径与重试

里程碑建议
- M1：服务可跑 + 清理完成（阶段 1 结束）
- M2：DAG 执行器可用（阶段 2 结束）
- M3：URL/本地主流程贯通（阶段 3 结束）
- M4：增强与稳定（阶段 4 结束）
