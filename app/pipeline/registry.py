"""节点注册表 - 节点类型到类的映射"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type

from app.pipeline.node_base import PipelineNode


class NodeNotFoundError(Exception):
    """节点类型未注册"""

    pass


class NodeRegistry:
    """
    节点注册表

    管理节点类型名称到类的映射，支持：
    - 注册节点类型
    - 根据类型名创建节点实例
    - 获取已注册的所有类型
    """

    def __init__(self):
        self._registry: Dict[str, Type[PipelineNode]] = {}

    def register(
        self, type_name: str, node_class: Type[PipelineNode]
    ) -> "NodeRegistry":
        """
        注册节点类型

        Args:
            type_name: 类型名称
            node_class: 节点类

        Returns:
            self（支持链式调用）
        """
        self._registry[type_name] = node_class
        return self

    def create(
        self, type_name: str, node_id: str, params: Optional[Dict[str, Any]] = None
    ) -> PipelineNode:
        """
        根据类型名创建节点实例

        Args:
            type_name: 类型名称
            node_id: 节点 ID
            params: 节点参数

        Returns:
            节点实例

        Raises:
            NodeNotFoundError: 类型未注册
        """
        if type_name not in self._registry:
            raise NodeNotFoundError(
                f"节点类型未注册: {type_name}，"
                f"可用类型: {list(self._registry.keys())}"
            )

        node_class = self._registry[type_name]
        return node_class(node_id=node_id, params=params)

    def get_registered_types(self) -> list[str]:
        """获取已注册的所有类型名称"""
        return list(self._registry.keys())

    def has_type(self, type_name: str) -> bool:
        """检查类型是否已注册"""
        return type_name in self._registry

    def __contains__(self, type_name: str) -> bool:
        return self.has_type(type_name)

    def __repr__(self) -> str:
        return f"NodeRegistry(types={self.get_registered_types()})"


# 全局默认注册表（单例）
_default_registry: Optional[NodeRegistry] = None


def get_default_registry() -> NodeRegistry:
    """
    获取默认注册表（单例）

    首次调用时会注册所有内置节点
    """
    global _default_registry

    if _default_registry is None:
        _default_registry = NodeRegistry()
        _register_builtin_nodes(_default_registry)

    return _default_registry


def _register_builtin_nodes(registry: NodeRegistry) -> None:
    """注册内置节点（使用真实实现）"""
    # 延迟导入避免循环依赖
    from app.pipeline.nodes.core import (
        InputNode,
        FetchMetadataNode,
        DownloadSubtitleNode,
        DownloadVideoNode,
        ParseSubtitleNode,
        ValidateSubtitleNode,
        ExtractAudioNode,
        TranscribeNode,
        DetectSilenceNode,
        TextSummarizeNode,
        SampleFramesNode,
        VlmSummarizeNode,
        MergeSummaryNode,
    )

    # 输入验证
    registry.register("InputNode", InputNode)

    # 元数据获取
    registry.register("FetchMetadataNode", FetchMetadataNode)

    # 下载相关
    registry.register("DownloadSubtitleNode", DownloadSubtitleNode)
    registry.register("DownloadVideoNode", DownloadVideoNode)

    # 字幕处理
    registry.register("ParseSubtitleNode", ParseSubtitleNode)
    registry.register("ValidateSubtitleNode", ValidateSubtitleNode)

    # 音频处理
    registry.register("ExtractAudioNode", ExtractAudioNode)
    registry.register("DetectSilenceNode", DetectSilenceNode)

    # 转录
    registry.register("TranscribeNode", TranscribeNode)

    # 总结生成
    registry.register("TextSummarizeNode", TextSummarizeNode)

    # VLM 相关（阶段4）
    registry.register("SampleFramesNode", SampleFramesNode)
    registry.register("VlmSummarizeNode", VlmSummarizeNode)
    registry.register("MergeSummaryNode", MergeSummaryNode)
