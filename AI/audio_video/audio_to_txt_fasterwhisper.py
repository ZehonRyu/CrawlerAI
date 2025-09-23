import os
import re

import torch
from faster_whisper import WhisperModel
from opencc import OpenCC
from pydub import AudioSegment
from pydub.effects import normalize

# 设置 FFmpeg 路径
ffmpeg_bin = r"F:/Project/AiProject/ffmpeg-7.0.2-essentials_build/bin"
os.environ["PATH"] = ffmpeg_bin + os.pathsep + os.environ["PATH"]

# 检查GPU可用性
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"  # GPU用float16，CPU用int8

# 使用用户目录作为模型缓存路径，避免权限问题
# MODEL_CACHE_DIR = os.path.join(
#     os.path.expanduser("~"), ".cache", "faster_whisper_models"
# )

# os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
MODEL_PATH = os.path.join(PROJECT_ROOT, "AI", "audio_video", "models")
LOCAL_MODEL_DIR = os.path.join(MODEL_PATH, "models--Systran--faster-whisper-small")

# 确保模型目录存在
os.makedirs(MODEL_PATH, exist_ok=True)


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
        # audio.export(temp_path, format="wav")
        audio.export(
            temp_path,
            format="wav",
            parameters=["-ar", "16000", "-ac", "1", "-acodec", "pcm_s16le"],
        )
        return temp_path
    except Exception as e:
        print(f"音频预处理失败: {e}")
        return input_path  # 失败时返回原文件


# ... existing code ...
def postprocess_text(text: str) -> str:
    """优化文本输出：繁体转简体 + 智能清理 + 修复提示词泄露
    Args:
        text: 原始识别文本
    Returns:
        后处理后的文本
    """
    cc = OpenCC("t2s")
    text = cc.convert(text)  # 繁体转简体

    # 清理多余空格和标点
    text = re.sub(r"请保持内容连贯性并使用自然断句[：﹚]*", "", text)
    text = re.sub(r"长音频.*?自然断句", "", text)
    text = re.sub(r"普通话简体中文转录.*?自然断句", "", text)

    # 处理中文文本空格
    text = re.sub(r"([\u4e00-\u9fff])\s+", r"\1", text)
    text = re.sub(r"\s+([\u4e00-\u9fff])", r"\1", text)

    # 标准化标点符号
    text = re.sub(r"。+", "。", text)
    text = re.sub(r"，\s+", "，", text)
    text = re.sub(r"\?", "？", text)
    text = re.sub(r"\!", "！", text)

    # 处理重复内容（更智能的方式）
    # 使用更保守的方法处理重复，避免误删重要内容
    sentences = re.split(r"([。！？])", text)
    cleaned_sentences = []
    seen_sentences = set()

    for i in range(0, len(sentences) - 1, 2):
        if i + 1 < len(sentences):
            sentence = sentences[i] + sentences[i + 1]
            # 简单去重，但保留短句（可能是强调）
            if sentence not in seen_sentences or len(sentence) < 10:
                cleaned_sentences.append(sentence)
                seen_sentences.add(sentence)

    text = "".join(cleaned_sentences)

    return text.strip()


# ... existing code ...


def enhanced_transcribe(
    model: WhisperModel, audio_path: str, is_long: bool = False
) -> str:
    """增强AI断句能力的转录函数
    Args:
        model: Whisper模型实例
        audio_path: 音频文件路径
        is_long: 是否为长音频
    Returns:
        转录文本
    """
    prompt = "长音频普通话简体中文转录保持内容连贯性自然断句" if is_long else "普通话简体中文转录使用正确标点自然断句"

    segments, _ = model.transcribe(
        audio_path,
        language="zh",
        initial_prompt=prompt,
        beam_size=5,
        best_of=5,
        temperature=0.0,
        condition_on_previous_text=True,
        vad_filter=True,
        vad_parameters=dict(
            threshold=0.35,
            min_speech_duration_ms=300,
            min_silence_duration_ms=500,
            speech_pad_ms=200,  # 增加语音前后填充
        ),
        without_timestamps=True,
    )

    full_text = "".join(segment.text for segment in segments)
    return full_text.replace(prompt, "")  # 移除可能的提示词残留


