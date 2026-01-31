"""文件上传模块测试"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.api.uploads import (
    FileStorage,
    FileSizeError,
    FileTypeError,
    FileNotFoundError,
    UploadedFile,
    get_file_storage,
)


@pytest.fixture
def temp_upload_dir():
    """临时上传目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db_path(temp_upload_dir):
    """临时 SQLite 数据库路径"""
    return temp_upload_dir / "uploads.db"


@pytest.fixture
def storage(temp_upload_dir, temp_db_path):
    """测试用 FileStorage 实例"""
    # 创建新实例，绕过单例
    s = object.__new__(FileStorage)
    s._initialized = False
    s.__init__(
        upload_dir=temp_upload_dir,
        max_file_size_mb=10,  # 10MB
        ttl_seconds=3600,
        db_path=temp_db_path,
    )
    # 确保每个测试前清空文件映射
    s._files.clear()
    yield s
    # 测试后清理
    s._files.clear()


class TestFileStorage:
    """FileStorage 单元测试"""

    def test_save_video_file(self, storage):
        """测试视频文件上传"""
        content = b"fake video content"
        result = storage.save(
            content=content,
            original_name="test_video.mp4",
            content_type="video/mp4",
        )

        assert result.file_id.startswith("f_")
        assert result.original_name == "test_video.mp4"
        assert result.size == len(content)
        assert result.file_type == "video"
        assert result.stored_path.exists()

    def test_save_audio_file(self, storage):
        """测试音频文件上传"""
        content = b"fake audio content"
        result = storage.save(
            content=content,
            original_name="test_audio.mp3",
            content_type="audio/mpeg",
        )

        assert result.file_type == "audio"
        assert result.stored_path.exists()

    def test_save_subtitle_file(self, storage):
        """测试字幕文件上传"""
        content = b"1\n00:00:01,000 --> 00:00:05,000\nHello World\n"
        result = storage.save(
            content=content,
            original_name="test_subtitle.srt",
            content_type="text/plain",
        )

        assert result.file_type == "subtitle"
        assert result.stored_path.exists()

    def test_reject_unsupported_file_type(self, storage):
        """测试拒绝不支持的文件类型"""
        with pytest.raises(FileTypeError) as exc_info:
            storage.save(
                content=b"some content",
                original_name="test.exe",
                content_type="application/x-executable",
            )

        assert "不支持的文件类型" in str(exc_info.value)

    def test_reject_oversized_file(self, storage):
        """测试拒绝超大文件"""
        # 创建一个超过 10MB 的内容
        large_content = b"x" * (11 * 1024 * 1024)

        with pytest.raises(FileSizeError) as exc_info:
            storage.save(
                content=large_content,
                original_name="large_video.mp4",
                content_type="video/mp4",
            )

        assert "超过限制" in str(exc_info.value)

    def test_get_existing_file(self, storage):
        """测试获取已上传文件"""
        content = b"test content"
        uploaded = storage.save(
            content=content,
            original_name="test.mp4",
            content_type="video/mp4",
        )

        result = storage.get(uploaded.file_id)
        assert result.file_id == uploaded.file_id
        assert result.stored_path.exists()

    def test_get_nonexistent_file(self, storage):
        """测试获取不存在的文件"""
        with pytest.raises(FileNotFoundError) as exc_info:
            storage.get("nonexistent_file_id")

        assert "文件不存在" in str(exc_info.value)

    def test_get_expired_file(self, storage):
        """测试获取过期文件"""
        content = b"test content"
        uploaded = storage.save(
            content=content,
            original_name="test.mp4",
            content_type="video/mp4",
        )

        # 模拟文件过期
        storage._files[uploaded.file_id].ttl_seconds = -1

        with pytest.raises(FileNotFoundError) as exc_info:
            storage.get(uploaded.file_id)

        assert "文件已过期" in str(exc_info.value)

    def test_delete_file(self, storage):
        """测试删除文件"""
        content = b"test content"
        uploaded = storage.save(
            content=content,
            original_name="test.mp4",
            content_type="video/mp4",
        )

        # 确认文件存在
        assert uploaded.stored_path.exists()

        # 删除文件
        result = storage.delete(uploaded.file_id)
        assert result is True

        # 确认文件已删除
        assert not uploaded.stored_path.exists()

        # 再次获取应该失败
        with pytest.raises(FileNotFoundError):
            storage.get(uploaded.file_id)

    def test_resolve_file_ids(self, storage):
        """测试批量解析 file_id"""
        video_content = b"video content"
        audio_content = b"audio content"

        video_uploaded = storage.save(
            content=video_content,
            original_name="test.mp4",
            content_type="video/mp4",
        )
        audio_uploaded = storage.save(
            content=audio_content,
            original_name="test.mp3",
            content_type="audio/mpeg",
        )

        resolved = storage.resolve_file_ids(
            video_file_id=video_uploaded.file_id,
            audio_file_id=audio_uploaded.file_id,
            subtitle_file_id=None,
        )

        assert resolved["video_path"] == str(video_uploaded.stored_path)
        assert resolved["audio_path"] == str(audio_uploaded.stored_path)
        assert resolved["subtitle_path"] is None

    def test_resolve_file_ids_wrong_type(self, storage):
        """测试解析时类型校验"""
        audio_content = b"audio content"
        audio_uploaded = storage.save(
            content=audio_content,
            original_name="test.mp3",
            content_type="audio/mpeg",
        )

        # 尝试将音频文件当作视频文件使用
        with pytest.raises(FileTypeError) as exc_info:
            storage.resolve_file_ids(video_file_id=audio_uploaded.file_id)

        assert "不是视频文件" in str(exc_info.value)

    def test_sanitize_filename(self, storage):
        """测试文件名清理"""
        # 测试路径穿越攻击
        result = storage._sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

        # 测试特殊字符
        result = storage._sanitize_filename('file<>:"|?*.mp4')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

        # 测试长文件名截断
        long_name = "a" * 300 + ".mp4"
        result = storage._sanitize_filename(long_name)
        assert len(result) <= 205  # 200 + 扩展名

    def test_cleanup_expired(self, storage):
        """测试过期文件清理"""
        # 使用不同内容确保生成不同的 file_id
        content1 = b"test content for file 1"
        content2 = b"test content for file 2"

        # 上传两个文件
        file1 = storage.save(content1, "test1.mp4", "video/mp4")
        file2 = storage.save(content2, "test2.mp4", "video/mp4")

        # 使 file1 过期
        storage._files[file1.file_id].ttl_seconds = -1

        # 执行清理
        cleaned = storage.cleanup_expired()

        assert cleaned == 1
        assert file1.file_id not in storage._files
        assert file2.file_id in storage._files

    def test_list_files(self, storage):
        """测试列出文件"""
        # 使用不同内容
        video_content = b"video test content"
        audio_content = b"audio test content"

        storage.save(video_content, "test1.mp4", "video/mp4")
        storage.save(audio_content, "test2.mp3", "audio/mpeg")

        files = storage.list_files()
        assert len(files) == 2

        file_types = {f["file_type"] for f in files}
        assert file_types == {"video", "audio"}


