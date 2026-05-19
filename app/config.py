import json
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

# 固态盘：配置 / 日志 / 数据库（小文件，需快速随机读写，与代码同盘）
APPDATA_PATH = ROOT_PATH / "AppData"
LOG_PATH = APPDATA_PATH / "logs"
LLM_LOG_FILE = LOG_PATH / "llm_requests.jsonl"
SETTINGS_PATH = APPDATA_PATH / "settings.json"
DB_PATH = APPDATA_PATH / "metadata.db"


def _resolve_data_root() -> Path:
    """解析大块数据根目录。

    优先读 settings.json 的 storage.data_root，为空则回退到项目内 work-dir。
    用于把视频、缓存、模型等大文件放到独立磁盘（如机械盘），与代码/数据库分盘。
    相对路径按项目根目录解析。
    """
    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            configured = str(data.get("storage", {}).get("data_root", "")).strip()
            if configured:
                path = Path(configured).expanduser()
                return path if path.is_absolute() else ROOT_PATH / path
    except (json.JSONDecodeError, OSError):
        pass
    return ROOT_PATH / "work-dir"


# 大块数据根目录：视频 / 上传 / 缓存 / 模型（可经 settings.json 的 storage.data_root 配置）
DATA_ROOT = _resolve_data_root()
CACHE_PATH = DATA_ROOT / "diskcache"   # diskcache：ASR/TTS/翻译等处理缓存
MODEL_PATH = DATA_ROOT / "models"      # 本地 ASR 模型文件
BUNDLE_PATH = DATA_ROOT / "bundles"    # 缓存产物 bundle（video.mp4、summary.json 等）
TMP_PATH = DATA_ROOT / "tmp"           # 任务临时工作目录
UPLOAD_PATH = DATA_ROOT / "uploads"    # 用户上传文件

# 日志配置
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 创建核心路径
for _p in (LOG_PATH, DATA_ROOT, CACHE_PATH, MODEL_PATH, BUNDLE_PATH, TMP_PATH, UPLOAD_PATH):
    _p.mkdir(parents=True, exist_ok=True)
