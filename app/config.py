import logging
import os
from pathlib import Path

VERSION = "v1.4.0"
# Processing profile version for cache validity. Bump when pipeline strategy changes.
PROFILE_VERSION = os.getenv("PROFILE_VERSION", "2026-02-02")
YEAR = 2025
APP_NAME = "VideoSummary"
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

# 日志配置
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 创建核心路径
for p in [CACHE_PATH, LOG_PATH, WORK_PATH, MODEL_PATH]:
    p.mkdir(parents=True, exist_ok=True)
