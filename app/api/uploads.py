"""文件上传管理模块

提供本地文件上传功能，支持：
- 文件类型白名单校验
- 文件大小限制
- 安全路径处理
- TTL 过期清理
- file_id 到 stored_path 的映射
"""
from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set

from app.config import WORK_PATH
from app.api.persistence import SQLiteStore, get_store


# 文件类型白名单配置
ALLOWED_VIDEO_EXTENSIONS: Set[str] = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".wmv"}
ALLOWED_AUDIO_EXTENSIONS: Set[str] = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"}
ALLOWED_SUBTITLE_EXTENSIONS: Set[str] = {".srt", ".vtt", ".ass", ".ssa", ".sub"}

ALLOWED_VIDEO_MIMES: Set[str] = {
    "video/mp4", "video/x-matroska", "video/webm", "video/quicktime",
    "video/x-msvideo", "video/x-flv", "video/x-ms-wmv",
}
ALLOWED_AUDIO_MIMES: Set[str] = {
    "audio/mpeg", "audio/wav", "audio/x-wav", "audio/flac",
    "audio/aac", "audio/mp4", "audio/ogg", "audio/x-ms-wma",
}
ALLOWED_SUBTITLE_MIMES: Set[str] = {
    "text/plain", "text/vtt", "application/x-subrip",
    "text/x-ssa", "application/octet-stream",  # 部分字幕文件无特定 MIME
}

# 默认配置
DEFAULT_MAX_FILE_SIZE_MB = 2048  # 2GB
DEFAULT_TTL_SECONDS = 3600 * 24  # 24小时
DEFAULT_CLEANUP_INTERVAL_SECONDS = 3600  # 1小时清理一次
DEFAULT_UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB
DEFAULT_READ_TIMEOUT_SECONDS = 30
DEFAULT_WRITE_TIMEOUT_SECONDS = 30


@dataclass
class UploadedFile:
    """上传文件的元数据"""
    file_id: str
    original_name: str
    size: int
    mime_type: str
    file_type: str  # "video" | "audio" | "subtitle"
    stored_path: Path
    file_hash: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = DEFAULT_TTL_SECONDS

    def is_expired(self) -> bool:
        """检查文件是否过期"""
        return time.time() > self.created_at + self.ttl_seconds

    def to_dict(self, include_stored_path: bool = False) -> Dict:
        """转换为字典，用于 API 响应"""
        result = {
            "file_id": self.file_id,
            "original_name": self.original_name,
            "size": self.size,
            "mime_type": self.mime_type,
            "file_type": self.file_type,
            "file_hash": self.file_hash,
        }
        if include_stored_path:
            result["stored_path"] = str(self.stored_path)
        return result


class FileTypeError(Exception):
    """文件类型不支持"""
    pass


class FileSizeError(Exception):
    """文件大小超限"""
    pass


class FileTimeoutError(Exception):
    """读写超时"""
    pass


class FileNotFoundError(Exception):
    """文件不存在或已过期"""
    pass


