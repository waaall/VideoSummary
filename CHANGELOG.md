## 更新日志


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