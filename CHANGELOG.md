## 更新日志

### 2026-02-12 - API 重构（Breaking）

- 直接替换 `/api/*`，不提供向后兼容层。
- 引入 Pydantic v2 强类型 schema（枚举、URL、regex、条件校验）。
- 拆分 `BaseSettings`：
  - `app/api/settings.py`（按领域定义 Upload/RateLimit/Worker）
- 新增依赖层 `app/api/dependencies.py`：
  - 限流依赖（上传/摘要）
  - 资源解析依赖（source 解析、job/cache 校验）
- 状态码语义调整：
  - `POST /api/uploads` -> `201`
  - `POST /api/summaries` -> `200`（命中）/`202`（处理中或新入队）
- 将上传异步路径中的文件系统与 SQLite 阻塞点统一迁移到 `asyncio.to_thread`。
- 增加 API 测试覆盖：
  - `tests/test_api/test_schemas_v2.py`
  - `tests/test_api/test_dependencies.py`
- 重写文档：`docs/dev/api.md`
- 新增升级文档：`docs/dev/api-breaking-changes.md`

## 已知问题

### 并发性能问题

/summaries 是异步：未命中会入队并返回 job_id，前端轮询 /jobs/{id}。main.py worker.py
任务执行用进程内 queue.Queue + 线程，线程数由 JOB_WORKER_COUNT 决定，默认 1。worker.py main.py docker-compose.yml
转码/转录阶段还有独立并发阈值：TRANSCODE_CONCURRENCY、TRANSCRIBE_CONCURRENCY，默认 2。limits.py
上传并发被 UPLOAD_SEMAPHORE 限制，默认 2。limits.py

#### 可能的瓶颈/风险

URL 的 cache_key 计算会调用 yt-dlp 获取身份信息，这是同步网络 IO，发生在请求入口线程中。cache_key.py main.py
本地文件如果缺 file_hash，会在入口线程里流式计算 SHA256；大文件会拖慢入口吞吐。main.py cache_key.py
任务队列是进程内的，重启会丢队列；多进程/多实例无法共享队列。worker.py
get_or_create_entry 非原子，多个请求同一 cache_key 可能重复创建任务或触发 SQLite 冲突。cache_service.py persistence.py
限流器/并发控制是内存级别，多进程或多实例不会全局生效。limits.py
SQLite 单连接 + 进程内锁，吞吐会被串行化；多进程下还有锁争用风险。persistence.py
