"""Pipeline 节点抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.pipeline.context import PipelineContext


class PipelineNode(ABC):
    """管线节点抽象基类，所有节点必须继承此类"""

    def __init__(self, node_id: str, params: Dict[str, Any] | None = None):
        """
        初始化节点

        Args:
            node_id: 节点唯一标识
            params: 节点参数配置
        """
        self.node_id = node_id
        self.params = params or {}

    @abstractmethod
    def run(self, ctx: PipelineContext) -> None:
        """
        执行节点逻辑，结果写入 ctx

        Args:
            ctx: 管线上下文
        """
        pass

    @abstractmethod
    def get_output_keys(self) -> List[str]:
        """
        返回该节点会输出的字段名列表

        Returns:
            字段名列表
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(node_id={self.node_id!r})"
