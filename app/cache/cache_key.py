"""Cache Key 计算模块

提供:
- URL 规范化
- yt-dlp 身份提取
- URL/本地文件的 cache_key 计算
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.config import APPDATA_PATH
from app.core.utils.logger import setup_logger

logger = setup_logger("cache_key")

# 流式 hash 计算的块大小
HASH_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB


def normalize_url(url: str) -> str:
    """规范化 URL

    - 移除 fragment
    - 统一 scheme (http -> https)
    - 排序 query 参数
    - 移除尾部斜杠
    """
    if not url:
        return ""

    parsed = urlparse(url.strip())

    # 统一 scheme
    scheme = parsed.scheme.lower()
    if scheme == "http":
        scheme = "https"

    # 规范化 host
    netloc = parsed.netloc.lower()

    # 排序 query 参数
    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    sorted_query = urlencode(sorted(query_params))

    # 规范化 path (移除尾部斜杠，但保留根路径)
    path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

    # 重建 URL，移除 fragment
    normalized = urlunparse((scheme, netloc, path, "", sorted_query, ""))

    return normalized


def extract_yt_dlp_identity(url: str) -> Optional[Tuple[str, str]]:
    """使用 yt-dlp 提取视频身份信息

    Returns:
        (extractor, id) 元组，提取失败时返回 None
    """
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,  # 不展开播放列表
        }

        # 检查 cookies 文件
        cookiefile_path = APPDATA_PATH / "cookies.txt"
        if cookiefile_path.exists():
            ydl_opts["cookiefile"] = str(cookiefile_path)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                extractor = info.get("extractor_key") or info.get("extractor", "")
                video_id = info.get("id", "")
                if extractor and video_id:
                    return (extractor.lower(), video_id)

    except Exception as e:
        logger.debug(f"yt-dlp 身份提取失败: {e}")

    return None


def compute_url_cache_key(url: str) -> str:
    """计算 URL 的 cache_key

    优先使用 yt-dlp 提取的 (extractor, id)，否则使用规范化 URL
    """
    # 尝试提取 yt-dlp 身份
    identity = extract_yt_dlp_identity(url)

    if identity:
        extractor, video_id = identity
        source = f"ytdlp:{extractor}:{video_id}"
        logger.debug(f"使用 yt-dlp 身份: {source}")
    else:
        source = f"url:{normalize_url(url)}"
        logger.debug(f"使用规范化 URL: {source}")

    # 计算 SHA256
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def compute_file_hash(file_path: str, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """流式计算文件 SHA256

    Args:
        file_path: 文件路径
        chunk_size: 读取块大小

    Returns:
        文件内容的 SHA256 十六进制字符串
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)

    return hasher.hexdigest()


def compute_local_cache_key(file_hash: str) -> str:
    """计算本地文件的 cache_key

    Args:
        file_hash: 文件内容的 SHA256

    Returns:
        cache_key
    """
    source = f"file:{file_hash}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def compute_cache_key_from_source(
    source_type: str,
    source_url: Optional[str] = None,
    file_hash: Optional[str] = None,
) -> str:
    """根据来源类型计算 cache_key

    Args:
        source_type: "url" 或 "local"
        source_url: URL (source_type="url" 时必填)
        file_hash: 文件 hash (source_type="local" 时必填)

    Returns:
        cache_key
    """
    if source_type == "url":
        if not source_url:
            raise ValueError("source_type 为 url 时必须提供 source_url")
        return compute_url_cache_key(source_url)
    elif source_type == "local":
        if not file_hash:
            raise ValueError("source_type 为 local 时必须提供 file_hash")
        return compute_local_cache_key(file_hash)
    else:
        raise ValueError(f"不支持的 source_type: {source_type}")
