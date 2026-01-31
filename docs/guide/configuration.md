# 配置指南

详细的配置选项说明。

## 全局配置

配置文件默认在：

- `AppData/settings.json`

服务启动后会读取该文件（`app/api/config.py`），未配置项会使用默认值。

## AppData 目录说明（跨平台）

`AppData` 是**项目根目录**下的子目录（不是 Windows 用户目录里的 AppData）。
所有平台路径一致，只是盘符/前缀不同：

- Windows: `C:\path\to\VideoSummary\AppData\settings.json`
- macOS: `/path/to/VideoSummary/AppData/settings.json`
- Linux: `/path/to/VideoSummary/AppData/settings.json`

该目录在启动时自动创建，常见内容包括 `settings.json`、`models`、`logs`、`cache`。

### 典型路径示例

假设你的项目在用户目录下：

- macOS: `/Users/<you>/Projects/VideoSummary/AppData/settings.json`
- Linux: `/home/<you>/Projects/VideoSummary/AppData/settings.json`
- Windows: `C:\Users\<you>\Projects\VideoSummary\AppData\settings.json`

模型目录固定为：

- `AppData/models`

## Whisper / ASR 配置

项目支持三种 Whisper 形式：

- **WhisperCpp**：本地 `whisper.cpp` CLI（可执行文件 + ggml 模型）
- **FasterWhisper**：本地 `faster-whisper`（或 `faster-whisper-xxl`）CLI
- **Whisper API**：远程 API（OpenAI 兼容）

关键配置项（`AppData/settings.json`）：

- `transcribe.model`: 选择引擎（`WHISPER_CPP` / `FASTER_WHISPER` / `WHISPER_API`）
- `transcribe.language`: 语种（如 `ENGLISH`、`CHINESE` 等）
- `whisper.model`: WhisperCpp 模型枚举（如 `TINY` / `BASE` / `SMALL` / `LARGE_V3_TURBO`）
- `whisper_api.api_base` / `whisper_api.api_key` / `whisper_api.model` / `whisper_api.prompt`
- `faster_whisper.program` / `faster_whisper.model` / `faster_whisper.model_dir` / `faster_whisper.device` / `faster_whisper.vad_*`

### WhisperCpp（本地）

- 可执行文件必须在 PATH 中，支持名称：`whisper-cli` 或 `whisper-cpp`
- 模型文件需放在 `AppData/models`，文件名匹配 `*ggml*{model}*.bin`

- [whisper.cpp model download](https://huggingface.co/ggerganov/whisper.cpp/tree/main)

示例：

```json
{
  "transcribe": { "model": "WHISPER_CPP", "language": "CHINESE" },
  "whisper": { "model": "BASE" }
}
```

### FasterWhisper（本地）

- 程序名会根据 `device` 自动选择并在 PATH 中查找：
  - `cpu`：优先 `faster-whisper-xxl`，否则 `faster-whisper`
  - `cuda`：要求 `faster-whisper-xxl`
- `faster_whisper.model_dir` 为空时，自动使用 `AppData/models`

示例：

```json
{
  "transcribe": { "model": "FASTER_WHISPER", "language": "CHINESE" },
  "faster_whisper": {
    "program": "faster-whisper-xxl",
    "model": "TINY",
    "device": "cuda",
    "model_dir": ""
  }
}
```

### Whisper API（远程）

示例：

```json
{
  "transcribe": { "model": "WHISPER_API", "language": "ENGLISH" },
  "whisper_api": {
    "api_base": "https://api.openai.com/v1",
    "api_key": "YOUR_KEY",
    "model": "whisper-1"
  }
}
```

## FFmpeg 配置

项目会直接调用 `ffmpeg`（抽音频、视频信息、字幕渲染等）。要求：

- `ffmpeg` 在 PATH 中可用
- 如果你使用项目内置的二进制，放在 `resource/bin` 下即可（启动时会自动加入 PATH）

可以用下面命令验证：

```bash
ffmpeg -version
```

## 跨平台无缝使用建议

- `settings.json` 放在项目内的 `AppData`，所有平台共用相同结构
- 尽量**不写死绝对路径**，模型放 `AppData/models`，`model_dir` 留空即可
- 二进制统一放 `resource/bin`（启动会自动加入 PATH），各平台只需替换对应可执行文件
- 如要同一份配置在 mac / Windows / Linux 都能跑，建议 `faster_whisper.device` 设为 `cpu`

## 高级配置

待补充...

---

更多配置细节，请参考：
- [LLM 配置](/config/llm)
- [ASR 配置](/config/asr)
- [翻译配置](/config/translator)
