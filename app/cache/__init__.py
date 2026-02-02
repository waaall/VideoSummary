"""缓存模块 - 同源去重与统一存储

提供:
- Cache Key 计算 (URL 规范化 + yt-dlp id + 文件 hash)
- Bundle 目录管理
- 缓存服务层 (查询/创建/更新)
- GC 清理
"""

from app.cache.cache_key import (
    compute_file_hash,
    compute_local_cache_key,
    compute_url_cache_key,
    extract_yt_dlp_identity,
    normalize_url,
)
from app.cache.bundle import BundleManager
from app.cache.cache_service import CacheService, get_cache_service
from app.cache.gc import CacheGC, get_cache_gc, start_gc_background

__all__ = [
    "normalize_url",
    "extract_yt_dlp_identity",
    "compute_url_cache_key",
    "compute_file_hash",
    "compute_local_cache_key",
    "BundleManager",
    "CacheService",
    "get_cache_service",
    "CacheGC",
    "get_cache_gc",
    "start_gc_background",
]
