import os
import subprocess
import sys


def extract_audio_from_mp4(input_mp4_path: str, output_mp3_path: str) -> None:
    """
    从 MP4 文件中提取音频并保存为 MP3 格式

    参数:
    input_mp4_path (str): 输入的 MP4 文件路径
    output_mp3_path (str): 输出的 MP3 文件路径

    异常:
    FileNotFoundError: 当输入文件不存在时抛出
    Exception: 处理过程中的其他错误
    """
    if not os.path.exists(input_mp4_path):
        raise FileNotFoundError(f"输入文件不存在: {input_mp4_path}")

    # 确保输出目录存在
    output_dir = os.path.dirname(output_mp3_path)
    if output_dir:  # 仅当输出目录非空时才创建
        os.makedirs(output_dir, exist_ok=True)

    # 构建 FFmpeg 命令
    ffmpeg_cmd = [
        "ffmpeg",
        "-i",
        input_mp4_path,
        "-vn",  # 禁用视频流
        "-acodec",
        "mp3",  # 音频编码为 MP3
        "-ab",
        "192k",  # 音频比特率
        "-y",  # 覆盖输出文件
        output_mp3_path,
    ]

    try:
        # 执行 FFmpeg 命令
        result = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise Exception(f"音频提取失败: {e.stderr}")
    except FileNotFoundError:
        raise Exception("未找到 FFmpeg 可执行文件，请确保 FFmpeg 已正确安装并添加到系统路径")
