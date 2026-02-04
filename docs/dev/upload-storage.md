---
title: 上传与存储设计 - VideoSummary
description: 说明上传接口的分层设计、存储与校验策略、持久化与清理流程，以及可配置项。
head:
  - - meta
    - name: keywords
      content: 上传,FastAPI,UploadFile,分层设计,文件存储,TTL,SQLite,VideoSummary
---

# 上传与存储设计

本页说明当前上传模块的分层思路、数据流、关键约束，以及为降低复杂度做的调整。

## 分层与职责

上传流程被拆成两层：

- **HTTP 路由层**（`app/api/main.py`）
  - 解析请求、鉴权/限流、参数校验
  - 把 HTTP 异常转成友好的状态码
  - 调用存储层保存并返回响应

- **存储/校验层**（`app/api/uploads.py`）
  - 类型白名单、大小限制、安全文件名
  - TTL 清理、file_id 生成、持久化映射
  - 不依赖 FastAPI，便于测试和复用

- **持久化层**（`app/api/persistence.py`）
  - SQLite 记录上传元数据与运行状态
  - 进程内锁保证并发安全

## 数据流概览

```
POST /uploads
  -> 限流/并发控制
  -> save_stream() 流式写盘
  -> 记录 metadata
  -> 返回 file_id
```

## 关键策略

- **流式写盘 + 分块校验**：每个 chunk 累积大小并即时校验，避免一次性读入内存。
- **安全路径**：存储路径为 `uploads/{file_id}/{safe_name}`，并清理危险字符。
- **内容去重**：上传完成后按 `file_hash` 查库，复用已有 `stored_path`，避免重复写盘（同一内容可能共享同一物理文件）。
- **TTL 清理**：后台线程定期清理过期文件；读取时也会触发过期检查。
- **持久化映射**：file_id 与实际路径写入 SQLite，支持重启恢复。

## 降复杂度的调整

当前版本保留结构但做了简化：

1. **修复恢复逻辑**：启动时从 SQLite 恢复记录改为一次性批量载入，避免只恢复最后一条。
2. **统一流式写入流程**：去掉“首块特殊处理”，用单一循环完成读写与大小检查。
3. **file_id 生成简化**：改为 UUID 随机值，不再依赖内容哈希，减少耦合和重复读取。

这些调整不改变功能边界，但降低了代码路径复杂度和潜在 bug 面积。

## 可配置项

### 上传路由层（环境变量）

- `UPLOAD_CONCURRENCY`：上传并发数（默认 2）
- `UPLOAD_RATE_LIMIT_PER_MINUTE`：每分钟上传限流（默认 30）
- `UPLOAD_CHUNK_SIZE`：分块大小（默认 8MB）
- `UPLOAD_READ_TIMEOUT_SECONDS`：读取超时（默认 30s）
- `UPLOAD_WRITE_TIMEOUT_SECONDS`：写入超时（默认 30s）
- `UPLOAD_CONTENT_LENGTH_GRACE_BYTES`：Content-Length 容忍阈值（默认 10MB）

### 存储层（构造参数）

- `upload_dir`：上传根目录（默认 `WORK_PATH/uploads`）
- `max_file_size_mb`：最大文件大小（默认 2048MB）
- `ttl_seconds`：文件保留时长（默认 24h）
- `db_path`：SQLite 路径（默认 `WORK_PATH/metadata.db`）

## 已知限制

- **单机/单进程设计**：限流、队列和缓存都是进程内实现，多实例需要外部组件（如 Redis/消息队列）。
- **不支持断点续传**：大文件上传若需要 resumable upload，可接入对象存储直传或 tus 协议。

如需进一步“生产化”，建议把限流/队列/存储逐步替换为分布式组件。
