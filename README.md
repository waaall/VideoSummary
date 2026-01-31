# VideoSummary

AI-powered video captioning and summarization backend engine.

## Features

- ASR transcription (multiple backends: Whisper, FasterWhisper, JianYing, etc.)
- Subtitle parsing and validation
- LLM-based text summarization
- Configurable DAG pipeline

## Quick Start

```bash
# Install dependencies
uv sync

# Start API server
uvicorn app.api.main:app --reload --port 8765
```

## API Endpoints

- `GET /health` - Health check
- `POST /pipeline/run` - Run pipeline with DAG configuration

---

# Pipeline 服务测试指南

## 服务管理

### 启动服务

```bash
uvicorn app.api.main:app --reload --port 8765
```

### 关闭服务

```bash
pkill -f "uvicorn app.api.main:app"
```

### 重启服务

```bash
pkill -f "uvicorn app.api.main:app" || true
sleep 1
uvicorn app.api.main:app --reload --port 8765
```

## 测试用例

### 1. 健康检查

```bash
curl -s http://127.0.0.1:8765/health | python -m json.tool
```

### 2. 简单串行 DAG

```bash
curl -s -X POST http://127.0.0.1:8765/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline": {
      "version": "v1",
      "nodes": [
        {"id": "input", "type": "InputNode", "params": {}},
        {"id": "meta", "type": "FetchMetadataNode", "params": {}},
        {"id": "summary", "type": "TextSummarizeNode", "params": {}}
      ],
      "edges": [
        {"source": "input", "target": "meta"},
        {"source": "meta", "target": "summary"}
      ]
    },
    "inputs": {"source_type": "local", "video_path": "/test.mp4"}
  }' | python -m json.tool
```

### 3. 条件分支（URL 类型，条件满足）

```bash
curl -s -X POST http://127.0.0.1:8765/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline": {
      "version": "v1",
      "nodes": [
        {"id": "input", "type": "InputNode", "params": {}},
        {"id": "download_sub", "type": "DownloadSubtitleNode", "params": {}},
        {"id": "validate", "type": "ValidateSubtitleNode", "params": {"mock_valid": true}},
        {"id": "summary", "type": "TextSummarizeNode", "params": {}}
      ],
      "edges": [
        {"source": "input", "target": "download_sub", "condition": "source_type == '\''url'\''"},
        {"source": "download_sub", "target": "validate"},
        {"source": "validate", "target": "summary", "condition": "subtitle_valid == True"}
      ]
    },
    "inputs": {"source_type": "url", "source_url": "https://example.com/video.mp4"}
  }' | python -m json.tool
```

### 4. 条件分支（local 类型，条件不满足）

```bash
curl -s -X POST http://127.0.0.1:8765/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline": {
      "version": "v1",
      "nodes": [
        {"id": "input", "type": "InputNode", "params": {}},
        {"id": "download_sub", "type": "DownloadSubtitleNode", "params": {}},
        {"id": "validate", "type": "ValidateSubtitleNode", "params": {"mock_valid": true}},
        {"id": "summary", "type": "TextSummarizeNode", "params": {}}
      ],
      "edges": [
        {"source": "input", "target": "download_sub", "condition": "source_type == '\''url'\''"},
        {"source": "download_sub", "target": "validate"},
        {"source": "validate", "target": "summary", "condition": "subtitle_valid == True"}
      ]
    },
    "inputs": {"source_type": "local", "video_path": "/test.mp4"}
  }' | python -m json.tool
```

### 5. 循环依赖检测

```bash
curl -s -X POST http://127.0.0.1:8765/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline": {
      "version": "v1",
      "nodes": [
        {"id": "a", "type": "InputNode", "params": {}},
        {"id": "b", "type": "InputNode", "params": {}},
        {"id": "c", "type": "InputNode", "params": {}}
      ],
      "edges": [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "c"},
        {"source": "c", "target": "a"}
      ]
    },
    "inputs": {"source_type": "local", "video_path": "/test.mp4"}
  }' | python -m json.tool
```

预期返回 400 错误，提示循环依赖。

## 可用节点

| 节点类型 | 参数 | 输出字段 |
|---------|------|---------|
| InputNode | - | source_type |
| FetchMetadataNode | - | video_duration |
| DownloadSubtitleNode | work_dir | subtitle_path |
| DownloadVideoNode | work_dir | video_path |
| ParseSubtitleNode | - | asr_data, subtitle_segment_count |
| ValidateSubtitleNode | - | subtitle_valid, subtitle_coverage_ratio |
| ExtractAudioNode | audio_track_index | audio_path |
| TranscribeNode | config | transcript_token_count, asr_data |
| DetectSilenceNode | - | is_silent, audio_rms |
| TextSummarizeNode | model, max_tokens, prompt | summary_text |
| SampleFramesNode | - | frames_paths (阶段4) |
| VlmSummarizeNode | - | vlm_summary (阶段4) |
| MergeSummaryNode | - | summary_text (阶段4) |

## 运行测试

### 运行所有 Pipeline 测试

```bash
uv run pytest tests/test_pipeline/ -v
```

### 测试覆盖内容

```
tests/test_pipeline/
├── conftest.py          # 共享 fixtures
├── test_nodes.py        # 节点单元测试（19 个）
└── test_pipeline_run.py # 流程集成测试（10 个）
```

**节点测试**：
- `TestInputNode`：输入验证（source_type、url/local 校验）
- `TestParseSubtitleNode`：SRT 文件解析
- `TestValidateSubtitleNode`：字幕覆盖率校验
- `TestDetectSilenceNode`：静音检测（基于 tokens/min）
- `TestNodeOutputKeys`：节点输出字段验证

**流程测试**：
- `TestPipelineGraph`：DAG 拓扑排序、循环依赖检测
- `TestPipelineRunner`：条件分支执行/跳过、trace 记录
- `TestLocalVideoFlow`：本地视频跳过下载节点
- `TestURLSubtitlePriorityFlow`：URL 字幕有效时跳过视频下载
- `TestThresholdsConfiguration`：自定义阈值配置

### Python 单元测试示例

```python
from app.api.schemas import PipelineConfig, PipelineNodeConfig, PipelineEdgeConfig, PipelineInputs
from app.pipeline.graph import PipelineGraph
from app.pipeline.runner import PipelineRunner
from app.pipeline.context import PipelineContext
from app.pipeline.registry import get_default_registry

# 构建配置
config = PipelineConfig(
    version='v1',
    nodes=[
        PipelineNodeConfig(id='input', type='InputNode', params={}),
        PipelineNodeConfig(id='validate', type='ValidateSubtitleNode', params={}),
    ],
    edges=[
        PipelineEdgeConfig(source='input', target='validate'),
    ]
)

# 执行
graph = PipelineGraph(config)
registry = get_default_registry()
runner = PipelineRunner(graph, registry)

inputs = PipelineInputs(source_type='local', video_path='/test.mp4')
ctx = PipelineContext.from_inputs(inputs)
ctx = runner.run(ctx)

# 检查结果
print(f"subtitle_valid: {ctx.subtitle_valid}")
for t in ctx.trace:
    print(f'{t.node_id}: {t.status} ({t.elapsed_ms}ms)')
```

