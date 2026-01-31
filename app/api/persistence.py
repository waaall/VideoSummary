"""SQLite-backed persistence for uploads and pipeline runs."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import WORK_PATH


DEFAULT_DB_PATH = WORK_PATH / "metadata.db"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), default=str)


def _json_loads(value: Optional[str]) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


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
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    file_id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mime_type TEXT,
                    file_type TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl_seconds INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    started_at REAL,
                    ended_at REAL,
                    summary_text TEXT,
                    context_json TEXT,
                    error TEXT,
                    pipeline_json TEXT,
                    inputs_json TEXT,
                    thresholds_json TEXT,
                    options_json TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_nodes (
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at REAL,
                    ended_at REAL,
                    elapsed_ms INTEGER,
                    error TEXT,
                    retryable INTEGER DEFAULT 0,
                    output_keys TEXT,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (run_id, node_id)
                )
                """
            )

    # ============ Uploads ============

    def upsert_upload(self, record: Dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO uploads (
                    file_id, original_name, size, mime_type, file_type,
                    stored_path, created_at, ttl_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    original_name=excluded.original_name,
                    size=excluded.size,
                    mime_type=excluded.mime_type,
                    file_type=excluded.file_type,
                    stored_path=excluded.stored_path,
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

    # ============ Runs ============

    def create_run(
        self,
        run_id: str,
        status: str,
        pipeline: Optional[Dict[str, Any]],
        inputs: Optional[Dict[str, Any]],
        thresholds: Optional[Dict[str, Any]],
        options: Optional[Dict[str, Any]],
    ) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO runs (
                    run_id, status, created_at, updated_at,
                    pipeline_json, inputs_json, thresholds_json, options_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    status,
                    now,
                    now,
                    _json_dumps(pipeline) if pipeline is not None else None,
                    _json_dumps(inputs) if inputs is not None else None,
                    _json_dumps(thresholds) if thresholds is not None else None,
                    _json_dumps(options) if options is not None else None,
                ),
            )

    def update_run_status(
        self,
        run_id: str,
        status: str,
        *,
        started_at: Optional[float] = None,
        ended_at: Optional[float] = None,
        summary_text: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE runs
                SET status = ?,
                    updated_at = ?,
                    started_at = COALESCE(?, started_at),
                    ended_at = COALESCE(?, ended_at),
                    summary_text = COALESCE(?, summary_text),
                    context_json = COALESCE(?, context_json),
                    error = COALESCE(?, error)
                WHERE run_id = ?
                """,
                (
                    status,
                    now,
                    started_at,
                    ended_at,
                    summary_text,
                    _json_dumps(context) if context is not None else None,
                    error,
                    run_id,
                ),
            )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["pipeline"] = _json_loads(data.pop("pipeline_json", None))
        data["inputs"] = _json_loads(data.pop("inputs_json", None))
        data["thresholds"] = _json_loads(data.pop("thresholds_json", None))
        data["options"] = _json_loads(data.pop("options_json", None))
        data["context"] = _json_loads(data.pop("context_json", None)) or {}
        return data

    def upsert_run_node(
        self,
        run_id: str,
        node_id: str,
        status: str,
        *,
        started_at: Optional[float] = None,
        ended_at: Optional[float] = None,
        elapsed_ms: Optional[int] = None,
        error: Optional[str] = None,
        retryable: bool = False,
        output_keys: Optional[List[str]] = None,
    ) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO run_nodes (
                    run_id, node_id, status, started_at, ended_at,
                    elapsed_ms, error, retryable, output_keys, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, node_id) DO UPDATE SET
                    status=excluded.status,
                    started_at=COALESCE(excluded.started_at, run_nodes.started_at),
                    ended_at=COALESCE(excluded.ended_at, run_nodes.ended_at),
                    elapsed_ms=COALESCE(excluded.elapsed_ms, run_nodes.elapsed_ms),
                    error=COALESCE(excluded.error, run_nodes.error),
                    retryable=excluded.retryable,
                    output_keys=COALESCE(excluded.output_keys, run_nodes.output_keys),
                    updated_at=excluded.updated_at
                """,
                (
                    run_id,
                    node_id,
                    status,
                    started_at,
                    ended_at,
                    elapsed_ms,
                    error,
                    1 if retryable else 0,
                    _json_dumps(output_keys) if output_keys is not None else None,
                    now,
                ),
            )

    def list_run_nodes(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM run_nodes
                WHERE run_id = ?
                ORDER BY started_at IS NULL, started_at, updated_at
                """,
                (run_id,),
            ).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["retryable"] = bool(data.get("retryable"))
            data["output_keys"] = _json_loads(data.get("output_keys"))
            results.append(data)
        return results


_store: Optional[SQLiteStore] = None


def get_store(db_path: Optional[Path] = None) -> SQLiteStore:
    global _store
    if db_path is not None:
        return SQLiteStore(db_path=db_path)
    if _store is None:
        _store = SQLiteStore()
    return _store
