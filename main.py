import asyncio
import glob
import os
import shutil
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

from AI.AI_rag.build_model import build_and_save_model
from AI.audio_video.video_to_txt import extract_txt_from_mp4

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

crawler_path = os.path.join(project_root, "crawler")
if crawler_path not in sys.path:
    sys.path.insert(0, crawler_path)


@dataclass
class CrawlerConfig:
    """
    爬虫配置类
    """

    logintype: str
    platform: str
    crawlertype: str


def clean_crawler_data() -> None:
    """
    清空整个crawler/data目录
    """
    crawler_data_dir = "data"

    print("Cleaning crawler data directory...")

    if os.path.exists(crawler_data_dir):
        try:
            # 删除目录中的所有内容
            for filename in os.listdir(crawler_data_dir):
                file_path = os.path.join(crawler_data_dir, filename)
                if os.path.isfile(file_path) or os.path.islink(
                    file_path
                ):  # 判断是否是文件或符号链接
                    os.unlink(file_path)  # 删除文件
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            print(f"  Directory cleaned: {crawler_data_dir}")
        except Exception as e:
            print(f"  Warning: Error cleaning directory {crawler_data_dir}: {e}")
    else:
        print(f"  Directory does not exist: {crawler_data_dir}")
        # 创建目录以便后续使用
        os.makedirs(crawler_data_dir, exist_ok=True)

    print("Crawler data directory cleaning completed")


def find_crawler_files(config: CrawlerConfig) -> List[Tuple[str, str, str]]:
    """
    根据CrawlerConfig查找crawler/data下面的文件
    返回格式: [(json_path, mp4_path, mp3_path), ...]
    """
    file_groups: List[Tuple[str, str, str]] = []

    if config.platform == "bili":
        # 修改为搜索 data/bilibili/videos/*/video.mp4 模式
        search_pattern = f"data/bilibili/videos/**/video.mp4"
        mp4_files = glob.glob(search_pattern, recursive=True)

        if not mp4_files:
            print(
                f"Warning: No matching video files found in data/{config.platform}/videos"
            )
            return file_groups

        print(f"Found {len(mp4_files)} video files:")

        for mp4_path in mp4_files:
            print(f"  - {mp4_path}")
            # 从MP4文件路径推断对应的JSON文件路径
            base_path = mp4_path.replace(".mp4", "")
            json_path = f"{base_path}.json"
            mp3_path = f"{base_path}.mp3"

            file_groups.append((json_path, mp4_path, mp3_path))

    elif config.platform == "zhihu":
        # 对于zhihu平台的文件查找逻辑
        search_pattern = f"data/{config.platform}/json/question_contents_*.json"
        json_files = glob.glob(search_pattern, recursive=True)

        if not json_files:
            print(f"Warning: No matching files found in crawler/data/{config.platform}")
            return file_groups

        print(f"Found {len(json_files)} JSON files:")

        for json_path in json_files:
            print(f"  - {json_path}")
            # 对于zhihu，可能需要不同的处理逻辑
            base_path = json_path.replace(".json", "")
            # 如果zhihu有音频文件，可以设置相应路径
            mp3_path = f"{base_path}.mp3"
            # zhihu可能没有对应的视频文件，设置为空或None
            mp4_path = f"{base_path}.mp4"  # 或者根据实际需求设置

            file_groups.append((json_path, mp4_path, mp3_path))
    return file_groups


async def run_crawler_internal(Cconfig: CrawlerConfig) -> None:
    print("\n=== Starting: Crawler Program ===")
    import importlib.util

    # 明确指定crawler.main的路径
    crawler_main_path = os.path.join(crawler_path, "crawler_main.py")
    spec = importlib.util.spec_from_file_location("crawler_main", crawler_main_path)
    crawler_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(crawler_main)

    # 运行爬虫
    await crawler_main.main(Cconfig.logintype, Cconfig.platform, Cconfig.crawlertype)
    print("Crawler program execution completed")


def process_bili_data(file_groups: List[Tuple[str, str, str]]) -> str:
    """处理B站数据"""
    processed_content = ""

    # 处理所有找到的文件组
    for i, (json_path, input_mp4_path, output_mp3_path) in enumerate(file_groups, 1):
        print(f"\nProcessing file group {i}/{len(file_groups)}:")

        # 检查视频文件是否存在
        if os.path.exists(input_mp4_path):
            print(f"  Video file: {input_mp4_path}")
            try:
                # extract_txt_from_mp4 应该返回文本内容而不是写入文件
                content = extract_txt_from_mp4(input_mp4_path)
                if content:
                    processed_content += content + "\n\n"
            except Exception as e:
                print(f"  Error: Audio conversion failed: {e}")
        else:
            print(f"  Warning: Video file does not exist: {input_mp4_path}")

    return processed_content


def process_zhihu_data(file_groups: List[Tuple[str, str, str]]) -> str:
    """处理知乎数据"""
    processed_content = ""

    for i, (json_path, mp4_path, mp3_path) in enumerate(file_groups, 1):
        print(f"\nProcessing Zhihu file group {i}/{len(file_groups)}:")
        print(f"  JSON file: {json_path}")

        if os.path.exists(json_path):
            try:
                # 加载并处理JSON数据
                with open(json_path, "r", encoding="utf-8") as f:
                    import json

                    data = json.load(f)
                    docs = []
                    for item in data:
                        # 尝试不同可能的字段名
                        content = (
                            item.get("content_text")
                            or item.get("content")
                            or item.get("text")
                            or ""
                        )
                        if content:  # 只添加有内容的文档
                            docs.append(content)

                # 将内容合并为一个字符串
                zhihu_content = "\n\n".join(docs)
                processed_content += zhihu_content + "\n\n"
                print(f"  Processed Zhihu JSON file: {json_path}")

            except Exception as e:
                print(f"  Error: Failed to process Zhihu data: {e}")
        else:
            print(f"  Warning: JSON file does not exist: {json_path}")

    return processed_content


