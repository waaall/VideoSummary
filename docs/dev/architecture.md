# 架构设计

VideoCaptioner 的系统架构设计。

## 技术栈

- **ASR 引擎**: Whisper (FasterWhisper/WhisperCpp)
- **LLM 集成**: OpenAI/DeepSeek/Gemini/Ollama 等
- **视频处理**: FFmpeg

## 核心模块

### 1. ASR 模块 (`app/core/asr/`)

语音识别模块，支持多种 ASR 引擎。

### 2. 字幕处理模块 (`app/core/split/`, `app/core/optimize/`)

字幕分割和优化模块，使用 LLM 进行智能处理。

### 3. 翻译模块 (`app/core/translate/`)

字幕翻译模块，支持多种翻译服务。

## 数据流

```
视频/音频 → ASR → ASRData → 分割 → 优化 → 翻译 → 字幕文件 → 视频合成
```

详细架构说明请参考 `CLAUDE.md` 文件。

---

相关文档：
- [API 文档](/dev/api)
- [贡献指南](/dev/contributing)
