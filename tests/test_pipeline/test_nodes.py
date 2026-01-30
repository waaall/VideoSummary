"""Pipeline 节点单元测试"""

import pytest

from app.api.schemas import PipelineInputs, PipelineThresholds
from app.core.asr.asr_data import ASRData, ASRDataSeg
from app.pipeline.context import PipelineContext
from app.pipeline.nodes.core import (
    DetectSilenceNode,
    ExtractAudioNode,
    FetchMetadataNode,
    InputNode,
    ParseSubtitleNode,
    TextSummarizeNode,
    ValidateSubtitleNode,
)


class TestInputNode:
    """InputNode 测试"""

    def test_valid_local_input(self):
        """本地视频输入验证通过"""
        node = InputNode(node_id="input", params={})
        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)

        node.run(ctx)
        assert ctx.source_type == "local"

    def test_valid_url_input(self):
        """URL 输入验证通过"""
        node = InputNode(node_id="input", params={})
        inputs = PipelineInputs(
            source_type="url", source_url="https://example.com/video.mp4"
        )
        ctx = PipelineContext.from_inputs(inputs)

        node.run(ctx)
        assert ctx.source_type == "url"

    def test_invalid_source_type(self):
        """无效 source_type 抛出异常"""
        node = InputNode(node_id="input", params={})
        inputs = PipelineInputs(source_type="invalid", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)

        with pytest.raises(ValueError, match="无效的 source_type"):
            node.run(ctx)

    def test_url_without_source_url(self):
        """URL 类型缺少 source_url 抛出异常"""
        node = InputNode(node_id="input", params={})
        inputs = PipelineInputs(source_type="url")
        ctx = PipelineContext.from_inputs(inputs)

        with pytest.raises(ValueError, match="必须提供 source_url"):
            node.run(ctx)

    def test_local_without_video_path(self):
        """本地类型缺少 video_path 抛出异常"""
        node = InputNode(node_id="input", params={})
        inputs = PipelineInputs(source_type="local")
        ctx = PipelineContext.from_inputs(inputs)

        with pytest.raises(ValueError, match="必须提供 video_path"):
            node.run(ctx)


class TestParseSubtitleNode:
    """ParseSubtitleNode 测试"""

    def test_parse_srt_file(self, sample_subtitle_path):
        """解析 SRT 文件"""
        node = ParseSubtitleNode(node_id="parse", params={})
        inputs = PipelineInputs(
            source_type="local",
            video_path="/test.mp4",
            subtitle_path=sample_subtitle_path,
        )
        ctx = PipelineContext.from_inputs(inputs)

        node.run(ctx)

        asr_data = ctx.get("asr_data")
        assert asr_data is not None
        assert isinstance(asr_data, ASRData)
        assert len(asr_data.segments) == 3
        assert ctx.get("subtitle_segment_count") == 3

    def test_parse_nonexistent_file(self):
        """解析不存在的文件"""
        node = ParseSubtitleNode(node_id="parse", params={})
        inputs = PipelineInputs(
            source_type="local",
            video_path="/test.mp4",
            subtitle_path="/nonexistent.srt",
        )
        ctx = PipelineContext.from_inputs(inputs)

        node.run(ctx)

        assert ctx.get("asr_data") is None

    def test_parse_no_subtitle_path(self):
        """没有字幕路径"""
        node = ParseSubtitleNode(node_id="parse", params={})
        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)

        node.run(ctx)

        assert ctx.get("asr_data") is None


class TestValidateSubtitleNode:
    """ValidateSubtitleNode 测试"""

    def test_valid_subtitle(self):
        """有效字幕（覆盖率足够）"""
        node = ValidateSubtitleNode(node_id="validate", params={})

        # 模拟 15 秒视频，字幕覆盖 14 秒
        segments = [
            ASRDataSeg("第一句", 1000, 5000),
            ASRDataSeg("第二句", 6000, 10000),
            ASRDataSeg("第三句", 11000, 15000),
        ]
        asr_data = ASRData(segments)

        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)
        ctx.set("asr_data", asr_data)
        ctx.set("video_duration", 15.0)

        node.run(ctx)

        assert ctx.subtitle_valid is True
        assert ctx.subtitle_coverage_ratio >= 0.8

    def test_invalid_subtitle_low_coverage(self):
        """无效字幕（覆盖率不足）"""
        node = ValidateSubtitleNode(node_id="validate", params={})

        # 模拟 100 秒视频，字幕只覆盖 10 秒
        segments = [
            ASRDataSeg("第一句", 1000, 5000),
            ASRDataSeg("第二句", 6000, 10000),
        ]
        asr_data = ASRData(segments)

        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)
        ctx.set("asr_data", asr_data)
        ctx.set("video_duration", 100.0)

        node.run(ctx)

        assert ctx.subtitle_valid is False
        assert ctx.subtitle_coverage_ratio < 0.8

    def test_no_asr_data(self):
        """没有 ASR 数据"""
        node = ValidateSubtitleNode(node_id="validate", params={})

        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)
        ctx.set("video_duration", 100.0)

        node.run(ctx)

        assert ctx.subtitle_valid is False
        assert ctx.subtitle_coverage_ratio == 0.0


class TestDetectSilenceNode:
    """DetectSilenceNode 测试"""

    def test_not_silent(self):
        """非静音视频"""
        node = DetectSilenceNode(node_id="detect", params={})

        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)
        ctx.set("transcript_token_count", 500)  # 较多 token
        ctx.set("video_duration", 60.0)  # 1 分钟

        node.run(ctx)

        # 500 tokens / 1 min = 500 tokens/min > 2.0 阈值
        assert ctx.is_silent is False

    def test_silent_video(self):
        """静音视频"""
        node = DetectSilenceNode(node_id="detect", params={})

        inputs = PipelineInputs(source_type="local", video_path="/test.mp4")
        ctx = PipelineContext.from_inputs(inputs)
        ctx.set("transcript_token_count", 5)  # 极少 token
        ctx.set("video_duration", 300.0)  # 5 分钟

        node.run(ctx)

        # 5 tokens / 5 min = 1 token/min < 2.0 阈值
        assert ctx.is_silent is True


class TestNodeOutputKeys:
    """测试节点 get_output_keys 方法"""

    def test_input_node_output_keys(self):
        node = InputNode(node_id="test", params={})
        assert "source_type" in node.get_output_keys()

    def test_fetch_metadata_output_keys(self):
        node = FetchMetadataNode(node_id="test", params={})
        assert "video_duration" in node.get_output_keys()

    def test_parse_subtitle_output_keys(self):
        node = ParseSubtitleNode(node_id="test", params={})
        keys = node.get_output_keys()
        assert "asr_data" in keys
        assert "subtitle_segment_count" in keys

    def test_validate_subtitle_output_keys(self):
        node = ValidateSubtitleNode(node_id="test", params={})
        keys = node.get_output_keys()
        assert "subtitle_valid" in keys
        assert "subtitle_coverage_ratio" in keys

    def test_detect_silence_output_keys(self):
        node = DetectSilenceNode(node_id="test", params={})
        keys = node.get_output_keys()
        assert "is_silent" in keys
        assert "audio_rms" in keys

    def test_text_summarize_output_keys(self):
        node = TextSummarizeNode(node_id="test", params={})
        assert "summary_text" in node.get_output_keys()
