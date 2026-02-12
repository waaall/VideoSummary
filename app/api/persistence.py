"""
基于 SQLite 的持久化存储层。

管理三类核心数据：
- uploads: 用户上传文件的元数据
- cache_entries: 视频摘要缓存条目（来源、状态、摘要文本、打包产物路径等）
- cache_jobs: 缓存生成任务的执行记录，通过外键关联 cache_entries

线程安全策略：单连接 + threading.Lock 互斥访问，配合 WAL 模式减少写锁冲突。
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import WORK_PATH


DEFAULT_DB_PATH = WORK_PATH / "metadata.db"


class SQLiteStore:
    """基于 SQLite 的持久化存储，提供线程安全的读写接口。

    采用单连接模式，所有读写操作通过 threading.Lock 串行化，
    适用于中低并发场景（如单进程 API 服务）。
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # check_same_thread=False 允许多线程共用同一连接，由 _lock 保证安全
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        # 使查询结果支持按列名访问（dict-like）
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            # WAL 模式：允许读写并发，减少锁等待
            self._conn.execute("PRAGMA journal_mode=WAL")
            # NORMAL 同步级别：在 WAL 模式下兼顾性能与数据安全
            self._conn.execute("PRAGMA synchronous=NORMAL")
            # 启用外键约束（SQLite 默认关闭）
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        """初始化数据库表结构，并通过 ALTER TABLE 兼容旧版本数据库的增量迁移。"""
        with self._conn:
            # 清理已废弃的旧表（早期 DAG 执行模型的遗留结构）
            self._conn.execute("DROP TABLE IF EXISTS run_nodes")
            self._conn.execute("DROP TABLE IF EXISTS runs")

            # ---------- uploads 表 ----------
            # 记录用户上传文件的元数据，file_id 为主键
            # ttl_seconds: 文件过期时间（秒），用于定期清理
            # file_hash: 文件内容哈希，用于去重判断
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

            # ---------- cache_entries 表 ----------
            # 缓存条目：每个唯一的 (来源+配置) 组合对应一条记录
            # source_type: 来源类型（如 "file", "url"）
            # source_ref: 来源标识（如文件 hash 或 URL）
            # source_name: 来源的可读名称（如原始文件名）
            # status: 处理状态（pending / processing / done / error）
            # profile_version: 处理配置版本号，配置变化时缓存失效
            # summary_text: 生成的摘要文本
            # bundle_path: 打包产物的存储路径
            # last_accessed: 最后访问时间，用于 LRU 淘汰策略
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    source_name TEXT,
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

            # ---------- cache_jobs 表 ----------
            # 缓存生成任务：同一 cache_entry 可能因重试产生多条 job 记录
            # 通过外键关联 cache_entries，删除 cache_entry 时需先删除关联的 jobs
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

            # ---------- 索引 ----------
            # 按来源查找缓存条目的联合索引
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_entries_source
                ON cache_entries(source_type, source_ref)
                """
            )
            # 按状态筛选缓存条目
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_entries_status
                ON cache_entries(status)
                """
            )
            # 按 cache_key 查找关联的 jobs
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_jobs_cache_key
                ON cache_jobs(cache_key)
                """
            )

            # ---------- 增量迁移 ----------
            # 对旧版数据库新增列，ALTER TABLE ADD COLUMN 在列已存在时会抛出
            # OperationalError，捕获后跳过即可
            try:
                self._conn.execute("ALTER TABLE uploads ADD COLUMN file_hash TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                self._conn.execute(
                    "ALTER TABLE cache_entries ADD COLUMN profile_version TEXT"
                )
            except sqlite3.OperationalError:
                pass
            try:
                self._conn.execute(
                    "ALTER TABLE cache_entries ADD COLUMN source_name TEXT"
                )
            except sqlite3.OperationalError:
                pass

    # ============ Uploads ============

    def upsert_upload(self, record: Dict[str, Any]) -> None:
        """插入或更新上传文件记录。

        使用 INSERT ... ON CONFLICT DO UPDATE 实现 upsert 语义，
        以 file_id 为冲突判断键，冲突时覆盖全部字段。
        """
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
        """按 file_id 删除上传记录。"""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM uploads WHERE file_id = ?", (file_id,))

    def get_upload(self, file_id: str) -> Optional[Dict[str, Any]]:
        """按 file_id 查询单条上传记录，不存在时返回 None。"""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM uploads WHERE file_id = ?", (file_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_uploads(self) -> List[Dict[str, Any]]:
        """列出所有上传记录。"""
        with self._lock:
            rows = self._conn.execute("SELECT * FROM uploads").fetchall()
        return [dict(row) for row in rows]

    # ============ Cache Entries ============

    def create_cache_entry(
        self,
        cache_key: str,
        source_type: str,
        source_ref: str,
        source_name: Optional[str] = None,
        bundle_path: Optional[str] = None,
        profile_version: Optional[str] = None,
    ) -> None:
        """创建缓存条目，初始状态为 'pending'。"""
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO cache_entries (
                    cache_key, source_type, source_ref, source_name, status, profile_version,
                    bundle_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    source_type,
                    source_ref,
                    source_name,
                    profile_version or "",
                    bundle_path,
                    now,
                    now,
                ),
            )

    def get_cache_entry(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """按 cache_key 查询缓存条目。"""
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
        """按来源类型和来源标识查询缓存条目（利用联合索引）。"""
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
        source_name: Optional[str] = None,
    ) -> None:
        """动态更新缓存条目的指定字段。

        仅传入非 None 的参数会被更新，updated_at 始终自动刷新。
        通过动态拼接 SET 子句实现按需更新，避免覆盖未指定的字段。
        """
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
        if source_name is not None:
            updates.append("source_name = ?")
            params.append(source_name)

        params.append(cache_key)

        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE cache_entries SET {', '.join(updates)} WHERE cache_key = ?",
                params,
            )

    def touch_cache_entry(self, cache_key: str) -> None:
        """刷新缓存条目的 last_accessed 时间戳，用于 LRU 淘汰判定。"""
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE cache_entries SET last_accessed = ? WHERE cache_key = ?",
                (now, cache_key),
            )

    def delete_cache_entry(self, cache_key: str) -> None:
        """删除缓存条目及其关联的所有 jobs（先删子表再删主表，满足外键约束）。"""
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
        """按条件筛选缓存条目列表。

        支持按 status 和 source_type 过滤，结果按 order_by 排序并限制数量。
        """
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
        """查询过期的缓存条目，供 GC（垃圾回收）使用。

        判定逻辑：COALESCE(last_accessed, updated_at) < 当前时间 - max_age_seconds
        优先使用 last_accessed，未被访问过的条目回退到 updated_at。
        结果按最久未访问排序，便于 GC 从最旧的开始清理。
        """
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
        """创建缓存生成任务，初始状态为 'pending'。"""
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
        """按 job_id 查询单条任务记录。"""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cache_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def get_cache_jobs_by_cache_key(self, cache_key: str) -> List[Dict[str, Any]]:
        """查询指定 cache_key 下的所有任务，按创建时间倒序排列。"""
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
        """获取指定 cache_key 下最新的一条任务记录（用于查询当前处理进度）。"""
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
        """动态更新任务状态和/或错误信息，updated_at 始终自动刷新。"""
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
        """按 job_id 删除单条任务记录。"""
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM cache_jobs WHERE job_id = ?", (job_id,)
            )

    # ============ Uploads (file_hash 去重支持) ============

    def update_upload_file_hash(self, file_id: str, file_hash: str) -> None:
        """为已有上传记录补充文件内容哈希值（用于异步计算 hash 后回填）。"""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE uploads SET file_hash = ? WHERE file_id = ?",
                (file_hash, file_id),
            )

    def list_uploads_by_hash(self, file_hash: str) -> List[Dict[str, Any]]:
        """按文件内容哈希查询所有匹配的上传记录，按创建时间倒序排列。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM uploads WHERE file_hash = ? ORDER BY created_at DESC",
                (file_hash,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_upload_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """按文件哈希查找未过期的上传记录，用于文件去重。

        遍历同 hash 的所有记录，优先返回第一条 TTL 未过期的记录；
        全部过期则返回 None，表示需要重新上传。
        """
        records = self.list_uploads_by_hash(file_hash)
        if not records:
            return None
        now = time.time()
        for record in records:
            created_at = float(record.get("created_at", 0))
            ttl_seconds = int(record.get("ttl_seconds", 0))
            # 判断 TTL 是否仍有效
            if created_at + ttl_seconds >= now:
                return record
        return None


# ---------- 模块级单例 ----------

_store: Optional[SQLiteStore] = None


def get_store(db_path: Optional[Path] = None) -> SQLiteStore:
    """获取 SQLiteStore 单例。

    传入 db_path 时创建独立实例（用于测试等场景）；
    不传时返回全局单例，进程内共享同一连接。
    """
    global _store
    if db_path is not None:
        return SQLiteStore(db_path=db_path)
    if _store is None:
        _store = SQLiteStore()
    return _store
