"""Pipeline 节点测试共享 fixtures"""

import tempfile
from pathlib import Path

import pytest


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

