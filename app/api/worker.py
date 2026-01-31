"""In-process job queue and worker for pipeline execution."""
from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.api.persistence import get_store
from app.pipeline.context import PipelineContext
from app.pipeline.graph import CyclicDependencyError, InvalidGraphError, PipelineGraph
from app.pipeline.registry import NodeNotFoundError, get_default_registry
from app.pipeline.runner import PipelineExecutionError, PipelineRunner


@dataclass
class PipelineJob:
    run_id: str
    pipeline: Any
    inputs: Any
    thresholds: Any
    options: Dict[str, Any]


class PipelineJobQueue:
    def __init__(self, worker_count: int = 1) -> None:
        self.worker_count = worker_count
        self._queue: "queue.Queue[PipelineJob]" = queue.Queue()
        self._stop_event = threading.Event()
        self._workers: list[threading.Thread] = []

    def start(self) -> None:
        if self.worker_count <= 0:
            return
        if self._workers:
            return
        for idx in range(self.worker_count):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"pipeline-worker-{idx}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

    def stop(self) -> None:
        self._stop_event.set()

    def enqueue(self, job: PipelineJob) -> None:
        self._queue.put(job)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._process_job(job)
            finally:
                self._queue.task_done()

    def _process_job(self, job: PipelineJob) -> None:
        store = get_store()
        now = time.time()
        store.update_run_status(job.run_id, "running", started_at=now)

        ctx: Optional[PipelineContext] = None
        error: Optional[str] = None
        status = "failed"

        try:
            graph = PipelineGraph(job.pipeline)
            registry = get_default_registry()

            def on_node_start(node_id: str, started_at: float) -> None:
                store.upsert_run_node(
                    job.run_id,
                    node_id,
                    "running",
                    started_at=started_at,
                )

            def on_node_end(
                node_id: str,
                node_status: str,
                started_at: float,
                ended_at: float,
                elapsed_ms: Optional[int],
                node_error: Optional[str],
                output_keys: Optional[list],
            ) -> None:
                store.upsert_run_node(
                    job.run_id,
                    node_id,
                    node_status,
                    started_at=started_at,
                    ended_at=ended_at,
                    elapsed_ms=elapsed_ms,
                    error=node_error,
                    output_keys=output_keys,
                )

            ctx = PipelineContext.from_inputs(job.inputs, job.thresholds)
            ctx.run_id = job.run_id

            runner = PipelineRunner(
                graph,
                registry,
                on_node_start=on_node_start,
                on_node_end=on_node_end,
            )
            ctx = runner.run(ctx)

            failed_nodes = [t for t in ctx.trace if t.status == "failed"]
            status = "failed" if failed_nodes else "completed"
        except (CyclicDependencyError, InvalidGraphError) as e:
            error = f"图结构无效: {e}"
        except NodeNotFoundError as e:
            error = f"节点类型未注册: {e}"
        except PipelineExecutionError as e:
            error = str(e)
        except Exception as e:
            error = str(e)

        ended_at = time.time()
        summary_text = ctx.summary_text if ctx else None
        context = ctx.to_dict() if ctx else {}
        store.update_run_status(
            job.run_id,
            status,
            ended_at=ended_at,
            summary_text=summary_text,
            context=context,
            error=error,
        )


def generate_run_id() -> str:
    return f"r_{uuid.uuid4().hex}"


_queue: Optional[PipelineJobQueue] = None


def get_job_queue(worker_count: int = 1) -> PipelineJobQueue:
    global _queue
    if _queue is None:
        _queue = PipelineJobQueue(worker_count=worker_count)
    return _queue
