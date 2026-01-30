# 后端化整改进度文档（4 个阶段）

结论：按"风险/依赖递增"的节奏，拆成 4 个阶段最合适。每阶段都有可验收的成果，避免一次性大改。

时间单位：以工作日估算，实际可按人力缩放。

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

## 阶段 2：DAG 编排层落地
目标：建立可配置管线的“骨架”，具备最小可执行能力。
范围/任务：
- PipelineContext / NodeBase / Graph / Runner / Registry / ConfigLoader
- 条件评估机制（subtitle_valid / is_silent / source_type）
- 单入口 /pipeline/run 读取 DAG 配置并执行
交付物：
- 可运行的 DAG 执行器（至少支持串行+条件分支）
- 请求/响应 schema 稳定
验收标准：
- 简单 DAG 能跑通（mock 节点即可）
- trace/日志记录结构可见
风险与缓解：
- 并发/短路先不做，留到阶段 4

## 阶段 3：核心节点迁移与流程贯通
目标：满足“URL 字幕优先 / 本地跳过下载 / 无声判断”的业务闭环。
范围/任务：
- 抽离下载/转录逻辑：从线程类迁移为节点
- 复用 transcribe() / ASRData / video2audio()
- 实现 FetchMetadataNode、DownloadSubtitleNode、ValidateSubtitleNode
- 实现 ExtractAudioNode / TranscribeNode / DetectSilenceNode
- 接入 TextSummarizeNode（LLM）
交付物：
- URL 与本地两条主流程可跑通
- 字幕优先与按需下载策略落地
验收标准：
- URL：字幕有效时不下载视频即可总结
- URL：字幕无效时走转录与无声判断
- Local：不触发下载节点
风险与缓解：
- 字幕有效性判定偏差：加密度/字数阈值

## 阶段 4：增强与稳定化
目标：提升可靠性与可观测性，接入可选能力。
范围/任务：
- VLM 抽帧与视觉总结节点（可选/可开关）
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
