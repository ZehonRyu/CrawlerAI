import asyncio
import json
import logging
import os
from collections import Counter

import aiofiles
import config
import execjs
import jieba
import matplotlib.pyplot as plt
from tools import utils
from tools.utils import get_resource_path, validate_file_path
from wordcloud import WordCloud

# 获取项目根目录
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
# js_file_path = os.path.join(project_root, 'libs', 'douyin.js')

# 正确的调用方式
js_file_path = get_resource_path("crawler/libs/douyin.js")

# 或者使用已有的工具函数（如果可用）
# js_file_path = get_resource_path("libs/douyin.js")

if os.path.exists(js_file_path):
    douyin_sign_obj = execjs.compile(open(js_file_path, encoding="utf-8-sig").read())
else:
    raise FileNotFoundError(f"找不到文件: {js_file_path}")


plot_lock = asyncio.Lock()


class AsyncWordCloudGenerator:
    def __init__(self):
        logging.getLogger("jieba").setLevel(logging.WARNING)
        # 使用路径工具获取文件路径
        self.stop_words_file = get_resource_path("crawler/docs/hit_stopwords.txt")

        # 验证文件是否存在
        if not validate_file_path(self.stop_words_file):
            raise FileNotFoundError(f"停止词文件不存在: {self.stop_words_file}")
        self.lock = asyncio.Lock()
        self.stop_words = self.load_stop_words()
        self.custom_words = config.CUSTOM_WORDS
        for word, group in self.custom_words.items():
            jieba.add_word(word)

    def load_stop_words(self):
        with open(self.stop_words_file, "r", encoding="utf-8") as f:
            return set(f.read().strip().split("\n"))

    async def generate_word_frequency_and_cloud(self, data, save_words_prefix):
        all_text = " ".join(item["content"] for item in data)
        words = [
            word
            for word in jieba.lcut(all_text)
            if word not in self.stop_words and len(word.strip()) > 0
        ]
        word_freq = Counter(words)

        # Save word frequency to file
        freq_file = f"{save_words_prefix}_word_freq.json"
        async with aiofiles.open(freq_file, "w", encoding="utf-8") as file:
            await file.write(json.dumps(word_freq, ensure_ascii=False, indent=4))

        # Try to acquire the plot lock without waiting
        if plot_lock.locked():
            utils.logger.info("Skipping word cloud generation as the lock is held.")
            return

        await self.generate_word_cloud(word_freq, save_words_prefix)

    async def generate_word_cloud(self, word_freq, save_words_prefix):
        await plot_lock.acquire()
        top_20_word_freq = {
            word: freq
            for word, freq in sorted(
                word_freq.items(), key=lambda item: item[1], reverse=True
            )[:20]
        }
        wordcloud = WordCloud(
            font_path=config.FONT_PATH,
            width=800,
            height=400,
            background_color="white",
            max_words=200,
            stopwords=self.stop_words,
            colormap="viridis",
            contour_color="steelblue",
            contour_width=1,
        ).generate_from_frequencies(top_20_word_freq)

        # Save word cloud image
        plt.figure(figsize=(10, 5), facecolor="white")
        plt.imshow(wordcloud, interpolation="bilinear")

        plt.axis("off")
        plt.tight_layout(pad=0)
        plt.savefig(f"{save_words_prefix}_word_cloud.png", format="png", dpi=300)
        plt.close()

        plot_lock.release()
