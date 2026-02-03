"""缓存服务层

提供缓存查询、创建、更新的统一接口
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.api.persistence import SQLiteStore, get_store
from app.cache.bundle import BundleManager, BundleManifest
from app.cache.cache_key import (
    compute_cache_key_from_source,
    normalize_url,
)
from app.config import PROFILE_VERSION
from app.core.utils.logger import setup_logger

logger = setup_logger("cache_service")

INVALID_SUMMARY_PREFIXES = (
    "无法生成摘要",
    "总结生成失败",
    "无有效信息",
)


@dataclass
class CacheLookupResult:
    """缓存查询结果"""
    hit: bool
    status: str  # "completed" | "running" | "pending" | "failed" | "not_found"
    cache_key: Optional[str] = None
    source_name: Optional[str] = None
    summary_text: Optional[str] = None
    bundle_path: Optional[str] = None
    job_id: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[float] = None
    updated_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hit": self.hit,
            "status": self.status,
            "cache_key": self.cache_key,
            "source_name": self.source_name,
            "summary_text": self.summary_text,
            "bundle_path": self.bundle_path,
            "job_id": self.job_id,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class CacheEntry:
    """缓存条目"""
    cache_key: str
    source_type: str
    source_ref: str
    status: str
    source_name: Optional[str] = None
    profile_version: str = PROFILE_VERSION
    summary_text: Optional[str] = None
    bundle_path: Optional[str] = None
    error: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0
    last_accessed: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        return cls(
            cache_key=data.get("cache_key", ""),
            source_type=data.get("source_type", ""),
            source_ref=data.get("source_ref", ""),
            source_name=data.get("source_name"),
            status=data.get("status", "pending"),
            profile_version=data.get("profile_version", PROFILE_VERSION),
            summary_text=data.get("summary_text"),
            bundle_path=data.get("bundle_path"),
            error=data.get("error"),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
            last_accessed=data.get("last_accessed"),
        )


class CacheService:
    """缓存服务"""

    def __init__(
        self,
        store: Optional[SQLiteStore] = None,
        bundle_manager: Optional[BundleManager] = None,
    ):
        self.store = store or get_store()
        self.bundle_manager = bundle_manager or BundleManager()

    def _is_summary_text_valid(self, text: Optional[str]) -> bool:
        if not text:
            return False
        stripped = text.strip()
        if not stripped:
            return False
        for prefix in INVALID_SUMMARY_PREFIXES:
            if stripped.startswith(prefix):
                return False
        return True

    def _load_summary_json(
        self, cache_key: str, source_type: str
    ) -> Optional[Dict[str, Any]]:
        bundle_dir = self.bundle_manager.get_bundle_dir(cache_key, source_type)
        summary_path = bundle_dir / "summary.json"
        if not summary_path.exists():
            return None
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.warning(f"读取 summary.json 失败: {e}")
        return None

    def _is_summary_json_valid(self, data: Dict[str, Any]) -> bool:
        if not isinstance(data, dict):
            return False
        summary_text = data.get("summary_text")
        model = data.get("model")
        input_chars = data.get("input_chars")
        profile_version = data.get("profile_version")
        if not isinstance(summary_text, str):
            return False
        if not isinstance(model, str):
            return False
        if not isinstance(input_chars, int):
            return False
        if not isinstance(profile_version, str):
            return False
        if profile_version != PROFILE_VERSION:
            return False
        return True

    def _is_cache_valid(self, entry: Dict[str, Any]) -> tuple[bool, str]:
        cache_key = entry.get("cache_key", "")
        source_type = entry.get("source_type", "")
        if entry.get("status") != "completed":
            return False, "cache_status_invalid"
        summary_text = entry.get("summary_text")
        if not self._is_summary_text_valid(summary_text):
            return False, "summary_text_invalid"

        manifest = self.bundle_manager.load_manifest(cache_key, source_type)
        if not manifest:
            return False, "bundle_manifest_missing"
        if manifest.profile_version != PROFILE_VERSION:
            return False, "profile_version_mismatch"
        if manifest.status != "completed":
            return False, "bundle_status_invalid"

        summary_json = self._load_summary_json(cache_key, source_type)
        if not summary_json or not self._is_summary_json_valid(summary_json):
            return False, "summary_json_invalid"
        if not self._is_summary_text_valid(summary_json.get("summary_text")):
            return False, "summary_text_invalid"
        if summary_text and summary_json.get("summary_text", "").strip() != summary_text.strip():
            return False, "summary_text_mismatch"

        return True, ""

    def lookup(
        self,
        source_type: str,
        source_url: Optional[str] = None,
        file_hash: Optional[str] = None,
        allow_stale: bool = False,
        *,
        strict: bool = True,
        touch: bool = True,
    ) -> CacheLookupResult:
        """查询缓存

        Args:
            source_type: "url" 或 "local"
            source_url: URL (source_type="url" 时)
            file_hash: 文件 hash (source_type="local" 时)
            allow_stale: 是否允许返回失败的缓存

        Returns:
            CacheLookupResult
        """
        # 计算 source_ref
        if source_type == "url":
            if not source_url:
                return CacheLookupResult(hit=False, status="not_found", error="缺少 source_url")
            source_ref = normalize_url(source_url)
        elif source_type == "local":
            if not file_hash:
                return CacheLookupResult(hit=False, status="not_found", error="缺少 file_hash")
            source_ref = file_hash
        else:
            return CacheLookupResult(hit=False, status="not_found", error=f"不支持的 source_type: {source_type}")

        # 计算 cache_key
        try:
            cache_key = compute_cache_key_from_source(source_type, source_url, file_hash)
        except Exception as e:
            logger.warning(f"cache_key 计算失败: {e}")
            return CacheLookupResult(hit=False, status="not_found", error=str(e))

        # 查询数据库
        entry = self.store.get_cache_entry(cache_key)

        if not entry:
            logger.debug(f"缓存未命中: {cache_key}")
            return CacheLookupResult(hit=False, status="not_found", cache_key=cache_key)

        status = entry.get("status", "pending")

        # 更新访问时间（只读接口可关闭）
        if touch:
            self.store.touch_cache_entry(cache_key)

        # 根据状态返回结果
        if status == "completed":
            if strict:
                valid, reason = self._is_cache_valid(entry)
                if not valid:
                    logger.warning(f"缓存无效: {cache_key} ({reason})")
                    self.update_status(cache_key, "failed", error=reason)
                    return CacheLookupResult(
                        hit=False,
                        status="failed",
                        cache_key=cache_key,
                        source_name=entry.get("source_name"),
                        error=reason,
                        created_at=entry.get("created_at"),
                        updated_at=entry.get("updated_at"),
                    )

            logger.info(f"缓存命中: {cache_key}")
            return CacheLookupResult(
                hit=True,
                status="completed",
                cache_key=cache_key,
                source_name=entry.get("source_name"),
                summary_text=entry.get("summary_text"),
                bundle_path=entry.get("bundle_path"),
                created_at=entry.get("created_at"),
                updated_at=entry.get("updated_at"),
            )

        if status in ("running", "pending"):
            # 查找正在执行的 job
            job = self.store.get_latest_job_for_cache(cache_key)
            job_id = job.get("job_id") if job else None
            logger.debug(f"缓存处理中: {cache_key}, job_id={job_id}")
            return CacheLookupResult(
                hit=False,
                status=status,
                cache_key=cache_key,
                source_name=entry.get("source_name"),
                job_id=job_id,
                created_at=entry.get("created_at"),
                updated_at=entry.get("updated_at"),
            )

        if status == "failed":
            if allow_stale:
                return CacheLookupResult(
                    hit=False,
                    status="failed",
                    cache_key=cache_key,
                    source_name=entry.get("source_name"),
                    error=entry.get("error"),
                    created_at=entry.get("created_at"),
                    updated_at=entry.get("updated_at"),
                )
            else:
                # 视为未命中，允许重试
                return CacheLookupResult(
                    hit=False,
                    status="failed",
                    cache_key=cache_key,
                    source_name=entry.get("source_name"),
                    error=entry.get("error"),
                )

        return CacheLookupResult(hit=False, status="not_found", cache_key=cache_key)

    def get_or_create_entry(
        self,
        cache_key: str,
        source_type: str,
        source_ref: str,
        source_name: Optional[str] = None,
    ) -> CacheEntry:
        """获取或创建缓存条目

        Args:
            cache_key: 缓存键
            source_type: "url" 或 "local"
            source_ref: 规范化 URL 或文件 hash

        Returns:
            CacheEntry
        """
        # 尝试获取已存在的条目
        entry_data = self.store.get_cache_entry(cache_key)

        if entry_data:
            entry = CacheEntry.from_dict(entry_data)
            if entry.profile_version != PROFILE_VERSION:
                self.store.update_cache_entry(
                    cache_key,
                    status="pending",
                    summary_text="",
                    error=None,
                    profile_version=PROFILE_VERSION,
                )
                entry_data = self.store.get_cache_entry(cache_key)
                return CacheEntry.from_dict(entry_data) if entry_data else entry
            if source_name and not entry.source_name:
                self.store.update_cache_entry(cache_key, source_name=source_name)
                entry_data = self.store.get_cache_entry(cache_key)
                return CacheEntry.from_dict(entry_data) if entry_data else entry
            return entry

        # 创建新条目
        bundle_path = str(self.bundle_manager.get_bundle_dir(cache_key, source_type))

        self.store.create_cache_entry(
            cache_key=cache_key,
            source_type=source_type,
            source_ref=source_ref,
            source_name=source_name,
            bundle_path=bundle_path,
            profile_version=PROFILE_VERSION,
        )

        logger.info(f"创建缓存条目: {cache_key} ({source_type})")

        entry_data = self.store.get_cache_entry(cache_key)
        return CacheEntry.from_dict(entry_data) if entry_data else CacheEntry(
            cache_key=cache_key,
            source_type=source_type,
            source_ref=source_ref,
            source_name=source_name,
            status="pending",
            bundle_path=bundle_path,
        )

    def update_status(
        self,
        cache_key: str,
        status: str,
        summary_text: Optional[str] = None,
        error: Optional[str] = None,
        source_name: Optional[str] = None,
    ) -> None:
        """更新缓存状态

        Args:
            cache_key: 缓存键
            status: 新状态 ("pending", "running", "completed", "failed")
            summary_text: 摘要文本 (status="completed" 时)
            error: 错误信息 (status="failed" 时)
        """
        self.store.update_cache_entry(
            cache_key,
            status=status,
            summary_text=summary_text,
            error=error,
            source_name=source_name,
        )

        # 同步更新 bundle.json
        entry = self.store.get_cache_entry(cache_key)
        if entry:
            manifest = self.bundle_manager.load_manifest(cache_key, entry["source_type"])
            if manifest:
                manifest.status = status
                if summary_text:
                    manifest.summary_text = summary_text
                if error:
                    manifest.error = error
                self.bundle_manager.save_manifest(cache_key, entry["source_type"], manifest)

        logger.info(f"更新缓存状态: {cache_key} -> {status}")

    def create_job(self, cache_key: str) -> str:
        """创建缓存任务

        Args:
            cache_key: 缓存键

        Returns:
            job_id
        """
        job_id = f"j_{uuid.uuid4().hex}"
        self.store.create_cache_job(job_id, cache_key)
        logger.info(f"创建缓存任务: {job_id} -> {cache_key}")
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息

        Returns:
            任务信息字典，包含 cache_entry 信息
        """
        job = self.store.get_cache_job(job_id)
        if not job:
            return None

        # 关联缓存条目信息
        cache_key = job.get("cache_key")
        if cache_key:
            entry = self.store.get_cache_entry(cache_key)
            if entry:
                job["cache_entry"] = entry

        return job

    def update_job(
        self,
        job_id: str,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """更新任务状态"""
        self.store.update_cache_job(job_id, status=status, error=error)
        logger.debug(f"更新任务状态: {job_id} -> {status}")

    def get_entry(self, cache_key: str) -> Optional[CacheEntry]:
        """获取缓存条目"""
        entry_data = self.store.get_cache_entry(cache_key)
        if not entry_data:
            return None
        return CacheEntry.from_dict(entry_data)

    def get_bundle_manifest(self, cache_key: str) -> Optional[BundleManifest]:
        """获取 bundle 清单"""
        entry = self.store.get_cache_entry(cache_key)
        if not entry:
            return None
        return self.bundle_manager.load_manifest(cache_key, entry["source_type"])

    def delete_entry(self, cache_key: str) -> bool:
        """删除缓存条目及其 bundle"""
        entry = self.store.get_cache_entry(cache_key)
        if not entry:
            return False

        # 删除 bundle
        self.bundle_manager.delete_bundle(cache_key, entry["source_type"])

        # 删除数据库记录
        self.store.delete_cache_entry(cache_key)

        logger.info(f"删除缓存: {cache_key}")
        return True


# 全局单例
_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """获取全局 CacheService 实例"""
    global _service
    if _service is None:
        _service = CacheService()
    return _service
