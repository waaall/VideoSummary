# API 文档

VideoSummary 核心 API 接口文档。

## HTTP API 接口

### 健康检查

```http
GET /health
```

**响应**:
```json
{"status": "ok", "version": "0.1.0"}
```

---

### 管道执行

```http
POST /pipeline/run
```

执行自定义 DAG 管道，支持条件分支和拓扑排序。

**请求体**: `PipelineRunRequest`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pipeline` | `PipelineConfig` | 是 | DAG 管道配置 |
| `inputs` | `PipelineInputs` | 是 | 输入参数 |
| `thresholds` | `PipelineThresholds` | 否 | 执行阈值 |
| `options` | `Dict[str, Any]` | 否 | 额外选项 |

---

### URL 自动流程

```http
POST /pipeline/auto/url
```

URL 优先流程：优先下载字幕，失败则下载视频转录。

**请求体**:

```json
{
  "inputs": {
    "source_url": "https://www.youtube.com/watch?v=..."
  },
  "options": {
    "work_dir": "/tmp/downloads",
    "audio_track_index": 0,
    "summary": {
      "model": "gpt-3.5-turbo",
      "max_tokens": 500,
      "prompt": "..."
    },
    "transcribe_config": {}
  }
}
```

---

### 本地自动流程

```http
POST /pipeline/auto/local
```

支持本地字幕/音频/视频文件。

**请求体**:

```json
{
  "inputs": {
    "source_type": "local",
    "subtitle_path": "/path/to/subtitle.srt",
    "audio_path": "/path/to/audio.mp3",
    "video_path": "/path/to/video.mp4"
  }
}
```

---

## 数据模型

### PipelineInputs

```python
source_type: str          # "url" | "local"
source_url: Optional[str] # URL 模式必填
video_path: Optional[str] # 本地视频路径
subtitle_path: Optional[str]
audio_path: Optional[str]
extra: Dict[str, Any]     # 扩展字段
```

### PipelineThresholds

```python
subtitle_coverage_min: float = 0.8      # 字幕覆盖率阈值
transcript_token_per_min_min: float = 2.0
audio_rms_max_for_silence: float = 0.01 # 静音 RMS 阈值
```

### PipelineConfig

```python
version: str = "v1"
entrypoint: Optional[str]           # 入口节点 ID
nodes: List[PipelineNodeConfig]     # 节点列表
edges: List[PipelineEdgeConfig]     # 边列表
```

### PipelineRunResponse

```python
run_id: str                     # 执行 ID
status: str                     # "completed" | "failed"
summary_text: Optional[str]     # 摘要结果
context: Dict[str, Any]         # 执行上下文
trace: List[TraceEvent]         # 执行追踪
```

---

## ASR 模块

### transcribe()

```python
from app.core.asr import transcribe

result = transcribe(
    audio_path="video.mp4",
    config=TranscribeConfig(
        transcribe_model=TranscribeModelEnum.FASTER_WHISPER,
        transcribe_language="zh",
        need_word_time_stamp=True
    ),
    callback=lambda progress, msg: print(f"{progress}%: {msg}")
)
```

**参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `audio_path` | `str` | 音频文件路径 |
| `config` | `TranscribeConfig` | 转录配置 |
| `callback` | `Callable[[int, str], None]` | 进度回调 |

**返回**: `ASRData`

### TranscribeConfig

```python
class TranscribeConfig:
    # 基础配置
    transcribe_model: TranscribeModelEnum
    transcribe_language: str  # "zh", "en", ...
    need_word_time_stamp: bool = True

    # Whisper API
    whisper_api_key: Optional[str]
    whisper_api_base: Optional[str]
    whisper_api_model: str = "whisper-1"

    # FasterWhisper
    faster_whisper_model: FasterWhisperModelEnum
    faster_whisper_device: str = "cuda"
    faster_whisper_vad_filter: bool = True
    faster_whisper_vad_threshold: float = 0.5
```

### TranscribeModelEnum

| 值 | 说明 |
|----|------|
| `JIANYING` | 剪映接口 |
| `BIJIAN` | B 接口 |
| `WHISPER_API` | Whisper API |
| `FASTER_WHISPER` | FasterWhisper |
| `WHISPER_CPP` | WhisperCpp |

---

## ASRData 类

转录结果数据类。

### 工厂方法

```python
# 从文件加载
ASRData.from_subtitle_file("subtitle.srt")

# 从字符串解析
ASRData.from_srt(srt_string)
ASRData.from_vtt(vtt_string)
ASRData.from_ass(ass_string)
ASRData.from_json(json_data)
ASRData.from_youtube_vtt(vtt_string)
```

### 数据处理

```python
asr_data.has_data()              # 是否有数据
asr_data.is_word_timestamp()     # 是否词级时间戳
asr_data.split_to_word_segments() # 句级转词级
asr_data.remove_punctuation()    # 移除标点
asr_data.optimize_timing(1000)   # 优化时序
asr_data.merge_segments(0, 2)    # 合并片段
```

### 导出方法

```python
asr_data.to_srt("output.srt")
asr_data.to_ass("output.ass", style_str="...")
asr_data.to_vtt("output.vtt")
asr_data.to_lrc("output.lrc")
asr_data.to_txt("output.txt")
asr_data.to_json()
asr_data.save("output.srt")  # 自动识别格式
```

### ASRDataSeg

```python
class ASRDataSeg:
    text: str           # 片段文本
    start_time: int     # 开始时间（毫秒）
    end_time: int       # 结束时间（毫秒）
    translated_text: str = ""

    # 时间戳转换
    to_srt_ts() -> str
    to_ass_ts() -> Tuple[str, str]
    to_lrc_ts() -> str
