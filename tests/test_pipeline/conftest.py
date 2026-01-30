"""Pipeline 测试共享 fixtures"""

import tempfile
from pathlib import Path

import pytest

from app.api.schemas import (
    PipelineConfig,
    PipelineEdgeConfig,
    PipelineInputs,
    PipelineNodeConfig,
    PipelineThresholds,
)
from app.pipeline.context import PipelineContext
from app.pipeline.graph import PipelineGraph
from app.pipeline.registry import get_default_registry
from app.pipeline.runner import PipelineRunner


@pytest.fixture
def registry():
    """获取默认节点注册表"""
    return get_default_registry()


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_video_path(temp_dir):
    """创建模拟视频文件路径（不创建实际文件）"""
    return str(temp_dir / "test_video.mp4")


@pytest.fixture
def sample_subtitle_path(temp_dir):
    """创建模拟字幕文件"""
    srt_content = """1
00:00:01,000 --> 00:00:05,000
这是第一句字幕

2
00:00:06,000 --> 00:00:10,000
这是第二句字幕

3
00:00:11,000 --> 00:00:15,000
这是第三句字幕
"""
    path = temp_dir / "test_subtitle.srt"
    path.write_text(srt_content, encoding="utf-8")
    return str(path)


@pytest.fixture
def default_thresholds():
    """默认阈值配置"""
    return PipelineThresholds(
        subtitle_coverage_min=0.8,
        transcript_token_per_min_min=2.0,
        audio_rms_max_for_silence=0.01,
    )


def create_pipeline_config(nodes: list, edges: list) -> PipelineConfig:
    """辅助函数：创建 PipelineConfig"""
    return PipelineConfig(
        version="v1",
        nodes=[PipelineNodeConfig(**n) for n in nodes],
        edges=[PipelineEdgeConfig(**e) for e in edges],
    )


def create_context(
    source_type: str,
    source_url: str = None,
    video_path: str = None,
    subtitle_path: str = None,
    thresholds: PipelineThresholds = None,
) -> PipelineContext:
    """辅助函数：创建 PipelineContext"""
    inputs = PipelineInputs(
        source_type=source_type,
        source_url=source_url,
        video_path=video_path,
        subtitle_path=subtitle_path,
    )
    return PipelineContext.from_inputs(inputs, thresholds)


def run_pipeline(config: PipelineConfig, ctx: PipelineContext) -> PipelineContext:
    """辅助函数：执行 pipeline"""
    graph = PipelineGraph(config)
    registry = get_default_registry()
    runner = PipelineRunner(graph, registry)
    return runner.run(ctx)
