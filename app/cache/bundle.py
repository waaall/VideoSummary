"""Bundle 目录管理模块

Bundle 是缓存产物的存储单元，包含:
- bundle.json: 清单与状态
- source.json: 源信息
- 各类产物文件 (video.mp4, audio.wav, subtitle.vtt, asr.json, summary.json)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import PROFILE_VERSION, WORK_PATH
from app.core.utils.logger import setup_logger

logger = setup_logger("bundle")

# 产物文件的标准命名
ARTIFACT_NAMES = {
    "video": "video.mp4",
    "audio": "audio.wav",
    "subtitle": "subtitle.vtt",
    "asr": "asr.json",
    "summary": "summary.json",
}

BUNDLE_VERSION = "v2"


@dataclass
class ArtifactInfo:
    """产物信息"""
    path: str  # 相对于 bundle 目录的路径
    size: int
    sha256: Optional[str] = None


@dataclass
class BundleManifest:
    """Bundle 清单 (bundle.json)"""
    version: str = BUNDLE_VERSION
    profile_version: str = PROFILE_VERSION
    cache_key: str = ""
    source_type: str = ""  # "url" | "local"
    source_ref: str = ""  # 规范化 URL 或文件 hash
    source_name: Optional[str] = None  # 展示名称（URL 标题或本地文件名）
    status: str = "pending"  # pending | running | completed | failed
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    artifacts: Dict[str, ArtifactInfo] = field(default_factory=dict)
    summary_text: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "version": self.version,
            "profile_version": self.profile_version,
            "cache_key": self.cache_key,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "source_name": self.source_name,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "artifacts": {
                k: {"path": v.path, "size": v.size, "sha256": v.sha256}
                for k, v in self.artifacts.items()
            },
            "summary_text": self.summary_text,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BundleManifest":
        """从字典创建"""
        artifacts = {}
        for k, v in data.get("artifacts", {}).items():
            artifacts[k] = ArtifactInfo(
                path=v.get("path", ""),
                size=v.get("size", 0),
                sha256=v.get("sha256"),
            )

        return cls(
            version=data.get("version", BUNDLE_VERSION),
            profile_version=data.get("profile_version", PROFILE_VERSION),
            cache_key=data.get("cache_key", ""),
            source_type=data.get("source_type", ""),
            source_ref=data.get("source_ref", ""),
            source_name=data.get("source_name"),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            artifacts=artifacts,
            summary_text=data.get("summary_text"),
            error=data.get("error"),
        )


class BundleManager:
    """Bundle 目录管理器"""

    def __init__(self, base_path: Optional[Path] = None):
        """
        Args:
            base_path: 缓存基础目录，默认 WORK_PATH / "cache"
        """
        self.base_path = base_path or (WORK_PATH / "cache")
        self.tmp_path = WORK_PATH / "tmp"

        # 确保目录存在
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.tmp_path.mkdir(parents=True, exist_ok=True)

    def get_bundle_dir(self, cache_key: str, source_type: str) -> Path:
        """获取 bundle 目录路径

        Args:
            cache_key: 缓存键
            source_type: "url" 或 "local"
        """
        return self.base_path / source_type / cache_key

    def get_tmp_dir(self, job_id: str) -> Path:
        """获取临时工作目录"""
        return self.tmp_path / job_id

    def create_tmp_dir(self, job_id: str) -> Path:
        """创建临时工作目录"""
        tmp_dir = self.get_tmp_dir(job_id)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return tmp_dir

    def bundle_exists(self, cache_key: str, source_type: str) -> bool:
        """检查 bundle 是否存在"""
        bundle_dir = self.get_bundle_dir(cache_key, source_type)
        return (bundle_dir / "bundle.json").exists()

    def load_manifest(self, cache_key: str, source_type: str) -> Optional[BundleManifest]:
        """加载 bundle 清单"""
        bundle_dir = self.get_bundle_dir(cache_key, source_type)
        manifest_path = bundle_dir / "bundle.json"

        if not manifest_path.exists():
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return BundleManifest.from_dict(data)
        except Exception as e:
            logger.warning(f"加载 bundle 清单失败: {e}")
            return None

    def save_manifest(
        self,
        cache_key: str,
        source_type: str,
        manifest: BundleManifest,
        target_dir: Optional[Path] = None,
    ) -> None:
        """保存 bundle 清单

        Args:
            cache_key: 缓存键
            source_type: 来源类型
            manifest: 清单对象
            target_dir: 目标目录，默认为 bundle 目录
        """
        if target_dir is None:
            target_dir = self.get_bundle_dir(cache_key, source_type)

        target_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = target_dir / "bundle.json"

        manifest.updated_at = time.time()

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, ensure_ascii=False, indent=2)

    def create_bundle(
        self,
        cache_key: str,
        source_type: str,
        source_ref: str,
        source_name: Optional[str] = None,
    ) -> BundleManifest:
        """创建新的 bundle

        Args:
            cache_key: 缓存键
            source_type: "url" 或 "local"
            source_ref: 规范化 URL 或文件 hash
        """
        manifest = BundleManifest(
            cache_key=cache_key,
            source_type=source_type,
            source_ref=source_ref,
            source_name=source_name,
            status="pending",
        )

        self.save_manifest(cache_key, source_type, manifest)

        # 保存 source.json
        bundle_dir = self.get_bundle_dir(cache_key, source_type)
        source_path = bundle_dir / "source.json"
        with open(source_path, "w", encoding="utf-8") as f:
            json.dump({
                "source_type": source_type,
                "source_ref": source_ref,
                "source_name": source_name,
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"创建 bundle: {cache_key} ({source_type})")
        return manifest

    def add_artifact(
        self,
        cache_key: str,
        source_type: str,
        artifact_type: str,
        source_path: Path,
        compute_hash: bool = True,
    ) -> ArtifactInfo:
        """添加产物到 bundle

        Args:
            cache_key: 缓存键
            source_type: 来源类型
            artifact_type: 产物类型 (video/audio/subtitle/asr/summary)
            source_path: 源文件路径
            compute_hash: 是否计算文件 hash
        """
        bundle_dir = self.get_bundle_dir(cache_key, source_type)
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # 确定目标文件名
        target_name = ARTIFACT_NAMES.get(artifact_type)
        if not target_name:
            # 未知类型，保留原扩展名
            target_name = f"{artifact_type}{source_path.suffix}"

        target_path = bundle_dir / target_name

        # 复制或移动文件
        if source_path != target_path:
            shutil.copy2(source_path, target_path)

        # 计算文件信息
        file_size = target_path.stat().st_size
        file_hash = None
        if compute_hash:
            file_hash = self._compute_file_hash(target_path)

        artifact = ArtifactInfo(
            path=target_name,
            size=file_size,
            sha256=file_hash,
        )

        # 更新清单
        manifest = self.load_manifest(cache_key, source_type)
        if manifest:
            manifest.artifacts[artifact_type] = artifact
            self.save_manifest(cache_key, source_type, manifest)

        logger.debug(f"添加产物 {artifact_type}: {target_name} ({file_size} bytes)")
        return artifact

    def finalize_from_tmp(
        self,
        job_id: str,
        cache_key: str,
        source_type: str,
    ) -> bool:
        """将临时目录原子移动到 cache 目录

        Args:
            job_id: 任务 ID
            cache_key: 缓存键
            source_type: 来源类型

        Returns:
            是否成功
        """
        tmp_dir = self.get_tmp_dir(job_id)
        if not tmp_dir.exists():
            logger.warning(f"临时目录不存在: {tmp_dir}")
            return False

        bundle_dir = self.get_bundle_dir(cache_key, source_type)
        bundle_dir.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 如果目标已存在，先移除
            if bundle_dir.exists():
                shutil.rmtree(bundle_dir)

            # 原子移动
            shutil.move(str(tmp_dir), str(bundle_dir))
            logger.info(f"Bundle 归档完成: {cache_key}")
            return True

        except Exception as e:
            logger.error(f"Bundle 归档失败: {e}")
            return False

    def cleanup_tmp(self, job_id: str) -> None:
        """清理临时目录"""
        tmp_dir = self.get_tmp_dir(job_id)
        if tmp_dir.exists():
            try:
                shutil.rmtree(tmp_dir)
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")

    def delete_bundle(self, cache_key: str, source_type: str) -> bool:
        """删除 bundle"""
        bundle_dir = self.get_bundle_dir(cache_key, source_type)
        if not bundle_dir.exists():
            return False

        try:
            shutil.rmtree(bundle_dir)
            logger.info(f"删除 bundle: {cache_key}")
            return True
        except Exception as e:
            logger.error(f"删除 bundle 失败: {e}")
            return False

    def get_bundle_size(self, cache_key: str, source_type: str) -> int:
        """获取 bundle 总大小（字节）"""
        bundle_dir = self.get_bundle_dir(cache_key, source_type)
        if not bundle_dir.exists():
            return 0

        total = 0
        for item in bundle_dir.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total

    def list_bundles(self, source_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有 bundle

        Args:
            source_type: 筛选来源类型，None 表示全部
        """
        results = []

        source_types = [source_type] if source_type else ["url", "local"]

        for st in source_types:
            type_dir = self.base_path / st
            if not type_dir.exists():
                continue

            for cache_dir in type_dir.iterdir():
                if not cache_dir.is_dir():
                    continue

                manifest = self.load_manifest(cache_dir.name, st)
                if manifest:
                    results.append({
                        "cache_key": cache_dir.name,
                        "source_type": st,
                        "source_name": manifest.source_name,
                        "status": manifest.status,
                        "created_at": manifest.created_at,
                        "updated_at": manifest.updated_at,
                        "size": self.get_bundle_size(cache_dir.name, st),
                    })

        return results

    def _compute_file_hash(self, file_path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
        """计算文件 SHA256"""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
