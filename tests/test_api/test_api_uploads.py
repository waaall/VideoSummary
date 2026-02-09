"""API 上传端点集成测试"""
from __future__ import annotations

import io
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.uploads import FileStorage, get_file_storage


@pytest.fixture
def client(monkeypatch):
    """测试客户端"""
    monkeypatch.setenv("JOB_WORKER_COUNT", "0")
    return TestClient(app)


@pytest.fixture
def temp_storage():
    """临时存储实例"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = object.__new__(FileStorage)
        storage._initialized = False
        storage.__init__(
            upload_dir=Path(tmpdir),
            max_file_size_mb=10,
            ttl_seconds=3600,
            db_path=Path(tmpdir) / "uploads.db",
        )
        storage._files.clear()
        yield storage
        storage._files.clear()


class TestUploadEndpoint:
    """POST /api/uploads 测试"""

    def test_upload_video_file(self, client, temp_storage):
        """测试上传视频文件"""
        with (
            patch("app.api.main.get_file_storage", return_value=temp_storage),
            patch("app.api.main.get_store", return_value=temp_storage.store),
        ):
            # 创建测试文件
            file_content = b"fake video content"
            files = {"file": ("test_video.mp4", io.BytesIO(file_content), "video/mp4")}

            response = client.post("/api/uploads", files=files)

            assert response.status_code == 200
            data = response.json()
            assert data["file_id"].startswith("f_")
            assert data["original_name"] == "test_video.mp4"
            assert data["size"] == len(file_content)
            assert data["file_type"] == "video"
            assert data["mime_type"] == "video/mp4"
            assert data["file_hash"]

    def test_upload_audio_file(self, client, temp_storage):
        """测试上传音频文件"""
        with (
            patch("app.api.main.get_file_storage", return_value=temp_storage),
            patch("app.api.main.get_store", return_value=temp_storage.store),
        ):
            file_content = b"fake audio content"
            files = {"file": ("test_audio.mp3", io.BytesIO(file_content), "audio/mpeg")}

            response = client.post("/api/uploads", files=files)

            assert response.status_code == 200
            data = response.json()
            assert data["file_type"] == "audio"
            assert data["file_hash"]

    def test_upload_subtitle_file(self, client, temp_storage):
        """测试上传字幕文件"""
        with (
            patch("app.api.main.get_file_storage", return_value=temp_storage),
            patch("app.api.main.get_store", return_value=temp_storage.store),
        ):
            file_content = b"1\n00:00:01,000 --> 00:00:05,000\nHello World\n"
            files = {"file": ("test_subtitle.srt", io.BytesIO(file_content), "text/plain")}

            response = client.post("/api/uploads", files=files)

            assert response.status_code == 200
            data = response.json()
            assert data["file_type"] == "subtitle"
            assert data["file_hash"]

    def test_upload_unsupported_type(self, client, temp_storage):
        """测试上传不支持的文件类型"""
        with patch("app.api.main.get_file_storage", return_value=temp_storage):
            file_content = b"executable content"
            files = {"file": ("test.exe", io.BytesIO(file_content), "application/x-executable")}

            response = client.post("/api/uploads", files=files)

            assert response.status_code == 415
            assert "不支持的文件类型" in response.json()["message"]


class TestLocalSummaryWithFileId:
    """POST /api/summaries 与 file_id 集成测试"""

    def test_local_summary_with_subtitle_file_id(self, client, temp_storage):
        """测试使用 file_id 的本地摘要"""
        with (
            patch("app.api.main.get_file_storage", return_value=temp_storage),
            patch("app.api.main.get_store", return_value=temp_storage.store),
        ):
            # 先上传字幕文件
            subtitle_content = b"1\n00:00:01,000 --> 00:00:05,000\nHello World\n"
            files = {"file": ("test.srt", io.BytesIO(subtitle_content), "text/plain")}

            upload_response = client.post("/api/uploads", files=files)
            assert upload_response.status_code == 200
            upload_data = upload_response.json()
            file_id = upload_data["file_id"]

            # 使用 file_id 调用摘要接口（仅测试入队与参数解析）
            request_data = {
                "source_type": "local",
                "file_id": file_id,
            }

            response = client.post("/api/summaries", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pending"
            assert data["job_id"].startswith("j_")
            assert data["cache_key"]

    def test_local_summary_with_nonexistent_file_id(self, client, temp_storage):
        """测试使用不存在的 file_id"""
        with (
            patch("app.api.main.get_file_storage", return_value=temp_storage),
            patch("app.api.main.get_store", return_value=temp_storage.store),
        ):
            request_data = {
                "source_type": "local",
                "file_id": "nonexistent_file_id",
            }

            response = client.post("/api/summaries", json=request_data)

            assert response.status_code == 404
            assert "文件不存在" in response.json()["message"]

    def test_cache_lookup_with_file_hash(self, client, temp_storage):
        """测试 cache/lookup 使用 file_hash"""
        with (
            patch("app.api.main.get_file_storage", return_value=temp_storage),
            patch("app.api.main.get_store", return_value=temp_storage.store),
        ):
            # 上传字幕文件
            subtitle_content = (
                f"1\n00:00:01,000 --> 00:00:05,000\nLookup {uuid.uuid4().hex}\n"
            ).encode()
            files = {"file": ("uploaded.srt", io.BytesIO(subtitle_content), "text/plain")}

            upload_response = client.post("/api/uploads", files=files)
            file_hash = upload_response.json()["file_hash"]

            response = client.post(
                "/api/cache/lookup",
                json={"source_type": "local", "file_hash": file_hash},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["hit"] is False
            assert data["status"] == "not_found"
