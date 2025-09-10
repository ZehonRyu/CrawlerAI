import os

from . import audio_to_txt_fasterwhisper, video_to_audio


def extract_txt_from_mp4(input_mp4_path: str):
    video_to_audio.extract_audio_from_mp4(input_mp4_path, input_mp4_path[:-4] + ".mp3")
    transcription = audio_to_txt_fasterwhisper.transcribe_audio(
        input_mp4_path[:-4] + ".mp3"
    )
    output_txt_path = input_mp4_path[:-4] + ".txt"
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write(transcription)
    # 删除中间mp3文件
    os.remove(input_mp4_path[:-4] + ".mp3")
    return transcription


if __name__ == "__main__":
    input_mp4_path = "data/bilibili/video/BV1jE411x7yz.mp4"
    extract_txt_from_mp4(input_mp4_path)
