# 构建阶段 - 用于安装依赖和编译
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.9 AS builder

# 设置工作目录
WORKDIR /app

# 替换为阿里云的Debian镜像源以提高下载速度
RUN echo "deb http://mirrors.aliyun.com/debian/ bullseye main non-free contrib" > /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian/ bullseye main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian-security/ bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list

# 更新包列表并安装构建依赖（包括编译工具）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    build-essential \
    git \
    pkg-config \
    portaudio19-dev && \
    rm -rf /var/lib/apt/lists/*

# 升级pip
RUN pip install --upgrade pip

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# === 构建阶段结束 ===

# 运行阶段 - 用于最终运行应用
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.9-slim AS runtime

# 设置工作目录
WORKDIR /app

# 替换为阿里云的Debian镜像源以提高下载速度
RUN echo "deb http://mirrors.aliyun.com/debian/ bullseye main non-free contrib" > /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian/ bullseye main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian-security/ bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list

# 更新包列表并安装运行时系统依赖（包括JavaScript运行时和图形界面依赖）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
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
    libgtk-3.0 \
    xvfb \
    curl \
    gnupg \
    libx11-6 \
    libxext6 \
    libxrender1 && \
    rm -rf /var/lib/apt/lists/*

# 安装Node.js作为JavaScript运行时
RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# 从构建阶段复制已安装的Python包
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

# 安装playwright浏览器依赖
# 使用python -m方式调用playwright命令
RUN pip install --no-cache-dir playwright
RUN python -m playwright install-deps
RUN python -m playwright install chromium

# 复制应用代码（只复制必要的文件，避免复制data等大目录）
COPY app.py main.py downloaw.py ./
COPY AI/ ./AI/
COPY crawler/ ./crawler/
COPY frontend/ ./frontend/
COPY AI/audio_video/models/ /app/AI/audio_video/models/
# 创建必要的运行时目录
RUN mkdir -p data browser_data

# 下载并安装faster-whisper模型（避免运行时下载）
# 优化: 只下载模型，不加载模型以减少缓存文件
RUN python -c "import os; os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'" && \
    python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small', local_files_only=False, mirror='https://hf-mirror.com')" 2>/dev/null || \
    python -c "from faster_whisper import WhisperModel; model = WhisperModel('small', device='cpu', compute_type='int8')" 2>/dev/null || \
    echo "Model download/installation completed"
RUN apt-get update && apt-get install -y xvfb xauth
# === 关键：清理不必要的缓存，保留必需的模型文件 ===
RUN pip cache purge && \
    # 清理pip缓存
    rm -rf /root/.cache/pip && \
    # 清理临时文件
    find /root/.cache -type f -name "*.tmp" -delete 2>/dev/null || true && \
    find /root/.cache -type f -name "*.cache" -delete 2>/dev/null || true && \
    # 清理不必要的huggingface缓存（保留模型文件）
    find /root/.cache/huggingface -type f -not -name "*.bin" -not -name "*.txt" -not -name "*.json" -not -name "*.model" -delete 2>/dev/null || true && \
    # 清理apt缓存
    rm -rf /var/lib/apt/lists/*

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV HOST=0.0.0.0
ENV PORT=5000
ENV DEBUG=False
ENV DATA_DIR=/app/data
ENV BROWSER_DATA_DIR=/app/browser_data
ENV HEADLESS=true
ENV REDIS_URL=redis://host.docker.internal:6379/0


# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# 启动应用（使用xvfb-run提供更可靠的虚拟显示环境）
CMD ["xvfb-run", "-a", "python", "app.py"]