class TestUploadedFile:
    """UploadedFile 单元测试"""

    def test_is_expired_false(self):
        """测试未过期"""
        import time

        uploaded = UploadedFile(
            file_id="test",
            original_name="test.mp4",
            size=100,
            mime_type="video/mp4",
            file_type="video",
            stored_path=Path("/tmp/test.mp4"),
            created_at=time.time(),
            ttl_seconds=3600,
        )

        assert uploaded.is_expired() is False

    def test_is_expired_true(self):
        """测试已过期"""
        import time

        uploaded = UploadedFile(
            file_id="test",
            original_name="test.mp4",
            size=100,
            mime_type="video/mp4",
            file_type="video",
            stored_path=Path("/tmp/test.mp4"),
            created_at=time.time() - 7200,  # 2小时前
            ttl_seconds=3600,  # 1小时TTL
        )

        assert uploaded.is_expired() is True

    def test_to_dict(self):
        """测试转换为字典"""
        uploaded = UploadedFile(
            file_id="test_id",
            original_name="test.mp4",
            size=100,
            mime_type="video/mp4",
            file_type="video",
            stored_path=Path("/tmp/test.mp4"),
        )

        # 不包含 stored_path
        result = uploaded.to_dict(include_stored_path=False)
        assert "stored_path" not in result
        assert result["file_id"] == "test_id"

        # 包含 stored_path
        result = uploaded.to_dict(include_stored_path=True)
        assert result["stored_path"] == "/tmp/test.mp4"
