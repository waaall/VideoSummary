# URL -> 字幕 -> 总结 测试指南

本文说明如何验证“URL 字幕优先”流程，并给出 API 手动测试与 pytest 自动化测试方法。

## 范围

- 仅 URL 输入
- 字幕下载 -> 解析 -> 校验 -> 总结
- 手动 API 测试与自动化测试

## 前置条件

- 安装依赖：`uv sync`
- 启动服务：`uvicorn app.api.main:app --reload --port 8765`
- `TextSummarizeNode` 需要 LLM 环境变量：
  - `OPENAI_BASE_URL`
  - `OPENAI_API_KEY`
  - 可选：`LLM_MODEL`
- 若目标站点需要登录，请把 cookies 放在 `AppData/cookies.txt`
- 使用**确实有字幕**的视频 URL

## 流程（字幕优先）

推荐节点顺序：

1) `InputNode`
2) `DownloadSubtitleNode`
3) `ParseSubtitleNode`
4) `FetchMetadataNode`（用于计算覆盖率）
5) `ValidateSubtitleNode`
6) `TextSummarizeNode`（仅当 `subtitle_valid == True`）

说明：
- `ValidateSubtitleNode` 依赖 `video_duration` 计算覆盖率；若缺失，会默认字幕有效。
- `TextSummarizeNode` 需要 LLM 环境变量，否则会报错。

## 手动 API 测试

健康检查：

```bash
curl -s http://127.0.0.1:8765/health | python -m json.tool
```

运行字幕优先管线：

```bash
curl -s -X POST http://127.0.0.1:8765/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline": {
      "version": "v1",
      "nodes": [
        {"id": "input", "type": "InputNode", "params": {}},
        {"id": "download_sub", "type": "DownloadSubtitleNode", "params": {}},
        {"id": "parse", "type": "ParseSubtitleNode", "params": {}},
        {"id": "meta", "type": "FetchMetadataNode", "params": {}},
        {"id": "validate", "type": "ValidateSubtitleNode", "params": {}},
        {"id": "summary", "type": "TextSummarizeNode", "params": {"max_tokens": 800}}
      ],
      "edges": [
        {"source": "input", "target": "download_sub"},
        {"source": "download_sub", "target": "parse"},
        {"source": "input", "target": "meta"},
        {"source": "parse", "target": "validate"},
        {"source": "meta", "target": "validate"},
        {"source": "validate", "target": "summary", "condition": "subtitle_valid == True"}
      ]
    },
    "inputs": {
      "source_type": "url",
      "source_url": "https://www.bilibili.com/video/BV1iApwzBEqZ/"
    }
  }' | python -m json.tool
```

期望结果：
- `status` 为 `completed`
- `summary_text` 非空
- `context.subtitle_valid` 为 `true`
- `trace` 包含 `download_sub`、`parse`、`validate`、`summary`

如果你希望跳过元数据（覆盖率），可移除 `meta` 节点及其边；此时 `ValidateSubtitleNode` 会在缺失时长时默认字幕有效。

## 自动流程 API 示例

### URL 自动流程（字幕优先）

```bash
curl -s -X POST http://127.0.0.1:8765/pipeline/auto/url \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "source_url": "https://www.bilibili.com/video/BV1iApwzBEqZ/"
    },
    "options": {
      "summary": {"max_tokens": 800},
      "transcribe_config": {
        "transcribe_model": "WHISPER_CPP",
        "whisper_model": "LARGE_V3_TURBO",
        "transcribe_language": "中文"
      }
    }
  }' | python -m json.tool
```

说明：
- 字幕有效时会直接总结；无效/无字幕时会走“下载视频 → 抽音频 → 转录 → 无声判断”分支。
- `transcribe_config` 可选；若省略则使用 `AppData/settings.json` 的默认转录配置。

### 本地自动流程（字幕/音频/视频）

字幕输入示例：

```bash
curl -s -X POST http://127.0.0.1:8765/pipeline/auto/local \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "subtitle_path": "/path/to/example.srt"
    }
  }' | python -m json.tool
```

说明：
- 传 `subtitle_path`：直接解析并总结。
- 传 `audio_path` 或 `video_path`：会执行转录流程，建议提供 `options.transcribe_config` 或配置好 `AppData/settings.json`。

## 自动化测试（不触发 LLM 外部调用）

运行全部 pipeline 测试：

```bash
uv run pytest tests/test_pipeline -v
```

聚焦 URL 字幕优先流程：

```bash
uv run pytest tests/test_pipeline/test_pipeline_run.py -k url_with_valid_subtitle_skips_video_download -v
```

该测试使用本地字幕夹具，并跳过 `TextSummarizeNode`，避免 LLM 与网络依赖。

## 排障

- `subtitle_path` 为空：目标 URL 可能无字幕；更换 URL 或提供 cookies。
- `summary_text` 为空或报错：检查 LLM 环境变量，并查看 `trace` 中 `TextSummarizeNode` 的错误信息。
- `status` 为 `failed`：查看 `trace[].error` 定位失败节点。
