from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TranscribeOutputFormatEnum(Enum):
    """转录输出格式"""

    SRT = "SRT"
    ASS = "ASS"
    VTT = "VTT"
    TXT = "TXT"
    ALL = "All"


class TranscribeModelEnum(Enum):
    """转录模型"""

    BIJIAN = "B 接口"
    JIANYING = "J 接口"
    WHISPER_API = "Whisper [API] ✨"
    WHISPER_SERVICE = "Whisper Service"
    FASTER_WHISPER = "FasterWhisper ✨"
    WHISPER_CPP = "WhisperCpp"


class VadMethodEnum(Enum):
    """VAD方法"""

    SILERO_V3 = "silero_v3"  # 通常比 v4 准确性低，但没有 v4 的一些怪癖
    SILERO_V4 = (
        "silero_v4"  # 与 silero_v4_fw 相同。运行原始 Silero 的代码，而不是适配过的代码
    )
    SILERO_V5 = (
        "silero_v5"  # 与 silero_v5_fw 相同。运行原始 Silero 的代码，而不是适配过的代码)
    )
    SILERO_V4_FW = (
        "silero_v4_fw"  # 默认模型。最准确的 Silero 版本，有一些非致命的小问题
    )
    # SILERO_V5_FW = "silero_v5_fw"  # 准确性差。不是 VAD，而是某种语音的随机检测器，有各种致命的小问题。避免使用！
    PYANNOTE_V3 = "pyannote_v3"  # 最佳准确性，支持 CUDA
    PYANNOTE_ONNX_V3 = "pyannote_onnx_v3"  # pyannote_v3 的轻量版。与 Silero v4 的准确性相似，可能稍好，支持 CUDA
    WEBRTC = "webrtc"  # 准确性低，过时的 VAD。仅接受 'vad_min_speech_duration_ms' 和 'vad_speech_pad_ms'
    AUDITOK = "auditok"  # 实际上这不是 VAD，而是 AAD - 音频活动检测


class SubtitleLayoutEnum(Enum):
    """字幕布局"""

    TRANSLATE_ON_TOP = "译文在上"
    ORIGINAL_ON_TOP = "原文在上"
    ONLY_ORIGINAL = "仅原文"
    ONLY_TRANSLATE = "仅译文"


class TranscribeLanguageEnum(Enum):
    """转录语言"""

    AUTO = "自动"
    ENGLISH = "英语"
    CHINESE = "中文"
    JAPANESE = "日本語"
    KOREAN = "韩语"
    YUE = "粤语"
    FRENCH = "法语"
    GERMAN = "德语"
    SPANISH = "西班牙语"
    RUSSIAN = "俄语"
    PORTUGUESE = "葡萄牙语"
    TURKISH = "土耳其语"
    POLISH = "Polish"
    CATALAN = "Catalan"
    DUTCH = "Dutch"
    ARABIC = "Arabic"
    SWEDISH = "Swedish"
    ITALIAN = "Italian"
    INDONESIAN = "Indonesian"
    HINDI = "Hindi"
    FINNISH = "Finnish"
    VIETNAMESE = "Vietnamese"
    HEBREW = "Hebrew"
    UKRAINIAN = "Ukrainian"
    GREEK = "Greek"
    MALAY = "Malay"
    CZECH = "Czech"
    ROMANIAN = "Romanian"
    DANISH = "Danish"
    HUNGARIAN = "Hungarian"
    TAMIL = "Tamil"
    NORWEGIAN = "Norwegian"
    THAI = "Thai"
    URDU = "Urdu"
    CROATIAN = "Croatian"
    BULGARIAN = "Bulgarian"
    LITHUANIAN = "Lithuanian"
    LATIN = "Latin"
    MAORI = "Maori"
    MALAYALAM = "Malayalam"
    WELSH = "Welsh"
    SLOVAK = "Slovak"
    TELUGU = "Telugu"
    PERSIAN = "Persian"
    LATVIAN = "Latvian"
    BENGALI = "Bengali"
    SERBIAN = "Serbian"
    AZERBAIJANI = "Azerbaijani"
    SLOVENIAN = "Slovenian"
    KANNADA = "Kannada"
    ESTONIAN = "Estonian"
    MACEDONIAN = "Macedonian"
    BRETON = "Breton"
    BASQUE = "Basque"
    ICELANDIC = "Icelandic"
    ARMENIAN = "Armenian"
    NEPALI = "Nepali"
    MONGOLIAN = "Mongolian"
    BOSNIAN = "Bosnian"
    KAZAKH = "Kazakh"
    ALBANIAN = "Albanian"
    SWAHILI = "Swahili"
    GALICIAN = "Galician"
    MARATHI = "Marathi"
    PUNJABI = "Punjabi"
    SINHALA = "Sinhala"
    KHMER = "Khmer"
    SHONA = "Shona"
    YORUBA = "Yoruba"
    SOMALI = "Somali"
    AFRIKAANS = "Afrikaans"
    OCCITAN = "Occitan"
    GEORGIAN = "Georgian"
    BELARUSIAN = "Belarusian"
    TAJIK = "Tajik"
    SINDHI = "Sindhi"
    GUJARATI = "Gujarati"
    AMHARIC = "Amharic"
    YIDDISH = "Yiddish"
    LAO = "Lao"
    UZBEK = "Uzbek"
    FAROESE = "Faroese"
    HAITIAN_CREOLE = "Haitian Creole"
    PASHTO = "Pashto"
    TURKMEN = "Turkmen"
    NYNORSK = "Nynorsk"
    MALTESE = "Maltese"
    SANSKRIT = "Sanskrit"
    LUXEMBOURGISH = "Luxembourgish"
    MYANMAR = "Myanmar"
    TIBETAN = "Tibetan"
    TAGALOG = "Tagalog"
    MALAGASY = "Malagasy"
    ASSAMESE = "Assamese"
    TATAR = "Tatar"
    HAWAIIAN = "Hawaiian"
    LINGALA = "Lingala"
    HAUSA = "Hausa"
    BASHKIR = "Bashkir"
    JAVANESE = "Javanese"
    SUNDANESE = "Sundanese"
    CANTONESE = "Cantonese"


