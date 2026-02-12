"""API 数据模型定义模块。

定义所有 API 端点的请求体、响应体、路径参数及枚举类型。
基于 Pydantic v2 实现序列化、反序列化与自动校验。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any

from fastapi import Path
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StringConstraints, model_validator


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def datetime_to_gmt_str(value: datetime) -> str:
    """将 datetime 转换为 HTTP 标准 GMT 时间字符串（RFC 7231 格式）。

    若传入的 datetime 不含时区信息，默认视为 UTC。
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


# ---------------------------------------------------------------------------
# 基础模型
# ---------------------------------------------------------------------------


class ApiModel(BaseModel):
    """所有 API 模型的基类，统一配置序列化行为。

    - extra="forbid": 禁止请求体包含未声明的字段，防止拼写错误被静默忽略
    - populate_by_name: 允许同时通过字段名和别名赋值
    - str_strip_whitespace: 自动去除字符串首尾空白
    - json_encoders: datetime 统一序列化为 GMT 字符串
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
        json_encoders={datetime: datetime_to_gmt_str},
    )


# ---------------------------------------------------------------------------
# 枚举类型
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    """视频来源类型。"""

    URL = "url"      # 通过 URL 引用远程资源
    LOCAL = "local"  # 通过本地上传的文件引用


class CacheStatus(str, Enum):
    """缓存条目的生命周期状态。"""

    COMPLETED = "completed"    # 摘要生成完成，可直接返回结果
    RUNNING = "running"        # 后台任务正在处理中
    PENDING = "pending"        # 已入队，等待调度执行
    FAILED = "failed"          # 处理失败
    NOT_FOUND = "not_found"    # 缓存中不存在该条目


class SummaryStatus(str, Enum):
    """摘要请求的处理状态（不含 not_found，因为请求必定会创建条目）。"""

    COMPLETED = "completed"
    RUNNING = "running"
    PENDING = "pending"
    FAILED = "failed"


class JobStatus(str, Enum):
    """后台异步任务的执行状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FileType(str, Enum):
    """上传文件的媒体类型分类。"""

    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"


# ---------------------------------------------------------------------------
# 带格式约束的类型别名
# ---------------------------------------------------------------------------

# 文件 ID：前缀 "f_" + 32 位十六进制，总长 34 字符
FileId = Annotated[
    str,
    StringConstraints(pattern=r"^f_[0-9a-f]{32}$", min_length=34, max_length=34),
]

# 文件内容 SHA-256 哈希值，64 位十六进制
FileHash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]

# 缓存键，同为 SHA-256 格式（由来源信息 + 处理策略版本计算得出）
CacheKey = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]

# 任务 ID：前缀 "j_" + 32 位十六进制，总长 34 字符
JobId = Annotated[
    str,
    StringConstraints(pattern=r"^j_[0-9a-f]{32}$", min_length=34, max_length=34),
]

# 路径参数类型，附加 OpenAPI 描述信息
JobIdPathParam = Annotated[JobId, Path(description="任务 ID")]
CacheKeyPathParam = Annotated[CacheKey, Path(description="缓存键")]


# ---------------------------------------------------------------------------
# 通用响应
# ---------------------------------------------------------------------------


class ErrorResponse(ApiModel):
    """统一错误响应格式，所有非 2xx 响应均使用此结构。"""

    message: str = Field(..., description="错误消息")
    code: str = Field(..., description="错误码")
    status: int = Field(..., ge=100, le=599, description="HTTP 状态码")
    request_id: str = Field(..., description="请求 ID")
    detail: Any | None = Field(default=None, description="错误详情")
    errors: Any | None = Field(default=None, description="字段级错误")


# ---------------------------------------------------------------------------
# 文件上传
# ---------------------------------------------------------------------------


class UploadResponse(ApiModel):
    """文件上传成功后的响应，返回服务端分配的文件标识及元信息。"""

    file_id: FileId = Field(..., description="文件唯一标识，用于后续流程引用")
    original_name: str = Field(..., min_length=1, max_length=512, description="原始文件名")
    size: int = Field(..., ge=1, description="文件大小（字节）")
    mime_type: str = Field(..., min_length=1, max_length=255, description="MIME 类型")
    file_type: FileType = Field(..., description="文件类型")
    file_hash: FileHash | None = Field(default=None, description="文件内容 SHA256")


# ---------------------------------------------------------------------------
# 来源请求（基类）
# ---------------------------------------------------------------------------


