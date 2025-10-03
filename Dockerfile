# 使用华为云镜像源
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.9-slim

# 设置工作目录
WORKDIR /app

# 替换为阿里云的Debian镜像源
RUN echo "deb http://mirrors.aliyun.com/debian/ bullseye main non-free contrib" > /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian/ bullseye main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian-security/ bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list

# 更新包列表并安装系统依赖，包括编译工具
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    build-essential \
    libffi-dev \
    ffmpeg \
    portaudio19-dev \
    pkg-config \
    git \
    wget \
    curl \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2 \
    libatspi2.0-0 \
    libgtk-3-0 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# 升级pip
RUN pip install --upgrade pip

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 安装playwright浏览器
RUN playwright install chromium

# 复制项目代码
COPY . .

# 下载并安装faster-whisper模型（可选，避免运行时下载）
RUN python -c "from faster_whisper import WhisperModel; model = WhisperModel('small', device='cpu', compute_type='int8')"

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV HOST=0.0.0.0
ENV PORT=5000
ENV DEBUG=False

# 启动应用
CMD ["python", "app.py"]
