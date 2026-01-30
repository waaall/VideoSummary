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

## 可用 Mock 节点

| 节点类型 | 参数 | 输出字段 |
|---------|------|---------|
| InputNode | - | source_type |
| FetchMetadataNode | mock_duration | video_duration |
| DownloadSubtitleNode | mock_path | subtitle_path |
| ValidateSubtitleNode | mock_valid, mock_coverage | subtitle_valid, subtitle_coverage_ratio |
| ExtractAudioNode | mock_path | audio_path |
| TranscribeNode | mock_tokens, mock_text | transcript_token_count |
| DetectSilenceNode | mock_silent, mock_rms | is_silent, audio_rms |
| TextSummarizeNode | mock_summary | summary_text |

## Python 单元测试

```python
from app.api.schemas import PipelineConfig, PipelineNodeConfig, PipelineEdgeConfig, PipelineInputs
from app.pipeline.graph import PipelineGraph, CyclicDependencyError
from app.pipeline.runner import PipelineRunner
from app.pipeline.context import PipelineContext

# 构建配置
config = PipelineConfig(
    version='v1',
    nodes=[
        PipelineNodeConfig(id='input', type='InputNode', params={}),
        PipelineNodeConfig(id='meta', type='FetchMetadataNode', params={'mock_duration': 600.0}),
        PipelineNodeConfig(id='summary', type='TextSummarizeNode', params={}),
    ],
    edges=[
        PipelineEdgeConfig(source='input', target='meta'),
        PipelineEdgeConfig(source='meta', target='summary'),
    ]
)

# 执行
graph = PipelineGraph(config)
inputs = PipelineInputs(source_type='local', video_path='/test.mp4')
ctx = PipelineContext.from_inputs(inputs)
runner = PipelineRunner(graph)
ctx = runner.run(ctx)

# 检查结果
print(ctx.summary_text)
print(ctx.video_duration)
for t in ctx.trace:
    print(f'{t.node_id}: {t.status}')
```
