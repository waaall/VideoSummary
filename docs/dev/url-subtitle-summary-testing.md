# URL -> 字幕 -> 总结 测试指南

本文说明如何验证“URL 字幕优先”流程，并给出 API 手动测试方法。

## 范围

- 仅 URL 输入
- 字幕下载 -> 解析 -> 校验 -> 总结
- 手动 API 测试与基础自动化测试

## 前置条件

- 安装依赖：`uv sync`
- 启动服务：`uvicorn app.api.main:app --reload --port 8765`
- `TextSummarizeNode` 需要 LLM 环境变量：
  - `OPENAI_BASE_URL`
  - `OPENAI_API_KEY`
  - 可选：`LLM_MODEL`
- 服务不会自动读取 `tests/.env`，需要显式加载（推荐）：
  - `uvicorn app.api.main:app --reload --port 8765 --env-file tests/.env`
  - 或先执行 `source tests/.env` 再启动
- 若目标站点需要登录，请把 cookies 放在 `AppData/cookies.txt`
- 使用**确实有字幕**的视频 URL

## 手动 API 测试

健康检查：

```bash
curl -s http://127.0.0.1:8765/health | python -m json.tool
```

创建摘要（URL）：

```bash
curl -s -X POST http://127.0.0.1:8765/summaries   -H "Content-Type: application/json"   -d '{
    "source_type": "url",
    "source_url": "https://www.bilibili.com/video/BV1iApwzBEqZ/"
  }' | python -m json.tool
```

拿到 `job_id` 后轮询任务状态：

```bash
curl -s http://127.0.0.1:8765/jobs/<job_id> | python -m json.tool
```

期望结果：
- `status` 为 `completed`
- `summary_text` 非空

## 自动化测试（轻量）

运行 API 基础测试：

```bash
uv run pytest tests/test_api/test_api_uploads.py -v
```

## 排障

- **只有 job_id，没有 summary_text**：任务尚未完成；继续轮询 `/jobs/<job_id>`。
- `summary_text` 为空或报错：检查 LLM 环境变量，并查看日志中 `TextSummarizeNode` 的错误信息。
- `status` 为 `failed`：查看 `jobs` 返回的 `error` 字段定位失败原因。
