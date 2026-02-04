FROM video-summary-basic:1.0.0

# 设置工作目录
WORKDIR /app

# 拷贝代码
COPY ./ ./


CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8765"]