# ... existing code ...
def transcribe_in_segments(
    model: WhisperModel, audio_path: str, segment_length: int = 45, overlap: int = 5
) -> str:
    """智能分段处理长音频
    Args:
        model: Whisper模型实例
        audio_path: 音频文件路径
        segment_length: 每段长度(秒)
        overlap: 段间重叠(秒)
    Returns:
        拼接后的完整文本
    """
    audio = AudioSegment.from_wav(audio_path)
    total_length = len(audio) / 1000
    segments = []

    start = 0
    segment_index = 0
    previous_text = ""

    while start < total_length:
        end = min(start + segment_length, total_length)
        segment_start = max(0, start - (overlap if segment_index > 0 else 0))
        segment_end = min(end + overlap, total_length)

        # 创建临时分段文件
        segment = audio[int(segment_start * 1000) : int(segment_end * 1000)]
        segment_path = f"temp_segment_{segment_index}.wav"
        segment.export(segment_path, format="wav")

        # 转录当前段，传递前一段的上下文
        segment_text = enhanced_transcribe_with_context(
            model, segment_path, previous_text
        )

        # 记录当前段文本作为下一段的上下文
        previous_text = segment_text[-200:] if len(segment_text) > 200 else segment_text

        segments.append(segment_text.strip())
        os.remove(segment_path)  # 立即删除临时分段

        start = end
        segment_index += 1

    # 合并结果并去除重复部分
    return merge_segments(segments)


def enhanced_transcribe_with_context(
    model: WhisperModel, audio_path: str, previous_text: str = ""
) -> str:
    """带上下文的增强转录函数
    Args:
        model: Whisper模型实例
        audio_path: 音频文件路径
        previous_text: 前一段文本作为上下文
    Returns:
        转录文本
    """
    prompt = "根据前面内容继续转录普通话简体中文保持上下文连贯性"

    segments, _ = model.transcribe(
        audio_path,
        language="zh",
        initial_prompt=prompt,
        prefix=previous_text[-100:] if previous_text else "",  # 提供前文作为前缀
        beam_size=5,
        best_of=5,
        temperature=0.0,
        condition_on_previous_text=True,
        vad_filter=True,
        vad_parameters=dict(
            threshold=0.35,
            min_speech_duration_ms=250,
            min_silence_duration_ms=500,
            speech_pad_ms=200,
        ),
        without_timestamps=True,
    )

    full_text = "".join(segment.text for segment in segments)
    return full_text.replace(prompt, "")


def merge_segments(segments):
    """合并分段结果，去除重复部分
    Args:
        segments: 分段文本列表
    Returns:
        合并后的文本
    """
    if not segments:
        return ""

    merged = segments[0]
    for i in range(1, len(segments)):
        # 查找重叠部分并合并
        overlap_found = False
        # 简单的重叠检测和合并策略
        segment = segments[i]
        # 如果能找到明显的句子结尾后的内容匹配，则认为是重叠部分
        sentences = re.split(r"[。！？]", merged)
        if len(sentences) > 1:
            last_sentence = sentences[-1]
            if len(last_sentence) > 10 and last_sentence in segment:
                # 找到重叠，只保留新段落中不重复的部分
                overlap_pos = segment.find(last_sentence)
                if overlap_pos >= 0:
                    merged += segment[overlap_pos + len(last_sentence) :]
                    overlap_found = True

        if not overlap_found:
            merged += segment

    return merged


# ... existing code ...
def transcribe_audio(input_path: str) -> str:
    """主转录函数：输入MP3路径，返回转录文本
    Args:
        input_path: 输入的MP3文件路径
    Returns:
        转录后的文本内容
    """
    # 预处理音频并获取临时WAV路径
    processed_path = preprocess_audio(input_path)

    try:
        # 检查本地模型是否存在
        if os.path.exists(LOCAL_MODEL_DIR) and os.listdir(LOCAL_MODEL_DIR):
            print(f"使用本地模型: {LOCAL_MODEL_DIR}")
            model = WhisperModel(
                LOCAL_MODEL_DIR, device=DEVICE, compute_type=COMPUTE_TYPE
            )
        else:
            print("本地模型不存在，将使用在线模型并自动下载")
            # 确保缓存目录存在
            os.makedirs(MODEL_PATH, exist_ok=True)
            model = WhisperModel(
                "small",
                device=DEVICE,
                compute_type=COMPUTE_TYPE,
                download_root=MODEL_PATH,
            )

        # 判断音频长度
        audio = AudioSegment.from_wav(processed_path)
        is_long = (len(audio) / 1000) > 40

        # 选择处理方式
        result_text = (
            transcribe_in_segments(model, processed_path)
            if is_long
            else enhanced_transcribe(model, processed_path)
        )

        # 后处理文本
        return postprocess_text(result_text)

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
