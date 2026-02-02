"""SQLite-backed persistence for uploads and cache metadata."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import WORK_PATH


DEFAULT_DB_PATH = WORK_PATH / "metadata.db"




class SQLiteStore:
    """Thin SQLite wrapper with thread-safe access."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            # 清理旧结构（无 DAG 重构）
            self._conn.execute("DROP TABLE IF EXISTS run_nodes")
            self._conn.execute("DROP TABLE IF EXISTS runs")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    file_id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mime_type TEXT,
                    file_type TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    file_hash TEXT,
                    created_at REAL NOT NULL,
                    ttl_seconds INTEGER NOT NULL
                )
                """
            )
            # 缓存条目表
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    profile_version TEXT NOT NULL,
                    summary_text TEXT,
                    bundle_path TEXT,
                    error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_accessed REAL
                )
                """
            )
            # 缓存任务表
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_jobs (
                    job_id TEXT PRIMARY KEY,
                    cache_key TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    error TEXT,
                    FOREIGN KEY (cache_key) REFERENCES cache_entries(cache_key)
                )
                """
            )
            # cache_entries 索引
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_entries_source
                ON cache_entries(source_type, source_ref)
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_entries_status
                ON cache_entries(status)
                """
            )
            # cache_jobs 索引
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_jobs_cache_key
                ON cache_jobs(cache_key)
                """
            )
            # uploads 表新增 file_hash 列（如果不存在）
            try:
                self._conn.execute("ALTER TABLE uploads ADD COLUMN file_hash TEXT")
            except sqlite3.OperationalError:
                pass  # 列已存在
            # cache_entries 表新增 profile_version 列（如果不存在）
            try:
                self._conn.execute(
                    "ALTER TABLE cache_entries ADD COLUMN profile_version TEXT"
                )
            except sqlite3.OperationalError:
                pass  # 列已存在

    # ============ Uploads ============

    def upsert_upload(self, record: Dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO uploads (
                    file_id, original_name, size, mime_type, file_type,
                    stored_path, file_hash, created_at, ttl_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    original_name=excluded.original_name,
                    size=excluded.size,
                    mime_type=excluded.mime_type,
                    file_type=excluded.file_type,
                    stored_path=excluded.stored_path,
                    file_hash=excluded.file_hash,
                    created_at=excluded.created_at,
                    ttl_seconds=excluded.ttl_seconds
                """,
                (
                    record["file_id"],
                    record["original_name"],
                    record["size"],
                    record.get("mime_type"),
                    record["file_type"],
                    record["stored_path"],
                    record.get("file_hash"),
                    record["created_at"],
                    record["ttl_seconds"],
                ),
            )

    def delete_upload(self, file_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM uploads WHERE file_id = ?", (file_id,))

    def get_upload(self, file_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM uploads WHERE file_id = ?", (file_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_uploads(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM uploads").fetchall()
        return [dict(row) for row in rows]

    # ============ Cache Entries ============

    def create_cache_entry(
        self,
        cache_key: str,
        source_type: str,
        source_ref: str,
        bundle_path: Optional[str] = None,
        profile_version: Optional[str] = None,
    ) -> None:
        """创建缓存条目"""
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO cache_entries (
                    cache_key, source_type, source_ref, status, profile_version,
                    bundle_path, created_at, updated_at
                ) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (cache_key, source_type, source_ref, profile_version or "", bundle_path, now, now),
            )

    def get_cache_entry(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存条目"""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cache_entries WHERE cache_key = ?", (cache_key,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def get_cache_entry_by_source(
        self, source_type: str, source_ref: str
    ) -> Optional[Dict[str, Any]]:
        """按来源查询缓存条目"""
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM cache_entries
                WHERE source_type = ? AND source_ref = ?
                """,
                (source_type, source_ref),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def update_cache_entry(
        self,
        cache_key: str,
        *,
        status: Optional[str] = None,
        summary_text: Optional[str] = None,
        bundle_path: Optional[str] = None,
        error: Optional[str] = None,
        profile_version: Optional[str] = None,
        last_accessed: Optional[float] = None,
    ) -> None:
        """更新缓存条目"""
        now = time.time()
        updates = ["updated_at = ?"]
        params: List[Any] = [now]

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if summary_text is not None:
            updates.append("summary_text = ?")
            params.append(summary_text)
        if bundle_path is not None:
            updates.append("bundle_path = ?")
            params.append(bundle_path)
        if error is not None:
            updates.append("error = ?")
            params.append(error)
        if profile_version is not None:
            updates.append("profile_version = ?")
            params.append(profile_version)
        if last_accessed is not None:
            updates.append("last_accessed = ?")
            params.append(last_accessed)

        params.append(cache_key)

        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE cache_entries SET {', '.join(updates)} WHERE cache_key = ?",
                params,
            )

    def touch_cache_entry(self, cache_key: str) -> None:
        """更新 last_accessed 时间"""
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE cache_entries SET last_accessed = ? WHERE cache_key = ?",
                (now, cache_key),
            )

    def delete_cache_entry(self, cache_key: str) -> None:
        """删除缓存条目"""
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM cache_jobs WHERE cache_key = ?", (cache_key,)
            )
            self._conn.execute(
                "DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,)
            )

    def list_cache_entries(
        self,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 100,
        order_by: str = "updated_at DESC",
    ) -> List[Dict[str, Any]]:
        """列出缓存条目"""
        conditions = []
        params: List[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if source_type:
            conditions.append("source_type = ?")
            params.append(source_type)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM cache_entries
                {where_clause}
                ORDER BY {order_by}
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [dict(row) for row in rows]

    def list_stale_cache_entries(
        self,
        max_age_seconds: float,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出过期的缓存条目（用于 GC）"""
        cutoff = time.time() - max_age_seconds
        conditions = ["COALESCE(last_accessed, updated_at) < ?"]
        params: List[Any] = [cutoff]

        if status:
            conditions.append("status = ?")
            params.append(status)

        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM cache_entries
                WHERE {' AND '.join(conditions)}
                ORDER BY COALESCE(last_accessed, updated_at) ASC
                """,
                params,
            ).fetchall()

        return [dict(row) for row in rows]

    # ============ Cache Jobs ============

    def create_cache_job(self, job_id: str, cache_key: str) -> None:
        """创建缓存任务"""
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO cache_jobs (
                    job_id, cache_key, status, created_at, updated_at
                ) VALUES (?, ?, 'pending', ?, ?)
                """,
                (job_id, cache_key, now, now),
            )

    def get_cache_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存任务"""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cache_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def get_cache_jobs_by_cache_key(self, cache_key: str) -> List[Dict[str, Any]]:
        """获取指定缓存的所有任务"""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM cache_jobs
                WHERE cache_key = ?
                ORDER BY created_at DESC
                """,
                (cache_key,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_latest_job_for_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取指定缓存的最新任务"""
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM cache_jobs
                WHERE cache_key = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (cache_key,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def update_cache_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """更新缓存任务"""
        now = time.time()
        updates = ["updated_at = ?"]
        params: List[Any] = [now]

        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if error is not None:
            updates.append("error = ?")
            params.append(error)

        params.append(job_id)

        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE cache_jobs SET {', '.join(updates)} WHERE job_id = ?",
                params,
            )

    def delete_cache_job(self, job_id: str) -> None:
        """删除缓存任务"""
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM cache_jobs WHERE job_id = ?", (job_id,)
            )

    # ============ Uploads (file_hash 支持) ============

    def update_upload_file_hash(self, file_id: str, file_hash: str) -> None:
        """更新上传文件的 hash"""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE uploads SET file_hash = ? WHERE file_id = ?",
                (file_hash, file_id),
            )

    def get_upload_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """按文件 hash 查询上传记录"""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM uploads WHERE file_hash = ?", (file_hash,)
            ).fetchone()
        if not row:
            return None
        return dict(row)


_store: Optional[SQLiteStore] = None


def get_store(db_path: Optional[Path] = None) -> SQLiteStore:
    global _store
    if db_path is not None:
        return SQLiteStore(db_path=db_path)
    if _store is None:
        _store = SQLiteStore()
    return _store
