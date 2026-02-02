FROM video-summary-basic:1.0.0

# ========== 元信息 ==========
LABEL com.rcny.video-summary.description="video-summary python program" \
      com.rcny.video-summary.author="rcny" \
      com.rcny.video-summary.url="http://www.hbrcny.cn/"

# 设置工作目录
WORKDIR /app

# 拷贝代码
COPY ./ ./


CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8765"]
