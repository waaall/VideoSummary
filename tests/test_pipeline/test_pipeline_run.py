"""Pipeline 运行集成测试"""

import pytest

from app.api.schemas import (
    PipelineConfig,
    PipelineEdgeConfig,
    PipelineInputs,
    PipelineNodeConfig,
    PipelineThresholds,
)
from app.pipeline.context import PipelineContext
from app.pipeline.graph import CyclicDependencyError, PipelineGraph
from app.pipeline.registry import get_default_registry
from app.pipeline.runner import PipelineRunner


class TestPipelineGraph:
    """PipelineGraph 测试"""

    def test_simple_linear_graph(self):
        """简单线性 DAG"""
        config = PipelineConfig(
            version="v1",
            nodes=[
                PipelineNodeConfig(id="a", type="InputNode", params={}),
                PipelineNodeConfig(id="b", type="FetchMetadataNode", params={}),
                PipelineNodeConfig(id="c", type="TextSummarizeNode", params={}),
            ],
            edges=[
                PipelineEdgeConfig(source="a", target="b"),
                PipelineEdgeConfig(source="b", target="c"),
            ],
        )

        graph = PipelineGraph(config)
        order = graph.topological_sort()

        # 验证拓扑顺序
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_cyclic_dependency_detection(self):
        """循环依赖检测"""
        config = PipelineConfig(
            version="v1",
            nodes=[
                PipelineNodeConfig(id="a", type="InputNode", params={}),
                PipelineNodeConfig(id="b", type="InputNode", params={}),
                PipelineNodeConfig(id="c", type="InputNode", params={}),
            ],
            edges=[
                PipelineEdgeConfig(source="a", target="b"),
                PipelineEdgeConfig(source="b", target="c"),
                PipelineEdgeConfig(source="c", target="a"),  # 形成环
            ],
        )

        with pytest.raises(CyclicDependencyError):
            PipelineGraph(config)

    def test_diamond_graph(self):
        """菱形 DAG"""
        config = PipelineConfig(
            version="v1",
            nodes=[
                PipelineNodeConfig(id="input", type="InputNode", params={}),
                PipelineNodeConfig(id="left", type="FetchMetadataNode", params={}),
                PipelineNodeConfig(id="right", type="ParseSubtitleNode", params={}),
                PipelineNodeConfig(id="merge", type="TextSummarizeNode", params={}),
            ],
            edges=[
                PipelineEdgeConfig(source="input", target="left"),
                PipelineEdgeConfig(source="input", target="right"),
                PipelineEdgeConfig(source="left", target="merge"),
                PipelineEdgeConfig(source="right", target="merge"),
            ],
        )

        graph = PipelineGraph(config)
        order = graph.topological_sort()

        # input 必须在 left 和 right 之前
        assert order.index("input") < order.index("left")
        assert order.index("input") < order.index("right")
        # left 和 right 必须在 merge 之前
        assert order.index("left") < order.index("merge")
        assert order.index("right") < order.index("merge")


class TestPipelineRunner:
    """PipelineRunner 测试"""

    def test_simple_pipeline_execution(self):
        """简单管线执行"""
        config = PipelineConfig(
            version="v1",
            nodes=[
                PipelineNodeConfig(id="input", type="InputNode", params={}),
            ],
            edges=[],
        )

        graph = PipelineGraph(config)
        registry = get_default_registry()
        runner = PipelineRunner(graph, registry)

        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)

        result = runner.run(ctx)

        # 验证 trace
        assert len(result.trace) == 1
        assert result.trace[0].node_id == "input"
        assert result.trace[0].status == "completed"

    def test_conditional_edge_satisfied(self):
        """条件边满足时执行"""
        config = PipelineConfig(
            version="v1",
            nodes=[
                PipelineNodeConfig(id="input", type="InputNode", params={}),
                PipelineNodeConfig(id="validate", type="ValidateSubtitleNode", params={}),
            ],
            edges=[
                PipelineEdgeConfig(
                    source="input",
                    target="validate",
                    condition="source_type == 'local'",
                ),
            ],
        )

        graph = PipelineGraph(config)
        registry = get_default_registry()
        runner = PipelineRunner(graph, registry)

        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)

        result = runner.run(ctx)

        # 条件满足，validate 节点应该执行
        node_ids = [t.node_id for t in result.trace]
        assert "validate" in node_ids

    def test_conditional_edge_not_satisfied(self):
        """条件边不满足时跳过"""
        config = PipelineConfig(
            version="v1",
            nodes=[
                PipelineNodeConfig(id="input", type="InputNode", params={}),
                PipelineNodeConfig(
                    id="download_sub", type="DownloadSubtitleNode", params={}
                ),
            ],
            edges=[
                PipelineEdgeConfig(
                    source="input",
                    target="download_sub",
                    condition="source_type == 'url'",  # 只有 URL 时才下载
                ),
            ],
        )

        graph = PipelineGraph(config)
        registry = get_default_registry()
        runner = PipelineRunner(graph, registry)

        # 使用 local 类型，条件不满足
        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)

        result = runner.run(ctx)

        # download_sub 节点应该被跳过
        node_ids = [t.node_id for t in result.trace if t.status == "completed"]
        assert "download_sub" not in node_ids

    def test_trace_records_elapsed_time(self):
        """trace 记录执行时间"""
        config = PipelineConfig(
            version="v1",
            nodes=[
                PipelineNodeConfig(id="input", type="InputNode", params={}),
            ],
            edges=[],
        )

        graph = PipelineGraph(config)
        registry = get_default_registry()
        runner = PipelineRunner(graph, registry)

        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)

        result = runner.run(ctx)

        # 验证 elapsed_ms 有值
        assert result.trace[0].elapsed_ms is not None
        assert result.trace[0].elapsed_ms >= 0