def process_xhs_data(config: CrawlerConfig) -> str:
    """处理小红书数据"""
    processed_content = ""

    if config.crawlertype == "detail":
        # 处理小红书数据
        content_file = "data/xhs/json/detail_contents_2025-09-04.json"
        comments_file = "data/xhs/json/detail_comments_2025-09-04.json"

        xhs_content = []

        # 处理帖子内容
        if os.path.exists(content_file):
            try:
                with open(content_file, "r", encoding="utf-8") as f:
                    import json

                    data = json.load(f)
                    # 如果是列表，取第一个元素
                    post = data[0] if isinstance(data, list) else data

                    # 提取帖子主要内容
                    xhs_content.append("帖子标题: " + post.get("title", ""))
                    xhs_content.append("帖子描述: " + post.get("desc", ""))
                    xhs_content.append(
                        "最后更新时间: " + str(post.get("last_update_time", ""))
                    )
                    xhs_content.append("用户ID: " + post.get("user_id", ""))
                    xhs_content.append("用户名: " + post.get("nickname", ""))
                    xhs_content.append("用户地区: " + post.get("ip_location", ""))
                    xhs_content.append("点赞数: " + post.get("liked_count", ""))
                    xhs_content.append("收藏数: " + post.get("collected_count", ""))
                    xhs_content.append("评论数: " + post.get("comment_count", ""))
                    xhs_content.append("标签: " + post.get("tag_list", ""))
                    xhs_content.append("")  # 空行分隔

            except Exception as e:
                print(f"  Error: Failed to process XHS content data: {e}")
        else:
            print(f"  Warning: XHS content file does not exist: {content_file}")

        # 处理评论内容
        if os.path.exists(comments_file):
            try:
                with open(comments_file, "r", encoding="utf-8") as f:
                    import json

                    comments_data = json.load(f)

                    # 提取每条评论的关键信息
                    for comment in comments_data:
                        xhs_content.append("评论地区: " + comment.get("ip_location", ""))
                        xhs_content.append("评论内容: " + comment.get("content", ""))
                        xhs_content.append(
                            "回复数: " + comment.get("sub_comment_count", "")
                        )
                        xhs_content.append("点赞数: " + comment.get("like_count", ""))
                        xhs_content.append("")  # 空行分隔

            except Exception as e:
                print(f"  Error: Failed to process XHS comments data: {e}")
        else:
            print(f"  Warning: XHS comments file does not exist: {comments_file}")

        # 将内容合并为一个字符串
        processed_content += "\n".join(xhs_content) + "\n\n"
        print("  Processed XHS data")

    return processed_content


def process_crawler_data(Cconfig: CrawlerConfig) -> str:
    """
    处理爬虫生成的数据文件，将数据转换为文本格式
    返回处理后的文本内容
    """
    # 查找爬虫生成的文件
    file_groups = find_crawler_files(Cconfig)
    processed_content = ""

    if Cconfig.platform == "bili" and file_groups:
        processed_content = process_bili_data(file_groups)
    elif Cconfig.platform == "zhihu" and file_groups:
        processed_content = process_zhihu_data(file_groups)
    elif Cconfig.platform == "xhs":
        processed_content = process_xhs_data(Cconfig)

    return processed_content.strip()


async def main(Cconfig: CrawlerConfig) -> None:
    # 0. 清空之前的数据文件（在爬虫运行前）
    print("\n" + "=" * 50)
    print("Step 0: Clean historical crawler data")
    print("=" * 50)
    clean_crawler_data()

    # 1. 执行爬虫
    print("\n" + "=" * 50)
    print("Step 1: Execute crawler program")
    print("=" * 50)
    await run_crawler_internal(Cconfig)

    # 2. 执行数据转化
    print("\n" + "=" * 50)
    print("Step 2: Execute audio to text program")
    print("=" * 50)

    # 查找爬虫生成的文件，将爬虫文件最后生成txt文件
    processed_content = process_crawler_data(Cconfig)

    # 3. 执行模型构建
    print("\n" + "=" * 50)
    print("Step 3: Execute model building program")
    print("=" * 50)

    if processed_content:
        # 创建临时文件用于模型构建
        temp_file_path = f"temp_{Cconfig.platform}_data.txt"
        try:
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(processed_content)

            model_name = Cconfig.platform + "_model"
            model_type = Cconfig.platform + "_model"
            build_and_save_model(
                data_path=temp_file_path, model_name=model_name, model_type=model_type
            )
        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    else:
        print("  Error: No valid data content found for model building")

    # 4. 清空爬虫生成文件（可选）
    print("\n" + "=" * 50)
    print("Step 4: Clean crawler generated files")
    print("=" * 50)
    # clean_crawler_data()  # 如果需要在最后也清空数据，取消注释这行


if __name__ == "__main__":
    # Cconfig = CrawlerConfig(
    #     logintype="cookie",
    #     platform="zhihu",
    #     crawlertype="question"
    # )

    # Alternative configurations:
    # Cconfig = CrawlerConfig(
    #     logintype="cookie",
    #     platform="bili",
    #     crawlertype="detail"
    # )

    Cconfig = CrawlerConfig(logintype="qrcode ", platform="xhs", crawlertype="detail")

    try:
        asyncio.run(main(Cconfig))
    except KeyboardInterrupt:
        sys.exit()