class FileStorage:
    """文件存储管理器（单例模式）

    负责：
    - 文件上传与存储
    - file_id 生成与映射
    - 文件类型与大小校验
    - TTL 过期清理
    """

    _instance: Optional["FileStorage"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        upload_dir: Optional[Path] = None,
        max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        store: Optional[SQLiteStore] = None,
        db_path: Optional[Path] = None,
    ):
        # 避免重复初始化
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.upload_dir = upload_dir or (WORK_PATH / "uploads")
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.ttl_seconds = ttl_seconds
        self.store = store or get_store(db_path=db_path)

        # 文件映射表：file_id -> UploadedFile
        self._files: Dict[str, UploadedFile] = {}
        self._files_lock = threading.Lock()

        # 确保上传目录存在
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # 启动清理线程
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        self._start_cleanup_thread()

        # 从持久化存储恢复记录
        self._load_from_store()

        self._initialized = True

    def _start_cleanup_thread(self):
        """启动后台清理线程"""
        def cleanup_worker():
            while not self._stop_cleanup.wait(DEFAULT_CLEANUP_INTERVAL_SECONDS):
                self.cleanup_expired()

        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()

    def _load_from_store(self) -> None:
        """从 SQLite 恢复上传记录"""
        now = time.time()
        loaded: Dict[str, UploadedFile] = {}
        for record in self.store.list_uploads():
            created_at = float(record.get("created_at", 0))
            ttl_seconds = int(record.get("ttl_seconds", self.ttl_seconds))
            if created_at + ttl_seconds < now:
                stored_path = Path(record.get("stored_path", ""))
                self._cleanup_physical_file(stored_path)
                self._delete_record(record.get("file_id"))
                continue
            stored_path = Path(record.get("stored_path", ""))
            if not stored_path.exists():
                self.store.delete_upload(record.get("file_id", ""))
                continue
            uploaded = UploadedFile(
                file_id=record["file_id"],
                original_name=record["original_name"],
                size=int(record["size"]),
                mime_type=record.get("mime_type", "application/octet-stream"),
                file_type=record["file_type"],
                stored_path=stored_path,
                file_hash=record.get("file_hash"),
                created_at=created_at,
                ttl_seconds=ttl_seconds,
            )
            loaded[uploaded.file_id] = uploaded
        if loaded:
            with self._files_lock:
                self._files.update(loaded)

    def _generate_file_id(self) -> str:
        """生成唯一 file_id"""
        return f"f_{uuid.uuid4().hex}"

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，防止目录穿越和特殊字符

        - 移除路径分隔符
        - 移除不安全字符
        - 限制长度
        """
        # 只保留文件名部分
        filename = Path(filename).name
        # 移除不安全字符
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
        # 限制长度（保留扩展名）
        name, ext = Path(filename).stem, Path(filename).suffix
        if len(name) > 200:
            name = name[:200]
        return name + ext

    def _detect_file_type(
        self, filename: str, content_type: Optional[str]
    ) -> tuple[str, str]:
        """检测文件类型

        Returns:
            (file_type, mime_type): 文件类型和 MIME 类型

        Raises:
            FileTypeError: 文件类型不支持
        """
        ext = Path(filename).suffix.lower()

        # 优先使用客户端提供的 MIME，回退到扩展名推断
        mime_type = content_type
        if not mime_type or mime_type == "application/octet-stream":
            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # 扩展名 + MIME 双校验
        if ext in ALLOWED_VIDEO_EXTENSIONS:
            if mime_type not in ALLOWED_VIDEO_MIMES and mime_type != "application/octet-stream":
                raise FileTypeError(f"视频文件 MIME 类型不匹配: {mime_type}")
            return "video", mime_type

        if ext in ALLOWED_AUDIO_EXTENSIONS:
            if mime_type not in ALLOWED_AUDIO_MIMES and mime_type != "application/octet-stream":
                raise FileTypeError(f"音频文件 MIME 类型不匹配: {mime_type}")
            return "audio", mime_type

        if ext in ALLOWED_SUBTITLE_EXTENSIONS:
            # 字幕文件 MIME 类型比较宽松
            return "subtitle", mime_type

        raise FileTypeError(
            f"不支持的文件类型: {ext}。"
            f"支持的格式：视频 {ALLOWED_VIDEO_EXTENSIONS}，"
            f"音频 {ALLOWED_AUDIO_EXTENSIONS}，"
            f"字幕 {ALLOWED_SUBTITLE_EXTENSIONS}"
        )

    def save(
        self,
        content: bytes,
        original_name: str,
        content_type: Optional[str] = None,
    ) -> UploadedFile:
        """保存上传的文件

        Args:
            content: 文件内容
            original_name: 原始文件名
            content_type: MIME 类型（可选）

        Returns:
            UploadedFile: 上传文件的元数据

        Raises:
            FileSizeError: 文件大小超限
            FileTypeError: 文件类型不支持
        """
        # 大小校验
        if len(content) > self.max_file_size_bytes:
            raise FileSizeError(
                f"文件大小 {len(content) / 1024 / 1024:.1f}MB 超过限制 "
                f"{self.max_file_size_bytes / 1024 / 1024:.0f}MB"
            )

        # 类型校验
        file_type, mime_type = self._detect_file_type(original_name, content_type)

        # 生成 file_id 和安全路径
        file_id = self._generate_file_id()
        safe_name = self._sanitize_filename(original_name)

        # 存储路径：uploads/{file_id}/{safe_name}
        file_dir = self.upload_dir / file_id
        file_dir.mkdir(parents=True, exist_ok=True)
        stored_path = file_dir / safe_name

        # 写入文件
        stored_path.write_bytes(content)

        file_hash = hashlib.sha256(content).hexdigest()

        # 创建元数据记录
        uploaded_file = UploadedFile(
            file_id=file_id,
            original_name=original_name,
            size=len(content),
            mime_type=mime_type,
            file_type=file_type,
            stored_path=stored_path,
            file_hash=file_hash,
            ttl_seconds=self.ttl_seconds,
        )

        # 注册到映射表 + 持久化
        with self._files_lock:
            self._files[file_id] = uploaded_file
        self.store.upsert_upload(
            {
                "file_id": file_id,
                "original_name": original_name,
                "size": len(content),
                "mime_type": mime_type,
                "file_type": file_type,
                "stored_path": str(stored_path),
                "file_hash": file_hash,
                "created_at": uploaded_file.created_at,
                "ttl_seconds": uploaded_file.ttl_seconds,
            }
        )

        return uploaded_file

    async def save_stream(
        self,
        *,
        read_chunk,
        original_name: str,
        content_type: Optional[str] = None,
        chunk_size: int = DEFAULT_UPLOAD_CHUNK_SIZE,
        read_timeout: float = DEFAULT_READ_TIMEOUT_SECONDS,
        write_timeout: float = DEFAULT_WRITE_TIMEOUT_SECONDS,
    ) -> UploadedFile:
        """流式保存上传的文件"""
        # 类型校验
        file_type, mime_type = self._detect_file_type(original_name, content_type)

        safe_name = self._sanitize_filename(original_name)

        file_id = self._generate_file_id()
        file_dir = self.upload_dir / file_id
        file_dir.mkdir(parents=True, exist_ok=True)
        stored_path = file_dir / safe_name

        size = 0
        hasher = hashlib.sha256()
        max_bytes = self.max_file_size_bytes
        try:
            with open(stored_path, "wb") as f:
                while True:
                    try:
                        chunk = await asyncio.wait_for(
                            read_chunk(chunk_size), timeout=read_timeout
                        )
                    except asyncio.TimeoutError as e:
                        raise FileTimeoutError("读取超时") from e
                    if not chunk:
                        break
                    size += len(chunk)
                    hasher.update(chunk)
                    if size > max_bytes:
                        raise FileSizeError(
                            f"文件大小 {size / 1024 / 1024:.1f}MB 超过限制 "
                            f"{max_bytes / 1024 / 1024:.0f}MB"
                        )
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(f.write, chunk),
                            timeout=write_timeout,
                        )
                    except asyncio.TimeoutError as e:
                        raise FileTimeoutError("写入超时") from e
            if size == 0:
                raise FileSizeError("上传内容为空")
        except Exception:
            # 清理已写入的文件
            try:
                if stored_path.exists():
                    stored_path.unlink()
                if stored_path.parent.exists() and not any(stored_path.parent.iterdir()):
                    stored_path.parent.rmdir()
            except OSError:
                pass
            raise

        file_hash = hasher.hexdigest()

        uploaded_file = UploadedFile(
            file_id=file_id,
            original_name=original_name,
            size=size,
            mime_type=mime_type,
            file_type=file_type,
            stored_path=stored_path,
            file_hash=file_hash,
            ttl_seconds=self.ttl_seconds,
        )

        with self._files_lock:
            self._files[file_id] = uploaded_file
        self.store.upsert_upload(
            {
                "file_id": file_id,
                "original_name": original_name,
                "size": size,
                "mime_type": mime_type,
                "file_type": file_type,
                "stored_path": str(stored_path),
                "file_hash": file_hash,
                "created_at": uploaded_file.created_at,
                "ttl_seconds": uploaded_file.ttl_seconds,
            }
        )

        return uploaded_file

    def get(self, file_id: str) -> UploadedFile:
        """获取文件元数据

        Args:
            file_id: 文件 ID

        Returns:
            UploadedFile: 文件元数据

        Raises:
            FileNotFoundError: 文件不存在或已过期
        """
        with self._files_lock:
            uploaded_file = self._files.get(file_id)

        if uploaded_file is None:
            record = self.store.get_upload(file_id)
            if not record:
                raise FileNotFoundError(f"文件不存在: {file_id}")
            uploaded_file = UploadedFile(
                file_id=record["file_id"],
                original_name=record["original_name"],
                size=int(record["size"]),
                mime_type=record.get("mime_type", "application/octet-stream"),
                file_type=record["file_type"],
                stored_path=Path(record["stored_path"]),
                file_hash=record.get("file_hash"),
                created_at=float(record.get("created_at", time.time())),
                ttl_seconds=int(record.get("ttl_seconds", self.ttl_seconds)),
            )
            with self._files_lock:
                self._files[file_id] = uploaded_file

        # 检查过期
        if uploaded_file.is_expired():
            self._delete_file(file_id)
            raise FileNotFoundError(f"文件已过期: {file_id}")

        # 检查物理文件
        if not uploaded_file.stored_path.exists():
            with self._files_lock:
                if file_id in self._files:
                    del self._files[file_id]
            self.store.delete_upload(file_id)
            raise FileNotFoundError(f"文件已被删除: {file_id}")

        return uploaded_file

    def get_path(self, file_id: str) -> Path:
        """获取文件存储路径

        Args:
            file_id: 文件 ID

        Returns:
            Path: 文件存储路径
        """
        return self.get(file_id).stored_path

    def resolve_file_ids(
        self,
        video_file_id: Optional[str] = None,
        audio_file_id: Optional[str] = None,
        subtitle_file_id: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """将 file_id 解析为实际路径

        Args:
            video_file_id: 视频文件 ID
            audio_file_id: 音频文件 ID
            subtitle_file_id: 字幕文件 ID

        Returns:
            Dict: 包含 video_path, audio_path, subtitle_path 的字典

        Raises:
            FileNotFoundError: 文件不存在
            FileTypeError: 文件类型不匹配
        """
        result = {
            "video_path": None,
            "audio_path": None,
            "subtitle_path": None,
        }

        if video_file_id:
            uploaded = self.get(video_file_id)
            if uploaded.file_type != "video":
                raise FileTypeError(f"file_id {video_file_id} 不是视频文件")
            result["video_path"] = str(uploaded.stored_path)

        if audio_file_id:
            uploaded = self.get(audio_file_id)
            if uploaded.file_type != "audio":
                raise FileTypeError(f"file_id {audio_file_id} 不是音频文件")
            result["audio_path"] = str(uploaded.stored_path)

        if subtitle_file_id:
            uploaded = self.get(subtitle_file_id)
            if uploaded.file_type != "subtitle":
                raise FileTypeError(f"file_id {subtitle_file_id} 不是字幕文件")
            result["subtitle_path"] = str(uploaded.stored_path)

        return result

    def _delete_record(self, file_id: Optional[str]) -> None:
        if not file_id:
            return
        self.store.delete_upload(file_id)

    def _cleanup_physical_file(self, stored_path: Path) -> None:
        try:
            if stored_path.exists():
                stored_path.unlink()
            if stored_path.parent.exists() and not any(stored_path.parent.iterdir()):
                stored_path.parent.rmdir()
        except OSError:
            pass

    def _delete_file(self, file_id: str) -> bool:
        """删除文件（内部方法，需在锁内调用）"""
        if file_id not in self._files:
            return False

        uploaded_file = self._files[file_id]

        # 删除物理文件
        self._cleanup_physical_file(uploaded_file.stored_path)

        # 从映射表移除 + 持久化删除
        del self._files[file_id]
        self.store.delete_upload(file_id)
        return True

    def delete(self, file_id: str) -> bool:
        """删除文件

        Args:
            file_id: 文件 ID

        Returns:
            bool: 是否删除成功
        """
        with self._files_lock:
            return self._delete_file(file_id)

    def cleanup_expired(self) -> int:
        """清理过期文件

        Returns:
            int: 清理的文件数量
        """
        cleaned = 0
        with self._files_lock:
            expired_ids = [
                fid for fid, f in self._files.items() if f.is_expired()
            ]
            for file_id in expired_ids:
                if self._delete_file(file_id):
                    cleaned += 1
        return cleaned

    def list_files(self) -> list[Dict]:
        """列出所有未过期文件"""
        with self._files_lock:
            return [
                f.to_dict() for f in self._files.values()
                if not f.is_expired()
            ]


# 全局单例
_storage: Optional[FileStorage] = None


def get_file_storage() -> FileStorage:
    """获取全局 FileStorage 实例"""
    global _storage
    if _storage is None:
        _storage = FileStorage()
    return _storage
