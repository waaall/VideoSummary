import logging
import os
from pathlib import Path

VERSION = "v1.4.0"
YEAR = 2025
APP_NAME = "VideoCaptioner"
AUTHOR = "Weifeng"

HELP_URL = "https://github.com/WEIFENG2333/VideoCaptioner"
GITHUB_REPO_URL = "https://github.com/WEIFENG2333/VideoCaptioner"
RELEASE_URL = "https://github.com/WEIFENG2333/VideoCaptioner/releases/latest"
FEEDBACK_URL = "https://github.com/WEIFENG2333/VideoCaptioner/issues"

# 核心路径
ROOT_PATH = Path(__file__).parent.parent

APPDATA_PATH = ROOT_PATH / "AppData"
WORK_PATH = ROOT_PATH / "work-dir"

LOG_PATH = APPDATA_PATH / "logs"
LLM_LOG_FILE = LOG_PATH / "llm_requests.jsonl"
SETTINGS_PATH = APPDATA_PATH / "settings.json"
CACHE_PATH = APPDATA_PATH / "cache"
MODEL_PATH = APPDATA_PATH / "models"

# 资源路径（UI 相关，后端可选）
RESOURCE_PATH = ROOT_PATH / "resource"
BIN_PATH = RESOURCE_PATH / "bin"
FASER_WHISPER_PATH = BIN_PATH / "Faster-Whisper-XXL"

# UI 专用资源路径（后端不需要，保留兼容性）
ASSETS_PATH = RESOURCE_PATH / "assets"
SUBTITLE_STYLE_PATH = RESOURCE_PATH / "subtitle_style"
TRANSLATIONS_PATH = RESOURCE_PATH / "translations"
FONTS_PATH = RESOURCE_PATH / "fonts"

# 日志配置
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 环境变量添加 bin 路径（用于 ffmpeg/faster-whisper 等工具）
if BIN_PATH.exists():
    os.environ["PATH"] = str(BIN_PATH) + os.pathsep + os.environ["PATH"]
if FASER_WHISPER_PATH.exists():
    os.environ["PATH"] = str(FASER_WHISPER_PATH) + os.pathsep + os.environ["PATH"]

# 创建核心路径
for p in [CACHE_PATH, LOG_PATH, WORK_PATH, MODEL_PATH]:
    p.mkdir(parents=True, exist_ok=True)