class WhisperModelEnum(Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE_V1 = "large-v1"
    LARGE_V2 = "large-v2"
    LARGE_V3_TURBO = "large-v3-turbo"


class FasterWhisperModelEnum(Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE_V1 = "large-v1"
    LARGE_V2 = "large-v2"
    LARGE_V3 = "large-v3"
    LARGE_V3_TURBO = "large-v3-turbo"


LANGUAGES = {
    "自动": "",
    "Auto": "",
    "auto": "",
    "英语": "en",
    "中文": "zh",
    "日本語": "ja",
    "德语": "de",
    "粤语": "yue",
    "西班牙语": "es",
    "俄语": "ru",
    "韩语": "ko",
    "法语": "fr",
    "葡萄牙语": "pt",
    "土耳其语": "tr",
    "English": "en",
    "Chinese": "zh",
    "German": "de",
    "Spanish": "es",
    "Russian": "ru",
    "Korean": "ko",
    "French": "fr",
    "Japanese": "ja",
    "Portuguese": "pt",
    "Turkish": "tr",
    "Polish": "pl",
    "Catalan": "ca",
    "Dutch": "nl",
    "Arabic": "ar",
    "Swedish": "sv",
    "Italian": "it",
    "Indonesian": "id",
    "Hindi": "hi",
    "Finnish": "fi",
    "Vietnamese": "vi",
    "Hebrew": "he",
    "Ukrainian": "uk",
    "Greek": "el",
    "Malay": "ms",
    "Czech": "cs",
    "Romanian": "ro",
    "Danish": "da",
    "Hungarian": "hu",
    "Tamil": "ta",
    "Norwegian": "no",
    "Thai": "th",
    "Urdu": "ur",
    "Croatian": "hr",
    "Bulgarian": "bg",
    "Lithuanian": "lt",
    "Latin": "la",
    "Maori": "mi",
    "Malayalam": "ml",
    "Welsh": "cy",
    "Slovak": "sk",
    "Telugu": "te",
    "Persian": "fa",
    "Latvian": "lv",
    "Bengali": "bn",
    "Serbian": "sr",
    "Azerbaijani": "az",
    "Slovenian": "sl",
    "Kannada": "kn",
    "Estonian": "et",
    "Macedonian": "mk",
    "Breton": "br",
    "Basque": "eu",
    "Icelandic": "is",
    "Armenian": "hy",
    "Nepali": "ne",
    "Mongolian": "mn",
    "Bosnian": "bs",
    "Kazakh": "kk",
    "Albanian": "sq",
    "Swahili": "sw",
    "Galician": "gl",
    "Marathi": "mr",
    "Punjabi": "pa",
    "Sinhala": "si",
    "Khmer": "km",
    "Shona": "sn",
    "Yoruba": "yo",
    "Somali": "so",
    "Afrikaans": "af",
    "Occitan": "oc",
    "Georgian": "ka",
    "Belarusian": "be",
    "Tajik": "tg",
    "Sindhi": "sd",
    "Gujarati": "gu",
    "Amharic": "am",
    "Yiddish": "yi",
    "Lao": "lo",
    "Uzbek": "uz",
    "Faroese": "fo",
    "Haitian Creole": "ht",
    "Pashto": "ps",
    "Turkmen": "tk",
    "Nynorsk": "nn",
    "Maltese": "mt",
    "Sanskrit": "sa",
    "Luxembourgish": "lb",
    "Myanmar": "my",
    "Tibetan": "bo",
    "Tagalog": "tl",
    "Malagasy": "mg",
    "Assamese": "as",
    "Tatar": "tt",
    "Hawaiian": "haw",
    "Lingala": "ln",
    "Hausa": "ha",
    "Bashkir": "ba",
    "Javanese": "jw",
    "Sundanese": "su",
    "Cantonese": "yue",
}


@dataclass
class AudioStreamInfo:
    """音频流信息"""

    index: int  # 音轨在视频中的实际索引（如 0, 1, 2 或 2, 3, 4）
    codec: str  # 音频编解码器（如 aac, mp3, opus）
    language: str = ""  # 语言标签（如 eng, chi, deu）
    title: str = ""  # 音轨标题（可选）


@dataclass
class VideoInfo:
    """视频信息类"""

    file_name: str
    file_path: str
    width: int
    height: int
    fps: float
    duration_seconds: float
    bitrate_kbps: int
    video_codec: str
    audio_codec: str
    audio_sampling_rate: int
    thumbnail_path: str
    audio_streams: list[AudioStreamInfo] = field(default_factory=list)  # 音频流列表


@dataclass
class TranscribeConfig:
    """转录配置类"""

    transcribe_model: Optional[TranscribeModelEnum] = None
    transcribe_language: str = ""
    need_word_time_stamp: bool = True
    output_format: Optional[TranscribeOutputFormatEnum] = None
    # Whisper Cpp 配置
    whisper_model: Optional[WhisperModelEnum] = None
    # Whisper API 配置
    whisper_api_key: Optional[str] = None
    whisper_api_base: Optional[str] = None
    whisper_api_model: Optional[str] = None
    whisper_api_prompt: Optional[str] = None
    # Whisper Service 配置
    whisper_service_base: Optional[str] = None
    whisper_service_encode: bool = True
    whisper_service_task: str = "transcribe"
    whisper_service_vad_filter: bool = False
    whisper_service_output: str = "srt"
    whisper_service_prompt: Optional[str] = None
    # Faster Whisper 配置
    faster_whisper_program: Optional[str] = None
    faster_whisper_model: Optional[FasterWhisperModelEnum] = None
    faster_whisper_model_dir: Optional[str] = None
    faster_whisper_device: str = "cuda"
    faster_whisper_vad_filter: bool = True
    faster_whisper_vad_threshold: float = 0.5
    faster_whisper_vad_method: Optional[VadMethodEnum] = VadMethodEnum.SILERO_V3
    faster_whisper_ff_mdx_kim2: bool = False
    faster_whisper_one_word: bool = True
    faster_whisper_prompt: Optional[str] = None

    def _mask_key(self, key: Optional[str]) -> str:
        """Mask sensitive key for display"""
        if not key or len(key) <= 12:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

    def print_config(self) -> str:
        """Print transcription configuration"""
        lines = ["=========== Transcription Task ==========="]
        lines.append(
            f"Model: {self.transcribe_model.value if self.transcribe_model else 'None'}"
        )
        lines.append(f"Language: {self.transcribe_language or 'Auto'}")
        lines.append(f"Word Timestamp: {self.need_word_time_stamp}")
        lines.append(
            f"Output Format: {self.output_format.value if self.output_format else 'None'}"
        )

        if self.transcribe_model == TranscribeModelEnum.WHISPER_API:
            lines.append(f"API Base: {self.whisper_api_base}")
            lines.append(f"API Key: {self._mask_key(self.whisper_api_key)}")
            lines.append(f"API Model: {self.whisper_api_model}")
            if self.whisper_api_prompt:
                lines.append(f"Prompt: {self.whisper_api_prompt[:30]}...")

        elif self.transcribe_model == TranscribeModelEnum.WHISPER_SERVICE:
            lines.append(f"Service Base: {self.whisper_service_base}")
            lines.append(f"Encode: {self.whisper_service_encode}")
            lines.append(f"Task: {self.whisper_service_task}")
            lines.append(f"VAD Filter: {self.whisper_service_vad_filter}")
            lines.append(f"Output: {self.whisper_service_output}")
            if self.whisper_service_prompt:
                lines.append(f"Prompt: {self.whisper_service_prompt[:30]}...")

        elif self.transcribe_model == TranscribeModelEnum.FASTER_WHISPER:
            lines.append(
                f"Model: {self.faster_whisper_model.value if self.faster_whisper_model else 'None'}"
            )
            lines.append(f"Device: {self.faster_whisper_device}")
            lines.append(f"VAD Filter: {self.faster_whisper_vad_filter}")
            if self.faster_whisper_vad_filter:
                lines.append(
                    f"VAD Method: {self.faster_whisper_vad_method.value if self.faster_whisper_vad_method else 'None'}"
                )
                lines.append(f"VAD Threshold: {self.faster_whisper_vad_threshold}")
            lines.append(f"One Word Per Segment: {self.faster_whisper_one_word}")

        elif self.transcribe_model == TranscribeModelEnum.WHISPER_CPP:
            lines.append(
                f"Model: {self.whisper_model.value if self.whisper_model else 'None'}"
            )

        lines.append("=" * 42)
        return "\n".join(lines)
