import logging
import os
import re

# Deleted:import whisper
from faster_whisper import WhisperModel
from opencc import OpenCC
from pydub import AudioSegment
from pydub.effects import normalize

# 设置日志配置 - 使用 force=True 确保配置生效
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
FFMPEG_PATH = os.path.join(
    PROJECT_ROOT, "AI", "audio_video", "ffmpeg-7.0.2-essentials_build", "bin"
)

# 如果项目中的FFmpeg路径存在，则使用它
if os.path.exists(FFMPEG_PATH):
    os.environ["PATH"] = FFMPEG_PATH + os.pathsep + os.environ["PATH"]
    logger.info(f"使用项目内置FFmpeg: {FFMPEG_PATH}")
else:
    logger.info("未找到项目内置FFmpeg，使用系统PATH中的FFmpeg")


def preprocess_audio(input_path: str) -> str:
    """优化音频质量以提高识别准确率
    Args:
        input_path: 输入的音频文件路径
    Returns:
        预处理后的临时WAV文件路径
    """
    try:
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_channels(1)  # 转换为单声道

        # 设置最佳采样率
        if audio.frame_rate != 16000:
            audio = audio.set_frame_rate(16000)

        audio = normalize(audio)  # 音量标准化
        audio = audio.compress_dynamic_range()  # 动态范围压缩

        # 创建临时文件
        temp_path = "temp_processed.wav"
        audio.export(
            temp_path,
            format="wav",
            parameters=["-ar", "16000", "-ac", "1", "-acodec", "pcm_s16le"],
        )
        return temp_path
    except Exception as e:
        logger.error(f"音频预处理失败: {e}")
        return input_path  # 失败时返回原文件


def transcribe_audio(input_path: str) -> str:
    """主转录函数：输入MP3路径，返回转录文本
    Args:
        input_path: 输入的MP3文件路径
    Returns:
        转录后的文本内容
    """
    # 预处理音频并获取临时WAV路径
    processed_path = preprocess_audio(input_path)

    # 检查预处理后的文件
    if not os.path.exists(processed_path):
        logger.error(f"错误: 预处理后的音频文件未生成: {processed_path}")
        return ""

    try:
        logger.info("加载Whisper模型...")
        # 直接从Hugging Face下载模型（现在可以正常联网了）
        # model = WhisperModel("small", device="cpu", compute_type="int8")
        # model = WhisperModel("/app/AI/audio_video/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120", device="cpu", compute_type="int8")

        local_model_path = os.path.join(
            PROJECT_ROOT,
            "AI",
            "audio_video",
            "models",
            "models--Systran--faster-whisper-small",
            "snapshots",
            "536b0662742c02347bc0e980a01041f333bce120",
        )
        logger.info(f"尝试加载模型路径: {local_model_path}")
        logger.info(f"模型路径是否存在: {os.path.exists(local_model_path)}")

        if os.path.exists(local_model_path):
            logger.info("模型目录中的文件:")
            try:
                for file in os.listdir(local_model_path):
                    logger.info(f"  {file}")
            except Exception as e:
                logger.error(f"无法列出模型目录内容: {e}")
        else:
            logger.error("模型路径不存在！")
            return ""

        # 尝试多种方式加载模型
        logger.info("尝试使用 local_files_only=True 加载模型...")
        try:
            model = WhisperModel(
                local_model_path,
                device="cpu",
                compute_type="int8",
                local_files_only=True,
            )
        except Exception as e:
            logger.warning(f"使用 local_files_only=True 失败: {e}")
            logger.info("尝试不使用 local_files_only 参数加载模型...")
            model = WhisperModel(local_model_path, device="cpu", compute_type="int8")

        logger.info("模型加载完成")

        # 转录音频
        logger.info("正在进行音频转录...")
        segments, info = model.transcribe(processed_path, language="zh")
        logger.info(f"检测到语言: {info.language}, 置信度: {info.language_probability}")

        # 收集所有转录文本
        text = ""
        for segment in segments:
            text += segment.text
        logger.info("音频转录完成")

        # 后处理文本
        logger.info("正在进行文本后处理...")
        return text

    except Exception as e:
        logger.error(f"转录过程中发生错误: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return ""
    finally:
        # 确保删除临时WAV文件
        if processed_path != input_path and os.path.exists(processed_path):
            os.remove(processed_path)


if __name__ == "__main__":
    audio_path = "F:/Project/CrawlerAI/data/video_fan.mp3"
    transcription = transcribe_audio(audio_path)
    print(transcription)

    # 从音频文件名生成输出文件名
    audio_filename = os.path.basename(audio_path)  # 获取文件名（带扩展名）
    base_name = os.path.splitext(audio_filename)[0]  # 去除扩展名
    output_filename = (
        f"F:/Project/CrawlerAI/data/{base_name}_transcription.txt"  # 生成新的输出文件名
    )

    # 保存结果到文件
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(transcription)
    print(f"结果已保存到 {output_filename}")
