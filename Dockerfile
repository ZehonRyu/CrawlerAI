FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    ffmpeg \
    portaudio19-dev \
    pkg-config \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install "Cython<3.0.0"
RUN pip install -r requirements.txt

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV HOST=0.0.0.0
ENV PORT=5000
ENV DEBUG=False

# 启动应用
CMD ["python", "app.py"]
