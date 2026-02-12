"""
应用配置模块，基于 pydantic-settings 实现。

各配置类通过环境变量注入参数值，每个类拥有独立的环境变量前缀，
使用 lru_cache 保证配置对象在进程生命周期内只实例化一次。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UploadSettings(BaseSettings):
    """上传相关配置，环境变量前缀为 UPLOAD_。"""

    model_config = SettingsConfigDict(env_prefix="UPLOAD_", extra="ignore")

    # 并发上传数，至少为 1
    concurrency: int = Field(default=2, ge=1)
    # 分片大小（字节），默认 8 MiB，最小 1 MiB
    chunk_size: int = Field(default=8 * 1024 * 1024, ge=1024 * 1024)
    # 读取超时（秒）
    read_timeout_seconds: float = Field(default=30.0, gt=0)
    # 写入超时（秒）
    write_timeout_seconds: float = Field(default=30.0, gt=0)
    # Content-Length 允许的额外冗余字节数，默认 10 MiB；
    # 用于容忍客户端声明长度与实际数据之间的偏差
    content_length_grace_bytes: int = Field(default=10 * 1024 * 1024, ge=0)


class RateLimitSettings(BaseSettings):
    """接口限流配置，环境变量前缀为 RATE_LIMIT_。"""

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_", extra="ignore")

    # 上传接口每分钟最大请求数；
    # 同时兼容旧环境变量名 UPLOAD_RATE_LIMIT_PER_MINUTE
    upload_per_minute: int = Field(
        default=30,
        ge=1,
        validation_alias=AliasChoices(
            "RATE_LIMIT_UPLOAD_PER_MINUTE",
            "UPLOAD_RATE_LIMIT_PER_MINUTE",
        ),
    )
    # 摘要接口每分钟最大请求数；
    # 同时兼容旧环境变量名 SUMMARY_RATE_LIMIT_PER_MINUTE
    summary_per_minute: int = Field(
        default=60,
        ge=1,
        validation_alias=AliasChoices(
            "RATE_LIMIT_SUMMARY_PER_MINUTE",
            "SUMMARY_RATE_LIMIT_PER_MINUTE",
        ),
    )


class WorkerSettings(BaseSettings):
    """后台任务 Worker 配置，环境变量前缀为 JOB_。"""

    model_config = SettingsConfigDict(env_prefix="JOB_", extra="ignore")

    # Worker 数量，0 表示禁用后台任务处理
    worker_count: int = Field(default=1, ge=0)


# --- 单例工厂函数 ---
# 使用 lru_cache 确保每个配置类全局仅创建一个实例，
# 避免重复读取环境变量，同时保证依赖注入时引用一致。


@lru_cache
def get_upload_settings() -> UploadSettings:
    return UploadSettings()


@lru_cache
def get_rate_limit_settings() -> RateLimitSettings:
    return RateLimitSettings()


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()


__all__ = [
    "RateLimitSettings",
    "UploadSettings",
    "WorkerSettings",
    "get_rate_limit_settings",
    "get_upload_settings",
    "get_worker_settings",
]
