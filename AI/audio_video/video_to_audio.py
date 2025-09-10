import os

from moviepy.editor import VideoFileClip


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

    # 加载视频文件并提取音频
    video = VideoFileClip(input_mp4_path)
    audio = video.audio

    # 保存为 MP3 格式
    audio.write_audiofile(output_mp3_path, verbose=False, logger=None)

    # 释放资源
    audio.close()
    video.close()


if __name__ == "__main__":
    # 测试代码
    try:
        print("开始提取音频...")
        extract_audio_from_mp4(
            input_mp4_path="F:/Project/CrawlerAI/crawler/data/bilibili/videos/114857860931075/video.mp4",
            output_mp3_path="F:/Project/CrawlerAI/data/video_fan.mp3",
        )
        print("✅ 音频提取成功！输出文件: video_fan.mp3")
    except Exception as e:
        print(f"❌ 处理失败: {str(e)}")
