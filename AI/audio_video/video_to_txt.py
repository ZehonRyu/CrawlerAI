import os

from . import audio_to_txt_fasterwhisper, video_to_audio


def extract_txt_from_mp4(input_mp4_path: str):
    mp3_path = input_mp4_path[:-4] + ".mp3"
    txt_path = input_mp4_path[:-4] + ".txt"

    try:
        # 提取音频
        video_to_audio.extract_audio_from_mp4(input_mp4_path, mp3_path)

        # 转录音频为文本
        transcription = audio_to_txt_fasterwhisper.transcribe_audio(mp3_path)

        # 保存转录结果到txt文件
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(transcription)

        # 删除中间mp3文件
        if os.path.exists(mp3_path):
            os.remove(mp3_path)

        # 确保返回转录内容
        if transcription and transcription.strip():
            return transcription
        else:
            return ""
    except Exception as e:
        # 清理可能存在的临时文件
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
        raise e


if __name__ == "__main__":
    input_mp4_path = "data/bilibili/video/BV1jE411x7yz.mp4"
    extract_txt_from_mp4(input_mp4_path)