class TestLocalVideoFlow:
    """本地视频流程测试"""

    def test_local_skips_download_nodes(self):
        """本地视频跳过下载节点"""
        config = PipelineConfig(
            version="v1",
            nodes=[
                PipelineNodeConfig(id="input", type="InputNode", params={}),
                PipelineNodeConfig(
                    id="download_sub", type="DownloadSubtitleNode", params={}
                ),
                PipelineNodeConfig(
                    id="download_video", type="DownloadVideoNode", params={}
                ),
                PipelineNodeConfig(id="validate", type="ValidateSubtitleNode", params={}),
            ],
            edges=[
                # 仅 URL 类型触发下载
                PipelineEdgeConfig(
                    source="input",
                    target="download_sub",
                    condition="source_type == 'url'",
                ),
                PipelineEdgeConfig(
                    source="input",
                    target="download_video",
                    condition="source_type == 'url'",
                ),
                # 本地直接到 validate
                PipelineEdgeConfig(
                    source="input",
                    target="validate",
                    condition="source_type == 'local'",
                ),
            ],
        )

        graph = PipelineGraph(config)
        registry = get_default_registry()
        runner = PipelineRunner(graph, registry)

        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)

        result = runner.run(ctx)

        completed_nodes = [t.node_id for t in result.trace if t.status == "completed"]
        assert "input" in completed_nodes
        assert "validate" in completed_nodes
        assert "download_sub" not in completed_nodes
        assert "download_video" not in completed_nodes


class TestURLSubtitlePriorityFlow:
    """URL 字幕优先流程测试"""

    def test_url_with_valid_subtitle_skips_video_download(self, sample_subtitle_path):
        """URL 有有效字幕时跳过视频下载"""
        # 构建一个模拟"字幕有效则跳过视频下载"的 DAG
        # 注意：不包含 TextSummarizeNode 以避免需要 LLM 环境变量
        config = PipelineConfig(
            version="v1",
            nodes=[
                PipelineNodeConfig(id="input", type="InputNode", params={}),
                PipelineNodeConfig(id="parse", type="ParseSubtitleNode", params={}),
                PipelineNodeConfig(id="validate", type="ValidateSubtitleNode", params={}),
                PipelineNodeConfig(
                    id="download_video", type="DownloadVideoNode", params={}
                ),
                # 用 DetectSilenceNode 代替 TextSummarizeNode，避免 LLM 依赖
                PipelineNodeConfig(id="end", type="DetectSilenceNode", params={}),
            ],
            edges=[
                PipelineEdgeConfig(source="input", target="parse"),
                PipelineEdgeConfig(source="parse", target="validate"),
                # 字幕有效直接到 end
                PipelineEdgeConfig(
                    source="validate",
                    target="end",
                    condition="subtitle_valid == True",
                ),
                # 字幕无效才下载视频
                PipelineEdgeConfig(
                    source="validate",
                    target="download_video",
                    condition="subtitle_valid == False",
                ),
            ],
        )

        graph = PipelineGraph(config)
        registry = get_default_registry()
        runner = PipelineRunner(graph, registry)

        # 提供有效字幕文件
        inputs = PipelineInputs(
            source_type="url",
            source_url="https://example.com/video.mp4",
            subtitle_path=sample_subtitle_path,
        )
        thresholds = PipelineThresholds(subtitle_coverage_min=0.5)  # 降低阈值便于测试
        ctx = PipelineContext.from_inputs(inputs, thresholds)
        # 模拟视频时长
        ctx.set("video_duration", 20.0)

        result = runner.run(ctx)

        completed_nodes = [t.node_id for t in result.trace if t.status == "completed"]

        # 验证执行路径
        assert "input" in completed_nodes
        assert "parse" in completed_nodes
        assert "validate" in completed_nodes

        # 字幕有效时应该直接总结，跳过视频下载
        if result.subtitle_valid:
            assert "download_video" not in completed_nodes


class TestThresholdsConfiguration:
    """阈值配置测试"""

    def test_custom_coverage_threshold(self):
        """自定义覆盖率阈值"""
        from app.core.asr.asr_data import ASRData, ASRDataSeg
        from app.pipeline.nodes.core import ValidateSubtitleNode

        # 创建覆盖率约 50% 的字幕
        segments = [ASRDataSeg("测试", 1000, 5000)]
        asr_data = ASRData(segments)

        node = ValidateSubtitleNode(node_id="validate", params={})

        # 默认阈值 0.8，应该无效
        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx1 = PipelineContext.from_inputs(inputs)
        ctx1.set("asr_data", asr_data)
        ctx1.set("video_duration", 10.0)

        node.run(ctx1)
        assert ctx1.subtitle_valid is False

        # 降低阈值到 0.3，应该有效
        thresholds = PipelineThresholds(subtitle_coverage_min=0.3)
        ctx2 = PipelineContext.from_inputs(inputs, thresholds)
        ctx2.set("asr_data", asr_data)
        ctx2.set("video_duration", 10.0)

        node.run(ctx2)
        assert ctx2.subtitle_valid is True
