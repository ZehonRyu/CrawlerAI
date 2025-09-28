FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.9.19

# 设置工作目录
WORKDIR /app

# 分步安装依赖以减少失败可能性
RUN apt-get update || echo "apt update failed, continuing..."
RUN apt-get install -y --no-install-recommends gcc g++ || echo "gcc g++ installation failed, continuing..."
RUN apt-get install -y --no-install-recommends ffmpeg || echo "ffmpeg installation failed, continuing..."
RUN apt-get install -y --no-install-recommends portaudio19-dev pkg-config || echo "portaudio19-dev pkg-config installation failed, continuing..."
RUN apt-get install -y --no-install-recommends git || echo "git installation failed, continuing..."
RUN rm -rf /var/lib/apt/lists/* 2>/dev/null || echo "cleanup failed, continuing..."

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
