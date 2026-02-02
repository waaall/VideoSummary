"""缓存 GC 清理模块

提供:
- 基于大小的清理 (CACHE_MAX_BYTES)
- 基于时间的清理 (CACHE_TTL_DAYS)
- 失败条目快速清理 (FAILED_TTL_HOURS)
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import List, Optional

from app.api.persistence import SQLiteStore, get_store
from app.cache.bundle import BundleManager
from app.config import WORK_PATH
from app.core.utils.logger import setup_logger

logger = setup_logger("cache_gc")

# GC 配置（可通过环境变量覆盖）
CACHE_MAX_BYTES = int(os.getenv("CACHE_MAX_BYTES", str(50 * 1024 * 1024 * 1024)))  # 50GB
CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "30"))  # 30天
FAILED_TTL_HOURS = int(os.getenv("FAILED_TTL_HOURS", "24"))  # 24小时

# GC 运行间隔
GC_INTERVAL_SECONDS = int(os.getenv("GC_INTERVAL_SECONDS", str(3600)))  # 1小时


class CacheGC:
    """缓存 GC 管理器"""

    def __init__(
        self,
        store: Optional[SQLiteStore] = None,
        bundle_manager: Optional[BundleManager] = None,
        max_bytes: int = CACHE_MAX_BYTES,
        ttl_days: int = CACHE_TTL_DAYS,
        failed_ttl_hours: int = FAILED_TTL_HOURS,
    ):
        self.store = store or get_store()
        self.bundle_manager = bundle_manager or BundleManager()
        self.max_bytes = max_bytes
        self.ttl_seconds = ttl_days * 24 * 3600
        self.failed_ttl_seconds = failed_ttl_hours * 3600

        self._stop_event = threading.Event()
        self._gc_thread: Optional[threading.Thread] = None

    def start_background(self, interval: int = GC_INTERVAL_SECONDS) -> None:
        """启动后台 GC 线程"""
        if self._gc_thread and self._gc_thread.is_alive():
            return

        def gc_loop():
            while not self._stop_event.wait(interval):
                try:
                    self.run_gc()
                except Exception as e:
                    logger.error(f"GC 运行失败: {e}")

        self._gc_thread = threading.Thread(target=gc_loop, daemon=True, name="cache-gc")
        self._gc_thread.start()
        logger.info(f"缓存 GC 已启动，间隔 {interval} 秒")

    def stop(self) -> None:
        """停止 GC 线程"""
        self._stop_event.set()

    def run_gc(self) -> dict:
        """执行一次 GC

        Returns:
            GC 统计信息
        """
        stats = {
            "cleaned_count": 0,
            "cleaned_bytes": 0,
            "cleaned_by_ttl": 0,
            "cleaned_by_size": 0,
            "cleaned_failed": 0,
        }

        # 1. 清理失败条目（快速清理）
        failed_cleaned = self._clean_failed_entries()
        stats["cleaned_failed"] = failed_cleaned
        stats["cleaned_count"] += failed_cleaned

        # 2. 清理过期条目（TTL）
        ttl_cleaned, ttl_bytes = self._clean_expired_entries()
        stats["cleaned_by_ttl"] = ttl_cleaned
        stats["cleaned_count"] += ttl_cleaned
        stats["cleaned_bytes"] += ttl_bytes

        # 3. 按大小清理（LRU）
        size_cleaned, size_bytes = self._clean_by_size()
        stats["cleaned_by_size"] = size_cleaned
        stats["cleaned_count"] += size_cleaned
        stats["cleaned_bytes"] += size_bytes

        if stats["cleaned_count"] > 0:
            logger.info(
                f"GC 完成: 清理 {stats['cleaned_count']} 条, "
                f"释放 {stats['cleaned_bytes'] / 1024 / 1024:.1f} MB"
            )

        return stats

    def _clean_failed_entries(self) -> int:
        """清理失败条目"""
        entries = self.store.list_stale_cache_entries(
            max_age_seconds=self.failed_ttl_seconds,
            status="failed",
        )

        cleaned = 0
        for entry in entries:
            cache_key = entry.get("cache_key")
            source_type = entry.get("source_type")
            if cache_key and source_type:
                self.bundle_manager.delete_bundle(cache_key, source_type)
                self.store.delete_cache_entry(cache_key)
                cleaned += 1
                logger.debug(f"清理失败条目: {cache_key}")

        return cleaned

    def _clean_expired_entries(self) -> tuple[int, int]:
        """清理过期条目"""
        entries = self.store.list_stale_cache_entries(
            max_age_seconds=self.ttl_seconds,
        )

        cleaned = 0
        cleaned_bytes = 0

        for entry in entries:
            cache_key = entry.get("cache_key")
            source_type = entry.get("source_type")
            if cache_key and source_type:
                size = self.bundle_manager.get_bundle_size(cache_key, source_type)
                self.bundle_manager.delete_bundle(cache_key, source_type)
                self.store.delete_cache_entry(cache_key)
                cleaned += 1
                cleaned_bytes += size
                logger.debug(f"清理过期条目: {cache_key}")

        return cleaned, cleaned_bytes

    def _clean_by_size(self) -> tuple[int, int]:
        """按大小清理（LRU 策略）"""
        # 计算当前总大小
        total_size = self._get_total_cache_size()

        if total_size <= self.max_bytes:
            return 0, 0

        # 按 last_accessed 排序，优先清理最久未访问的
        entries = self.store.list_cache_entries(
            limit=1000,
            order_by="COALESCE(last_accessed, updated_at) ASC",
        )

        cleaned = 0
        cleaned_bytes = 0

        for entry in entries:
            if total_size - cleaned_bytes <= self.max_bytes:
                break

            cache_key = entry.get("cache_key")
            source_type = entry.get("source_type")
            status = entry.get("status")

            # 不清理正在运行的任务
            if status in ("running", "pending"):
                continue

            if cache_key and source_type:
                size = self.bundle_manager.get_bundle_size(cache_key, source_type)
                self.bundle_manager.delete_bundle(cache_key, source_type)
                self.store.delete_cache_entry(cache_key)
                cleaned += 1
                cleaned_bytes += size
                logger.debug(f"按大小清理: {cache_key} ({size / 1024 / 1024:.1f} MB)")

        return cleaned, cleaned_bytes

    def _get_total_cache_size(self) -> int:
        """获取缓存总大小"""
        cache_dir = self.bundle_manager.base_path
        if not cache_dir.exists():
            return 0

        total = 0
        for item in cache_dir.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
        return total

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        total_size = self._get_total_cache_size()
        entries = self.store.list_cache_entries(limit=10000)

        status_counts = {}
        for entry in entries:
            status = entry.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "max_size_mb": round(self.max_bytes / 1024 / 1024, 2),
            "usage_percent": round(total_size / self.max_bytes * 100, 1) if self.max_bytes > 0 else 0,
            "entry_count": len(entries),
            "status_counts": status_counts,
            "ttl_days": self.ttl_seconds // (24 * 3600),
            "failed_ttl_hours": self.failed_ttl_seconds // 3600,
        }


# 全局单例
_gc: Optional[CacheGC] = None


def get_cache_gc() -> CacheGC:
    """获取全局 CacheGC 实例"""
    global _gc
    if _gc is None:
        _gc = CacheGC()
    return _gc


def start_gc_background() -> None:
    """启动后台 GC"""
    gc = get_cache_gc()
    gc.start_background()
