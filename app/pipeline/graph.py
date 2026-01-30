"""DAG 图结构和拓扑排序"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from app.api.schemas import PipelineConfig, PipelineEdgeConfig


class CyclicDependencyError(Exception):
    """循环依赖错误"""

    pass


class InvalidGraphError(Exception):
    """图结构无效错误"""

    pass


class PipelineGraph:
    """
    DAG 图结构

    解析 PipelineConfig 构建有向无环图，支持：
    - 拓扑排序
    - 循环依赖检测
    - 前驱/后继节点查询
    - 边条件查询
    """

    def __init__(self, config: PipelineConfig):
        """
        从 PipelineConfig 构建图

        Args:
            config: 管线配置

        Raises:
            InvalidGraphError: 图结构无效
            CyclicDependencyError: 存在循环依赖
        """
        self.config = config

        # 节点 ID 集合
        self.node_ids: Set[str] = {node.id for node in config.nodes}

        # 节点 ID -> 节点配置映射
        self.node_configs: Dict[str, "PipelineConfig"] = {
            node.id: node for node in config.nodes
        }

        # 邻接表：source -> [(target, condition), ...]
        self._adjacency: Dict[str, List[Tuple[str, Optional[str]]]] = defaultdict(list)

        # 反向邻接表：target -> [(source, condition), ...]
        self._reverse_adjacency: Dict[str, List[Tuple[str, Optional[str]]]] = defaultdict(list)

        # 入度表
        self._in_degree: Dict[str, int] = {node_id: 0 for node_id in self.node_ids}

        # 边条件映射：(source, target) -> condition
        self._edge_conditions: Dict[Tuple[str, str], Optional[str]] = {}

        # 构建图
        self._build_graph(config.edges)

        # 检测循环依赖
        self._detect_cycle()

        # 确定入口节点
        self.entrypoint = self._resolve_entrypoint(config.entrypoint)

    def _build_graph(self, edges: List[PipelineEdgeConfig]) -> None:
        """构建邻接表"""
        for edge in edges:
            # 验证边的端点存在
            if edge.source not in self.node_ids:
                raise InvalidGraphError(f"边的源节点不存在: {edge.source}")
            if edge.target not in self.node_ids:
                raise InvalidGraphError(f"边的目标节点不存在: {edge.target}")

            # 添加边
            self._adjacency[edge.source].append((edge.target, edge.condition))
            self._reverse_adjacency[edge.target].append((edge.source, edge.condition))
            self._in_degree[edge.target] += 1
            self._edge_conditions[(edge.source, edge.target)] = edge.condition

    def _detect_cycle(self) -> None:
        """使用 DFS 检测循环依赖"""
        # 0: 未访问, 1: 访问中, 2: 已完成
        state: Dict[str, int] = {node_id: 0 for node_id in self.node_ids}
        path: List[str] = []

        def dfs(node_id: str) -> bool:
            """返回 True 表示发现环"""
            if state[node_id] == 1:
                # 找到环，提取环路径
                cycle_start = path.index(node_id)
                cycle = path[cycle_start:] + [node_id]
                raise CyclicDependencyError(
                    f"检测到循环依赖: {' -> '.join(cycle)}"
                )
            if state[node_id] == 2:
                return False

            state[node_id] = 1
            path.append(node_id)

            for target, _ in self._adjacency[node_id]:
                dfs(target)

            path.pop()
            state[node_id] = 2
            return False

        for node_id in self.node_ids:
            if state[node_id] == 0:
                dfs(node_id)

    def _resolve_entrypoint(self, explicit_entrypoint: Optional[str]) -> str:
        """确定入口节点"""
        if explicit_entrypoint:
            if explicit_entrypoint not in self.node_ids:
                raise InvalidGraphError(f"指定的入口节点不存在: {explicit_entrypoint}")
            return explicit_entrypoint

        # 自动选择入度为 0 的节点
        zero_in_degree = [
            node_id for node_id, degree in self._in_degree.items() if degree == 0
        ]

        if not zero_in_degree:
            raise InvalidGraphError("没有入口节点（所有节点都有前驱）")

        if len(zero_in_degree) > 1:
            # 多个入口节点，选择第一个（按配置顺序）
            for node in self.config.nodes:
                if node.id in zero_in_degree:
                    return node.id

        return zero_in_degree[0]

    def topological_sort(self) -> List[str]:
        """
        返回拓扑排序后的节点 ID 列表

        Returns:
            按拓扑顺序排列的节点 ID 列表
        """
        # Kahn's algorithm
        in_degree = self._in_degree.copy()
        queue = deque(
            node_id for node_id, degree in in_degree.items() if degree == 0
        )
        result: List[str] = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)

            for target, _ in self._adjacency[node_id]:
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)

        # 如果结果数量不等于节点数量，说明有环（理论上不会发生，因为已经检测过）
        if len(result) != len(self.node_ids):
            raise CyclicDependencyError("拓扑排序失败，存在循环依赖")

        return result

    def get_predecessors(self, node_id: str) -> List[Tuple[str, Optional[str]]]:
        """
        获取节点的前驱节点

        Args:
            node_id: 节点 ID

        Returns:
            前驱节点列表：[(前驱 ID, 边条件), ...]
        """
        return list(self._reverse_adjacency[node_id])

    def get_successors(self, node_id: str) -> List[Tuple[str, Optional[str]]]:
        """
        获取节点的后继节点

        Args:
            node_id: 节点 ID

        Returns:
            后继节点列表：[(后继 ID, 边条件), ...]
        """
        return list(self._adjacency[node_id])

    def get_edge_condition(self, source: str, target: str) -> Optional[str]:
        """
        获取边的条件表达式

        Args:
            source: 源节点 ID
            target: 目标节点 ID

        Returns:
            条件表达式，无条件时返回 None
        """
        return self._edge_conditions.get((source, target))

    def get_nodes_without_predecessors(self) -> List[str]:
        """获取没有前驱的节点（入口节点）"""
        return [
            node_id for node_id, degree in self._in_degree.items() if degree == 0
        ]

    def __repr__(self) -> str:
        return (
            f"PipelineGraph(nodes={len(self.node_ids)}, "
            f"edges={sum(len(targets) for targets in self._adjacency.values())}, "
            f"entrypoint={self.entrypoint!r})"
        )