```

---

## 字幕处理

### render_ass_video()

```python
from app.core.subtitle import render_ass_video

render_ass_video(
    video_path="input.mp4",
    subtitle_path="subtitle.ass",
    output_path="output.mp4"
)
```

### auto_wrap_ass_file()

```python
from app.core.subtitle import auto_wrap_ass_file

auto_wrap_ass_file("subtitle.ass", max_width=30)
```

---

## 翻译模块

### BaseTranslator

```python
class BaseTranslator(ABC):
    def __init__(
        self,
        thread_num: int,
        batch_num: int,
        target_language: TargetLanguage,
        update_callback: Optional[Callable]
    )

    def translate_subtitle(self, subtitle_data: ASRData) -> ASRData
    def stop()
```

### 翻译器实现

- `LLMTranslator` - LLM 翻译
- `DeepLXTranslator` - DeepLX
- `GoogleTranslator` - 谷歌翻译
- `BingTranslator` - 微软翻译

---

## 视频工具

### get_video_info()

```python
from app.core.utils.video_utils import get_video_info

info = get_video_info("video.mp4")
# info.width, info.height, info.fps, info.duration_seconds, ...
```

### video2audio()

```python
from app.core.utils.video_utils import video2audio

video2audio("video.mp4", "audio.wav", audio_track_index=0)
```

---

## LLM 模块

### get_llm_client()

```python
from app.core.llm.client import get_llm_client

client = get_llm_client()
# 需要环境变量: OPENAI_BASE_URL, OPENAI_API_KEY
```

### call_llm()

```python
from app.core.llm.client import call_llm

response = call_llm(
    messages=[{"role": "user", "content": "..."}],
    model="gpt-3.5-turbo",
    max_tokens=500
)
```

---

## Pipeline 框架

### PipelineContext

```python
class PipelineContext:
    run_id: str
    source_type: str
    source_url: Optional[str]
    video_path: Optional[str]
    subtitle_path: Optional[str]
    audio_path: Optional[str]
    thresholds: PipelineThresholds

    # 中间状态
    video_duration: Optional[float]
    subtitle_valid: bool
    is_silent: bool
    summary_text: Optional[str]
    trace: List[TraceEvent]
    extra: Dict[str, Any]

    # 方法
    get(key: str, default=None) -> Any
    set(key: str, value: Any)
    add_trace(node_id, status, elapsed_ms, error, output_keys)
    to_dict() -> Dict
```

### PipelineNode

```python
class PipelineNode(ABC):
    def __init__(self, node_id: str, params: Dict[str, Any] = None)

    @abstractmethod
    def run(self, ctx: PipelineContext) -> None

    @abstractmethod
    def get_output_keys(self) -> List[str]
```

### 内置节点

| 节点 | 说明 | 输出 |
|------|------|------|
| `InputNode` | 验证输入 | `source_type`, `local_input_type` |
| `FetchMetadataNode` | 获取元数据 | `video_duration`, `video_width`, ... |
| `DownloadSubtitleNode` | 下载字幕 | `subtitle_path` |
| `DownloadVideoNode` | 下载视频 | `video_path` |
| `ParseSubtitleNode` | 解析字幕 | `asr_data`, `subtitle_segment_count` |
| `ValidateSubtitleNode` | 验证字幕 | `subtitle_valid`, `subtitle_coverage_ratio` |
| `ExtractAudioNode` | 提取音频 | `audio_path` |
| `DetectSilenceNode` | 检测静音 | `is_silent`, `audio_rms` |
| `TranscribeNode` | 音频转录 | `asr_data`, `transcript_token_count` |
| `TextSummarizeNode` | 文本摘要 | `summary_text` |
| `WarningNode` | 输出警告 | `summary_text` |

### NodeRegistry

```python
from app.pipeline.registry import get_default_registry

registry = get_default_registry()
registry.register("MyNode", MyNodeClass)
node = registry.create("InputNode", "input_1", params={})
```

---

## 条件表达式

边配置支持条件表达式：

```python
PipelineEdgeConfig(
    source="validate",
    target="summary",
    condition="subtitle_valid == True"
)
```

可用变量：`subtitle_valid`, `is_silent`, `video_duration`, `local_input_type`, ...

---

## 使用示例

### URL 自动流程

```bash
curl -X POST http://localhost:8000/pipeline/auto/url \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {"source_url": "https://youtube.com/watch?v=..."},
    "options": {"summary": {"model": "gpt-3.5-turbo", "max_tokens": 500}}
  }'
```

### 自定义 DAG

```bash
curl -X POST http://localhost:8000/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline": {
      "version": "v1",
      "nodes": [
        {"id": "input", "type": "InputNode"},
        {"id": "extract", "type": "ExtractAudioNode"},
        {"id": "transcribe", "type": "TranscribeNode", "params": {...}}
      ],
      "edges": [
        {"source": "input", "target": "extract"},
        {"source": "extract", "target": "transcribe"}
      ]
    },
    "inputs": {"source_type": "local", "video_path": "/path/video.mp4"}
  }'
```

---

相关文档：
- [架构设计](/dev/architecture)
- [贡献指南](/dev/contributing)