class SourceRequest(ApiModel):
    """视频来源请求基类，根据 source_type 选择不同的引用方式。

    - source_type=url  时：必须提供 source_url，不可提供 file_id / file_hash
    - source_type=local 时：必须且只能提供 file_id 或 file_hash 中的一个
    """

    source_type: SourceType = Field(..., description="来源类型: url | local")
    source_url: AnyHttpUrl | None = Field(default=None, description="URL (source_type=url 时)")
    file_id: FileId | None = Field(default=None, description="上传文件 ID (source_type=local 时)")
    file_hash: FileHash | None = Field(default=None, description="文件 hash (source_type=local 时)")

    @model_validator(mode="after")
    def validate_source_fields(self) -> "SourceRequest":
        """根据 source_type 校验字段互斥关系，确保请求语义一致。"""
        if self.source_type == SourceType.URL:
            if self.source_url is None:
                raise ValueError("source_type 为 url 时必须提供 source_url")
            if self.file_id is not None or self.file_hash is not None:
                raise ValueError("source_type 为 url 时不能提供 file_id 或 file_hash")
            return self

        # source_type == LOCAL
        if self.source_url is not None:
            raise ValueError("source_type 为 local 时不能提供 source_url")
        # file_id 和 file_hash 必须二选一：两者同时为 None 或同时非 None 都不合法
        if (self.file_id is None) == (self.file_hash is None):
            raise ValueError("source_type 为 local 时必须且只能提供 file_id 或 file_hash")
        return self


# ---------------------------------------------------------------------------
# 缓存查询
# ---------------------------------------------------------------------------


class CacheLookupRequest(SourceRequest):
    """缓存查询请求，复用 SourceRequest 的字段和校验逻辑。"""

    pass


class CacheLookupResponse(ApiModel):
    """缓存查询响应。

    hit=True 且 status=completed 时，summary_text 中包含已生成的摘要；
    hit=True 且 status=running/pending 时，返回关联的 job_id 供轮询。
    """

    hit: bool = Field(..., description="是否命中缓存")
    status: CacheStatus = Field(..., description="状态: completed | running | pending | failed | not_found")
    cache_key: CacheKey | None = Field(default=None, description="缓存键")
    source_name: str | None = Field(default=None, description="来源名称")
    summary_text: str | None = Field(default=None, description="摘要文本")
    bundle_path: str | None = Field(default=None, description="Bundle 目录路径")
    job_id: JobId | None = Field(default=None, description="任务 ID (status=running/pending 时)")
    error: str | None = Field(default=None, description="错误信息")
    created_at: float | None = Field(default=None, ge=0, description="创建时间")
    updated_at: float | None = Field(default=None, ge=0, description="更新时间")


# ---------------------------------------------------------------------------
# 摘要生成
# ---------------------------------------------------------------------------


class SummaryRequest(SourceRequest):
    """摘要生成请求。设置 refresh=True 可忽略已有缓存，强制重新生成。"""

    refresh: bool = Field(default=False, description="强制重新生成")


class SummaryResponse(ApiModel):
    """摘要生成响应。

    同步返回当前处理状态；若已完成则直接携带 summary_text。
    """

    status: SummaryStatus = Field(..., description="状态: completed | running | pending | failed")
    cache_key: CacheKey = Field(..., description="缓存键")
    job_id: JobId | None = Field(default=None, description="任务 ID")
    summary_text: str | None = Field(default=None, description="摘要文本 (status=completed 时)")
    source_name: str | None = Field(default=None, description="来源名称")
    error: str | None = Field(default=None, description="错误信息")
    created_at: float | None = Field(default=None, ge=0, description="创建时间")


# ---------------------------------------------------------------------------
# 任务状态查询
# ---------------------------------------------------------------------------


class JobStatusResponse(ApiModel):
    """后台任务状态响应，支持前端轮询任务进度。

    同时携带关联的缓存状态和摘要文本，避免客户端额外请求。
    """

    job_id: JobId = Field(..., description="任务 ID")
    cache_key: CacheKey = Field(..., description="关联的缓存键")
    status: JobStatus = Field(..., description="状态: pending | running | completed | failed")
    created_at: float = Field(..., ge=0, description="创建时间")
    updated_at: float = Field(..., ge=0, description="更新时间")
    error: str | None = Field(default=None, description="错误信息")
    cache_status: CacheStatus | None = Field(default=None, description="缓存状态")
    summary_text: str | None = Field(default=None, description="摘要文本")
    source_name: str | None = Field(default=None, description="来源名称")


# ---------------------------------------------------------------------------
# 缓存管理
# ---------------------------------------------------------------------------


class CacheEntryResponse(ApiModel):
    """缓存条目详情，用于管理端查看单条缓存的完整信息。"""

    cache_key: CacheKey = Field(..., description="缓存键")
    source_type: SourceType = Field(..., description="来源类型")
    source_ref: str = Field(..., min_length=1, max_length=2048, description="来源引用 (规范化 URL 或文件 hash)")
    source_name: str | None = Field(default=None, description="来源名称")
    status: CacheStatus = Field(..., description="状态")
    profile_version: str = Field(..., min_length=1, max_length=128, description="处理策略版本")
    summary_text: str | None = Field(default=None, description="摘要文本")
    bundle_path: str | None = Field(default=None, description="Bundle 目录路径")
    error: str | None = Field(default=None, description="错误信息")
    created_at: float = Field(..., ge=0, description="创建时间")
    updated_at: float = Field(..., ge=0, description="更新时间")
    last_accessed: float | None = Field(default=None, ge=0, description="最后访问时间")


class CacheDeleteResponse(ApiModel):
    """缓存删除响应。"""

    cache_key: CacheKey = Field(..., description="缓存键")
    deleted: bool = Field(..., description="是否已删除")
