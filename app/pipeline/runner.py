"""管线执行器 - 按拓扑顺序执行节点"""

from __future__ import annotations

import time
from typing import Dict, Optional, Set

from app.pipeline.condition import ConditionEvaluationError, evaluate_condition
from app.pipeline.context import PipelineContext
from app.pipeline.graph import PipelineGraph
from app.pipeline.node_base import PipelineNode
from app.pipeline.registry import NodeRegistry, get_default_registry


class PipelineExecutionError(Exception):
    """管线执行错误"""

    pass


class PipelineRunner:
    """
    管线执行器

    按拓扑顺序执行 DAG 中的节点，支持：
    - 条件分支（前驱边条件评估）
    - 执行追踪（trace）
    - 节点跳过（前驱条件不满足）
    """

    def __init__(
        self,
        graph: PipelineGraph,
        registry: Optional[NodeRegistry] = None,
    ):
        """
        初始化执行器

        Args:
            graph: DAG 图结构
            registry: 节点注册表，默认使用全局注册表
        """
        self.graph = graph
        self.registry = registry or get_default_registry()

        # 创建节点实例
        self._nodes: Dict[str, PipelineNode] = {}
        for node_id in graph.node_ids:
            node_config = graph.node_configs[node_id]
            self._nodes[node_id] = self.registry.create(
                type_name=node_config.type,
                node_id=node_id,
                params=node_config.params,
            )

    def run(self, ctx: PipelineContext) -> PipelineContext:
        """
        执行管线

        Args:
            ctx: 管线上下文

        Returns:
            执行后的上下文

        Raises:
            PipelineExecutionError: 执行失败
        """
        # 获取拓扑顺序
        sorted_nodes = self.graph.topological_sort()

        # 记录已执行和已跳过的节点
        executed: Set[str] = set()
        skipped: Set[str] = set()

        for node_id in sorted_nodes:
            # 检查是否应该执行该节点
            should_run, skip_reason = self._should_run_node(
                node_id, ctx, executed, skipped
            )

            if not should_run:
                # 跳过节点
                skipped.add(node_id)
                ctx.add_trace(
                    node_id=node_id,
                    status="skipped",
                    error=skip_reason,
                )
                continue

            # 执行节点
            node = self._nodes[node_id]
            start_time = time.time()

            try:
                node.run(ctx)
                elapsed_ms = int((time.time() - start_time) * 1000)
                executed.add(node_id)

                ctx.add_trace(
                    node_id=node_id,
                    status="completed",
                    elapsed_ms=elapsed_ms,
                    output_keys=node.get_output_keys(),
                )

            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)
                ctx.add_trace(
                    node_id=node_id,
                    status="failed",
                    elapsed_ms=elapsed_ms,
                    error=str(e),
                )
                raise PipelineExecutionError(
                    f"节点 {node_id} 执行失败: {e}"
                ) from e

        return ctx

    def _should_run_node(
        self,
        node_id: str,
        ctx: PipelineContext,
        executed: Set[str],
        skipped: Set[str],
    ) -> tuple[bool, Optional[str]]:
        """
        判断节点是否应该执行

        规则：
        1. 如果节点没有前驱，则执行
        2. 如果所有前驱都被跳过，则跳过
        3. 评估所有入边的条件：
           - 如果有任一入边条件满足（或无条件），则执行
           - 如果所有入边条件都不满足，则跳过

        Args:
            node_id: 节点 ID
            ctx: 上下文
            executed: 已执行的节点集合
            skipped: 已跳过的节点集合

        Returns:
            (是否执行, 跳过原因)
        """
        predecessors = self.graph.get_predecessors(node_id)

        # 无前驱节点，直接执行
        if not predecessors:
            return True, None

        # 检查是否所有前驱都被跳过
        active_predecessors = [
            (pred_id, cond) for pred_id, cond in predecessors
            if pred_id not in skipped
        ]

        if not active_predecessors:
            return False, "所有前驱节点都被跳过"

        # 评估入边条件
        namespace = ctx.to_eval_namespace()

        for pred_id, condition in active_predecessors:
            # 前驱必须已执行
            if pred_id not in executed:
                continue

            # 无条件或条件满足，则执行
            if condition is None:
                return True, None

            try:
                if evaluate_condition(condition, namespace):
                    return True, None
            except ConditionEvaluationError as e:
                # 条件评估失败，视为不满足
                continue

        # 所有入边条件都不满足
        return False, "所有入边条件都不满足"
