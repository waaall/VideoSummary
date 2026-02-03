from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """文件上传响应"""

    file_id: str = Field(..., description="文件唯一标识，用于后续流程引用")
    original_name: str = Field(..., description="原始文件名")
    size: int = Field(..., description="文件大小（字节）")
    mime_type: str = Field(..., description="MIME 类型")
    file_type: str = Field(..., description="文件类型: video|audio|subtitle")
    file_hash: Optional[str] = Field(default=None, description="文件内容 SHA256")


class CacheLookupRequest(BaseModel):
    """缓存查询请求"""

    source_type: str = Field(..., description="来源类型: url | local")
    source_url: Optional[str] = Field(default=None, description="URL (source_type=url 时)")
    file_id: Optional[str] = Field(default=None, description="上传文件 ID (source_type=local 时)")
    file_hash: Optional[str] = Field(default=None, description="文件 hash (source_type=local 时)")

    class Config:
        extra = "forbid"


class CacheLookupResponse(BaseModel):
    """缓存查询响应"""

    hit: bool = Field(..., description="是否命中缓存")
    status: str = Field(
        ..., description="状态: completed | running | pending | failed | not_found"
    )
    cache_key: Optional[str] = Field(default=None, description="缓存键")
    summary_text: Optional[str] = Field(default=None, description="摘要文本")
    bundle_path: Optional[str] = Field(default=None, description="Bundle 目录路径")
    job_id: Optional[str] = Field(default=None, description="任务 ID (status=running/pending 时)")
    error: Optional[str] = Field(default=None, description="错误信息")
    created_at: Optional[float] = Field(default=None, description="创建时间")
    updated_at: Optional[float] = Field(default=None, description="更新时间")


class SummaryRequest(BaseModel):
    """摘要请求（统一执行入口）"""

    source_type: str = Field(..., description="来源类型: url | local")
    source_url: Optional[str] = Field(default=None, description="URL (source_type=url 时)")
    file_id: Optional[str] = Field(default=None, description="上传文件 ID (source_type=local 时)")
    file_hash: Optional[str] = Field(default=None, description="文件 hash (source_type=local 时)")
    refresh: bool = Field(default=False, description="强制重新生成")

    class Config:
        extra = "forbid"


class SummaryResponse(BaseModel):
    """摘要响应"""

    status: str = Field(..., description="状态: completed | running | pending | failed")
    cache_key: str = Field(..., description="缓存键")
    job_id: Optional[str] = Field(default=None, description="任务 ID")
    summary_text: Optional[str] = Field(default=None, description="摘要文本 (status=completed 时)")
    error: Optional[str] = Field(default=None, description="错误信息")
    created_at: Optional[float] = Field(default=None, description="创建时间")


class JobStatusResponse(BaseModel):
    """任务状态响应"""

    job_id: str = Field(..., description="任务 ID")
    cache_key: str = Field(..., description="关联的缓存键")
    status: str = Field(..., description="状态: pending | running | completed | failed")
    created_at: float = Field(..., description="创建时间")
    updated_at: float = Field(..., description="更新时间")
    error: Optional[str] = Field(default=None, description="错误信息")
    cache_status: Optional[str] = Field(default=None, description="缓存状态")
    summary_text: Optional[str] = Field(default=None, description="摘要文本")


class CacheEntryResponse(BaseModel):
    """缓存条目响应"""

    cache_key: str = Field(..., description="缓存键")
    source_type: str = Field(..., description="来源类型")
    source_ref: str = Field(..., description="来源引用 (规范化 URL 或文件 hash)")
    status: str = Field(..., description="状态")
    profile_version: str = Field(..., description="处理策略版本")
    summary_text: Optional[str] = Field(default=None, description="摘要文本")
    bundle_path: Optional[str] = Field(default=None, description="Bundle 目录路径")
    error: Optional[str] = Field(default=None, description="错误信息")
    created_at: float = Field(..., description="创建时间")
    updated_at: float = Field(..., description="更新时间")
    last_accessed: Optional[float] = Field(default=None, description="最后访问时间")


class CacheDeleteResponse(BaseModel):
    """缓存删除响应"""

    cache_key: str = Field(..., description="缓存键")
    deleted: bool = Field(..., description="是否已删除")
