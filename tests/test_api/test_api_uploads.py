"""API 上传端点集成测试"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.uploads import FileStorage, get_file_storage


@pytest.fixture
def client(monkeypatch):
    """测试客户端"""
    monkeypatch.setenv("PIPELINE_WORKER_COUNT", "0")
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
    """POST /uploads 测试"""

    def test_upload_video_file(self, client, temp_storage):
        """测试上传视频文件"""
        with patch("app.api.main.get_file_storage", return_value=temp_storage):
            # 创建测试文件
            file_content = b"fake video content"
            files = {"file": ("test_video.mp4", io.BytesIO(file_content), "video/mp4")}

            response = client.post("/uploads", files=files)

            assert response.status_code == 200
            data = response.json()
            assert data["file_id"].startswith("f_")
            assert data["original_name"] == "test_video.mp4"
            assert data["size"] == len(file_content)
            assert data["file_type"] == "video"
            assert data["mime_type"] == "video/mp4"

    def test_upload_audio_file(self, client, temp_storage):
        """测试上传音频文件"""
        with patch("app.api.main.get_file_storage", return_value=temp_storage):
            file_content = b"fake audio content"
            files = {"file": ("test_audio.mp3", io.BytesIO(file_content), "audio/mpeg")}

            response = client.post("/uploads", files=files)

            assert response.status_code == 200
            data = response.json()
            assert data["file_type"] == "audio"

    def test_upload_subtitle_file(self, client, temp_storage):
        """测试上传字幕文件"""
        with patch("app.api.main.get_file_storage", return_value=temp_storage):
            file_content = b"1\n00:00:01,000 --> 00:00:05,000\nHello World\n"
            files = {"file": ("test_subtitle.srt", io.BytesIO(file_content), "text/plain")}

            response = client.post("/uploads", files=files)

            assert response.status_code == 200
            data = response.json()
            assert data["file_type"] == "subtitle"

    def test_upload_unsupported_type(self, client, temp_storage):
        """测试上传不支持的文件类型"""
        with patch("app.api.main.get_file_storage", return_value=temp_storage):
            file_content = b"executable content"
            files = {"file": ("test.exe", io.BytesIO(file_content), "application/x-executable")}

            response = client.post("/uploads", files=files)

            assert response.status_code == 415
            assert "不支持的文件类型" in response.json()["detail"]


class TestLocalPipelineWithFileId:
    """POST /pipeline/auto/local 与 file_id 集成测试"""

    def test_local_pipeline_with_subtitle_file_id(self, client, temp_storage):
        """测试使用 file_id 的本地流程"""
        with patch("app.api.main.get_file_storage", return_value=temp_storage):
            # 先上传字幕文件
            subtitle_content = b"1\n00:00:01,000 --> 00:00:05,000\nHello World\n"
            files = {"file": ("test.srt", io.BytesIO(subtitle_content), "text/plain")}

            upload_response = client.post("/uploads", files=files)
            assert upload_response.status_code == 200
            file_id = upload_response.json()["file_id"]

            # 使用 file_id 调用流程（仅测试参数传递，不执行完整流程）
            request_data = {
                "inputs": {
                    "subtitle_file_id": file_id,
                },
                "options": {},
            }

            # 注意：完整流程需要 LLM，这里只验证 file_id 解析正确
            # 实际测试需要 mock 更多组件
            response = client.post("/pipeline/auto/local", json=request_data)

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "queued"
            assert data["run_id"].startswith("r_")

    def test_local_pipeline_with_nonexistent_file_id(self, client, temp_storage):
        """测试使用不存在的 file_id"""
        with patch("app.api.main.get_file_storage", return_value=temp_storage):
            request_data = {
                "inputs": {
                    "video_file_id": "nonexistent_file_id",
                },
                "options": {},
            }

            response = client.post("/pipeline/auto/local", json=request_data)

            assert response.status_code == 404
            assert "文件不存在" in response.json()["detail"]

    def test_local_pipeline_with_wrong_file_type(self, client, temp_storage):
        """测试 file_id 类型不匹配"""
        with patch("app.api.main.get_file_storage", return_value=temp_storage):
            # 上传音频文件
            audio_content = b"fake audio content"
            files = {"file": ("test.mp3", io.BytesIO(audio_content), "audio/mpeg")}

            upload_response = client.post("/uploads", files=files)
            audio_file_id = upload_response.json()["file_id"]

            # 尝试将音频文件当作视频文件使用
            request_data = {
                "inputs": {
                    "video_file_id": audio_file_id,
                },
                "options": {},
            }

            response = client.post("/pipeline/auto/local", json=request_data)

            assert response.status_code == 400
            assert "不是视频文件" in response.json()["detail"]

    def test_local_pipeline_file_id_priority(self, client, temp_storage):
        """测试 file_id 优先于 path"""
        with patch("app.api.main.get_file_storage", return_value=temp_storage):
            # 上传字幕文件
            subtitle_content = b"1\n00:00:01,000 --> 00:00:05,000\nHello World\n"
            files = {"file": ("uploaded.srt", io.BytesIO(subtitle_content), "text/plain")}

            upload_response = client.post("/uploads", files=files)
            file_id = upload_response.json()["file_id"]

            # 同时提供 file_id 和 path，应该使用 file_id
            request_data = {
                "inputs": {
                    "subtitle_file_id": file_id,
                    "subtitle_path": "/nonexistent/path.srt",  # 不存在的路径
                },
                "options": {},
            }

            response = client.post("/pipeline/auto/local", json=request_data)

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "queued"
            assert data["run_id"].startswith("r_")
