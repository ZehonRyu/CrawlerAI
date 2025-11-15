import argparse
import asyncio
import glob
import logging
import os
import re
import shutil
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from AI.audio_video.video_to_txt import extract_txt_from_mp4
from crawler_celery import celery_app

# 设置项目根目录
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 添加crawler目录到sys.path
crawler_path = os.path.join(project_root, "crawler")
if crawler_path not in sys.path:
    sys.path.insert(0, crawler_path)

# 在导入crawler.var之前确保路径设置正确
try:
    from crawler import db
    from crawler.var import task_id_var
except ImportError:
    # 如果相对导入失败，尝试直接导入
    import db
    import var

    task_id_var = var.task_id_var


# 会话管理类
class UserSession:
    def __init__(self, task_id=None):
        self.task_id = task_id or str(uuid.uuid4())
        self.session_dir = f"sessions/{self.task_id}"
        self.data_dir = f"{self.session_dir}/data"
        self.transmit_dir = f"{self.session_dir}/transmit_data"
        self.config_dir = f"{self.session_dir}/config"

    def setup_session(self):
        """创建会话目录结构"""
        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.transmit_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        return self

    def cleanup_session(self):
        """清理会话目录"""
        if os.path.exists(self.session_dir):
            shutil.rmtree(self.session_dir)


# 线程本地存储用于隔离不同请求的环境变量
class RequestLocal:
    def __init__(self):
        self.local = threading.local()

    def set_session(self, session):
        self.local.session = session

    def get_session(self):
        return getattr(self.local, "session", None)


request_local = RequestLocal()


@dataclass
class CrawlerConfig:
    """
    爬虫配置类
    """

    logintype: str
    platform: str
    crawlertype: str
    session: UserSession = None


def clean_crawler_data(session=None) -> None:
    """
    清空crawler/data目录
    如果提供了session，则只清空该会话的数据
    """
    if session:
        # 只清理特定会话的数据
        crawler_data_dir = session.data_dir
        print(f"Cleaning session data directory: {crawler_data_dir}")
    else:
        # 清理全局数据目录（向后兼容）
        crawler_data_dir = "data"
        print("Cleaning global crawler data directory...")

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

    # 使用会话特定的数据目录
    data_base_dir = "data"  # 默认数据目录
    if config.session and hasattr(config.session, "data_dir"):
        data_base_dir = config.session.data_dir
        print(f"Using session data directory: {data_base_dir}")
    else:
        print(f"Using default data directory: {data_base_dir}")

    if config.platform == "bilibili":
        # 修改为搜索 data/bilibili/videos/*/video.mp4 模式
        search_pattern = f"{data_base_dir}/bilibili/videos/**/video.mp4"
        mp4_files = glob.glob(search_pattern, recursive=True)

        if not mp4_files:
            print(
                f"Warning: No matching video files found in {data_base_dir}/{config.platform}/videos"
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
        search_pattern = (
            f"{data_base_dir}/{config.platform}/json/question_contents_*.json"
        )
        json_files = glob.glob(search_pattern, recursive=True)

        if not json_files:
            # 如果在特定目录没找到，尝试在默认目录查找
            default_search_pattern = (
                f"data/{config.platform}/json/question_contents_*.json"
            )
            json_files = glob.glob(default_search_pattern, recursive=True)
            print(f"Trying default directory, found {len(json_files)} JSON files")

        if not json_files:
            print(
                f"Warning: No matching files found in {data_base_dir}/{config.platform}"
            )
            # 列出目录内容帮助调试
            json_dir = f"{data_base_dir}/{config.platform}/json"
            if os.path.exists(json_dir):
                print(f"Files in {json_dir}: {os.listdir(json_dir)}")
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


def run_crawler_internal(
    self,
    logintype: str,
    platform: str,
    crawlertype: str,
    url: str = None,
    task_type: str = None,
) -> dict:
    print("\n=== Starting: Crawler Program ===")

    try:
        # 获取任务ID（从var模块或环境变量）
        from crawler.var import task_id_var

        task_id = task_id_var.get() or os.environ.get("CRAWLER_TASK_ID")
        print(f"执行中的任务ID: {task_id} (类型: {type(task_id)})")

        # 确保task_id是字符串类型
        if task_id is not None:
            task_id = str(task_id)

        # 如果没有任务ID，生成一个新的
        if not task_id:
            import uuid

            task_id = f"generated_task_{uuid.uuid4().hex[:8]}"
            print(f"生成新的任务ID: {task_id}")

        # 同步var模块中的task_id
        try:
            from crawler.var import task_id_var

            task_id_var.set(task_id)
            print(f"同步var模块中的task_id: {task_id}")
        except Exception as e:
            print(f"同步var模块失败: {e}")

        # 创建用户会话（使用任务ID作为基础）
        session = UserSession(task_id).setup_session()

        # 设置任务ID环境变量，确保其他模块可以访问
        os.environ["CRAWLER_TASK_ID"] = task_id  # 使用原始任务ID而不是会话ID
        print(f"设置环境变量 CRAWLER_TASK_ID = {task_id}")

        # 创建配置对象
        Cconfig = CrawlerConfig(
            logintype=logintype,
            platform=platform,
            crawlertype=crawlertype,
            session=session,
        )
        # 创建用户会话
        if not Cconfig.session:
            Cconfig.session = UserSession().setup_session()

        # 设置线程本地会话
        request_local.set_session(Cconfig.session)

        # 为会话创建特定的配置文件
        original_config_path = os.path.join(
            os.path.dirname(__file__), "crawler", "config", "base_config.py"
        )
        session_config_path = create_session_config(
            Cconfig.session, original_config_path, url, task_type
        )

        # 设置环境变量
        os.environ["CRAWLER_TASK_ID"] = Cconfig.session.task_id
        os.environ["CRAWLER_WORK_DIR"] = Cconfig.session.session_dir
        os.environ["CRAWLER_SESSION_CONFIG"] = session_config_path
        os.environ["DATA_STORAGE_PATH"] = f"sessions/{Cconfig.session.task_id}/data"
        os.environ["DATA_DIR"] = f"sessions/{Cconfig.session.task_id}/data"

        print(f"Session ID: {Cconfig.session.task_id}")
        print(f"Work directory: {Cconfig.session.session_dir}")
        print(f"Session config: {session_config_path}")
        print(f"设置环境变量 DATA_STORAGE_PATH = sessions/{Cconfig.session.task_id}/data")
        print(f"设置环境变量 DATA_DIR = sessions/{Cconfig.session.task_id}/data")

        # 如果提供了URL，验证配置是否正确更新
        if url and task_type:
            print(f"Verifying URL configuration for {task_type}")
            try:
                with open(session_config_path, "r", encoding="utf-8") as f:
                    config_content = f.read()
                    print(f"会话配置文件内容预览:")
                    lines = config_content.split("\n")
                    for i, line in enumerate(lines):
                        if "DATA_DIR" in line or "DATA_STORAGE_PATH" in line:
                            print(f"  Line {i+1}: {line}")
                    if (
                        task_type == "zhihu-question"
                        and "ZHIHU_QUESTION_URL" in config_content
                    ):
                        # 提取配置的URL
                        import re

                        match = re.search(
                            r'ZHIHU_QUESTION_URL = "([^"]+)"', config_content
                        )
                        if match:
                            configured_url = match.group(1)
                            print(f"Configured ZHIHU_QUESTION_URL: {configured_url}")
                            if configured_url == url:
                                print("URL configuration verified successfully")
                            else:
                                print(
                                    f"WARNING: URL mismatch. Expected: {url}, Configured: {configured_url}"
                                )
            except Exception as e:
                print(f"Error verifying URL configuration: {e}")

        # 添加crawler目录到Python路径
        project_root = os.path.dirname(os.path.abspath(__file__))
        crawler_path = os.path.join(project_root, "crawler")

        # 添加会话配置目录到Python路径开头，确保优先使用会话配置
        session_config_dir = os.path.join(Cconfig.session.session_dir, "config")
        if session_config_dir not in sys.path:
            sys.path.insert(0, session_config_dir)
            print(f"添加会话配置目录到Python路径: {session_config_dir}")

        if crawler_path not in sys.path:
            sys.path.insert(0, crawler_path)
            print(f"添加crawler目录到Python路径: {crawler_path}")

        # 验证配置
        print("\n验证配置:")
        print(f"当前工作目录: {os.getcwd()}")
        print(f"Python路径前10个: {sys.path[:10]}")  # 显示前10个路径

        # 检查环境变量
        print(f"DATA_STORAGE_PATH环境变量: {os.environ.get('DATA_STORAGE_PATH', '未设置')}")
        print(f"DATA_DIR环境变量: {os.environ.get('DATA_DIR', '未设置')}")
        print(
            f"CRAWLER_SESSION_CONFIG环境变量: {os.environ.get('CRAWLER_SESSION_CONFIG', '未设置')}"
        )

        # 尝试导入配置验证
        try:
            print("尝试导入会话特定配置...")
            # 先尝试导入会话特定配置
            sys.path.insert(0, session_config_dir)
            import importlib

            import crawler.config.base_config as session_config

            print(f"会话配置DATA_DIR: {session_config.DATA_DIR}")
            print(
                f"会话配置DATA_STORAGE_PATH: {getattr(session_config, 'DATA_STORAGE_PATH', '未定义')}"
            )
            importlib.reload(session_config)  # 重新加载确保使用最新配置
        except Exception as e:
            print(f"会话配置导入失败: {e}")

            # 尝试查看会话配置文件内容
            try:
                session_config_file = os.path.join(session_config_dir, "base_config.py")
                if os.path.exists(session_config_file):
                    print(f"会话配置文件存在: {session_config_file}")
                    with open(session_config_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        print("会话配置文件内容 (前20行):")
                        for i, line in enumerate(content.split("\n")[:20]):
                            print(f"  {i+1}: {line}")
                else:
                    print(f"会话配置文件不存在: {session_config_file}")
            except Exception as file_error:
                print(f"读取会话配置文件失败: {file_error}")

        # 检查爬虫模块如何获取数据目录
        print("\n检查爬虫模块数据目录获取方式:")
        try:
            from crawler.media_platform.bilibili.core import BilibiliCrawler

            print(f"BilibiliCrawler应该使用的数据目录: sessions/{Cconfig.session.task_id}/data")
        except Exception as e:
            print(f"无法检查BilibiliCrawler: {e}")

        # 直接导入并运行爬虫
        # 运行爬虫（使用同步方式）
        import asyncio

        from crawler import crawler_main

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            crawler_main.main(Cconfig.logintype, Cconfig.platform, Cconfig.crawlertype)
        )
        loop.close()
        print("Crawler program execution completed")

        # 爬虫执行完成后，立即传输数据
        print("\n" + "=" * 50)
        print("Step 3.5: Transmit crawler data files")
        try:
            transmit_result = transmit_data(Cconfig)
            if transmit_result:
                print(f"Data transmission successful: {transmit_result}")
                # 返回标准格式的结果，包含会话ID和任务ID
                result = {
                    "status": "success",
                    "message": "爬虫运行完成",
                    "result_file": transmit_result["file_path"],
                    "session_id": transmit_result["session_id"],
                    "task_id": task_id,  # 确保返回原始任务ID
                }
                return result
            else:
                print("Data transmission failed")
                return {
                    "status": "failed",
                    "message": "数据传输失败",
                    "task_id": task_id,  # 确保返回原始任务ID
                }
        except Exception as e:
            print(f"Error during data transmission: {e}")
            import traceback

            traceback.print_exc()
            return {
                "status": "error",
                "message": f"数据传输时出错: {str(e)}",
                "task_id": task_id,  # 确保返回原始任务ID
            }

    except Exception as e:
        print(f"Error running crawler: {e}")
        import traceback

        traceback.print_exc()
        return {
            "status": "error",
            "message": f"运行爬虫时出错: {str(e)}",
            "task_id": task_id,  # 确保返回原始任务ID
        }
    finally:
        # 清理环境变量
        env_vars_to_clear = [
            "CRAWLER_TASK_ID",
            "CRAWLER_WORK_DIR",
            "CRAWLER_SESSION_CONFIG",
            "DATA_STORAGE_PATH",
            "DATA_DIR",
        ]
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]


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


# 在main.py文件顶部添加task_file_mapping
task_file_mapping = {}


def transmit_data(config: CrawlerConfig):
    """
    传输爬取的数据文件
    根据平台、日期和任务ID打包对应的JSON文件
    """
    from crawler.var import task_id_var

    platform = config.platform
    today = datetime.now().strftime("%Y-%m-%d")
    task_id = task_id_var.get() or os.environ.get("CRAWLER_TASK_ID")

    print(f"Transmit data - Task ID: {task_id}")

    # 首先尝试使用会话特定的数据目录
    data_dir = None
    if config.session:
        # 尝试会话特定的数据目录
        session_data_dirs = [
            f"{config.session.data_dir}/{platform}/json",
            f"{config.session.data_dir}/{platform}",
            f"{config.session.session_dir}/data/{platform}/json",
            f"{config.session.session_dir}/data/{platform}",
        ]

        for dir_path in session_data_dirs:
            if os.path.exists(dir_path):
                data_dir = dir_path
                print(f"Using session data directory: {data_dir}")
                break

    # 如果没有会话特定目录，尝试全局目录
    if not data_dir:
        global_data_dirs = [f"data/{platform}/json", f"data/{platform}"]

        for dir_path in global_data_dirs:
            if os.path.exists(dir_path):
                data_dir = dir_path
                print(f"Using global data directory: {data_dir}")
                break

    # 如果仍然找不到数据目录
    if not data_dir or not os.path.exists(data_dir):
        logging.error(f"数据目录不存在: {data_dir}")
        # 列出可能的目录帮助调试
        print("Available directories:")
        if os.path.exists("data"):
            try:
                print(f"  data: {os.listdir('data')}")
            except:
                print("  data: (无法列出内容)")
        if config.session and os.path.exists(config.session.session_dir):
            try:
                session_data_path = f"{config.session.session_dir}/data"
                if os.path.exists(session_data_path):
                    print(f"  session data: {os.listdir(session_data_path)}")
            except:
                print("  session data: (无法列出内容)")
        return None

    print(f"Final data directory: {data_dir}")

    # 获取目录中的文件列表
    try:
        if os.path.isdir(data_dir):
            data_dir_contents = os.listdir(data_dir)
            print(f"Files in data directory: {data_dir_contents}")
        else:
            logging.error(f"数据目录不是有效目录: {data_dir}")
            return None
    except Exception as e:
        print(f"Error listing data directory: {e}")
        return None

    # 查找文件（优先查找与当前任务ID匹配的文件）
    target_files = []
    if task_id:
        # 首先查找与当前任务ID精确匹配的文件
        for file in data_dir_contents:
            if (
                file.startswith(f"{config.crawlertype}_")
                and (today in file or task_id in file)
                and file.endswith((".json", ".txt"))
            ):
                file_path = os.path.join(data_dir, file)
                if os.path.isfile(file_path):  # 确保是文件而不是目录
                    target_files.append((file_path, os.path.getmtime(file_path)))
                    print(f"Found task-specific file: {file_path}")

    # 如果没有找到与任务ID匹配的文件，查找今天的文件
    if not target_files:
        print("No task-specific file found, searching for today's files")
        for file in data_dir_contents:
            if (
                (
                    file.startswith(f"{config.crawlertype}_")
                    or config.crawlertype in file
                )
                and (today in file)
                and file.endswith((".json", ".txt"))
            ):
                file_path = os.path.join(data_dir, file)
                if os.path.isfile(file_path):  # 确保是文件而不是目录
                    target_files.append((file_path, os.path.getmtime(file_path)))
                    print(f"Found today's file: {file_path}")

    # 如果仍然没有找到文件，尝试查找任何相关的文件
    if not target_files:
        print("No today's files found, searching for any related files")
        for file in data_dir_contents:
            if (config.crawlertype in file or platform in file) and file.endswith(
                (".json", ".txt")
            ):
                file_path = os.path.join(data_dir, file)
                if os.path.isfile(file_path):  # 确保是文件而不是目录
                    target_files.append((file_path, os.path.getmtime(file_path)))
                    print(f"Found related file: {file_path}")

    if not target_files:
        logging.error(f"未找到相关的数据文件: {data_dir}")
        # 列出目录中的所有文件帮助调试
        try:
            all_files = [
                f
                for f in data_dir_contents
                if os.path.isfile(os.path.join(data_dir, f))
            ]
            print(f"All files in directory: {all_files}")
        except:
            print("无法列出目录中的文件")
        return None

    # 按修改时间排序，获取最新的文件
    target_files.sort(key=lambda x: x[1], reverse=True)
    data_file_path = target_files[0][0]

    print(f"Selected file: {data_file_path}")

    # 使用会话特定的传输目录或默认目录
    transmit_dir = "transmit_data"
    if config.session:
        transmit_dir = config.session.transmit_dir

    print(f"Using transmit directory: {transmit_dir}")

    # 确保传输目录存在
    if not os.path.exists(transmit_dir):
        try:
            os.makedirs(transmit_dir)
            print(f"Created transmit directory: {transmit_dir}")
        except Exception as e:
            logging.error(f"Failed to create transmit directory {transmit_dir}: {e}")
            # 回退到默认传输目录
            transmit_dir = "transmit_data"
            if not os.path.exists(transmit_dir):
                os.makedirs(transmit_dir, exist_ok=True)
            print(f"Fallback to default transmit directory: {transmit_dir}")

    # 构造传输文件名（保留任务ID以确保唯一性）
    filename = os.path.basename(data_file_path)
    # 不再移除任务ID，保持文件名的唯一性
    transmit_file_path = os.path.join(transmit_dir, filename)
    print(f"Transmit file path: {transmit_file_path}")

    try:
        # 复制文件到传输目录
        shutil.copy2(data_file_path, transmit_file_path)
        print(f"Copied file from {data_file_path} to {transmit_file_path}")
        logging.info(f"数据文件已传输到: {transmit_file_path}")

        # 返回传输文件路径和会话ID（如果存在）
        result = {"file_path": transmit_file_path}
        if config.session:
            result["session_id"] = config.session.task_id

        return result
    except Exception as e:
        logging.error(f"传输数据文件时出错: {e}")
        print(f"Error copying file: {e}")
        import traceback

        traceback.print_exc()
        return None


async def main(Cconfig: CrawlerConfig) -> None:
    # 0. 清空之前的数据文件（在爬虫运行前）
    print("\n" + "=" * 50)
    print("Step 0: Clean historical crawler data")
    print("=" * 50)
    clean_crawler_data(Cconfig.session)

    # 1. 执行爬虫
    print("\n" + "=" * 50)
    print("Step 1: Execute crawler program")
    await run_crawler_internal(Cconfig)

    # 2. 执行数据转化
    print("\n" + "=" * 50)
    print("Step 2: Execute data processing program")

    # 查找爬虫生成的文件，将爬虫文件最后生成txt文件
    processed_content = process_crawler_data(Cconfig)

    # 将处理后的内容保存到文件，供后续模型构建使用
    if processed_content:
        # 使用会话特定的处理文件路径
        if Cconfig.session:
            processed_file_path = (
                f"{Cconfig.session.session_dir}/processed_{Cconfig.platform}_data.txt"
            )
        else:
            processed_file_path = f"processed_{Cconfig.platform}_data.txt"

        try:
            with open(processed_file_path, "w", encoding="utf-8") as f:
                f.write(processed_content)
            print(f"Processed data saved to: {processed_file_path}")
        except Exception as e:
            print(f"Error saving processed data: {e}")
    else:
        print("  Warning: No valid data content found")

    # 注意：不再自动执行模型构建，而是等待用户点击"生成模型"按钮
    print("\n" + "=" * 50)
    print("Step 3: Waiting for user to click 'Build Model' button")
    print("Model building is now manual via the web interface")

    # 新增步骤：传输爬虫数据文件
    print("\n" + "=" * 50)
    print("Step 3.5: Transmit crawler data files")
    try:
        transmit_result = transmit_data(Cconfig)
        if transmit_result:
            print(f"Data transmission successful: {transmit_result}")
        else:
            print("Data transmission failed")
    except Exception as e:
        print(f"Error during data transmission: {e}")
        import traceback

        traceback.print_exc()

    # 4. 清空爬虫生成文件（可选）
    print("\n" + "=" * 50)
    print("Step 4: Clean crawler generated files")
    # clean_crawler_data(Cconfig.session)  # 如果需要在最后也清空数据，取消注释这行


def process_crawler_data(Cconfig: CrawlerConfig) -> str:
    """
    处理爬虫生成的数据文件，将数据转换为文本格式
    返回处理后的文本内容
    """
    # 查找爬虫生成的文件
    file_groups = find_crawler_files(Cconfig)
    processed_content = ""

    if Cconfig.platform == "bilibili" and file_groups:
        processed_content = process_bili_data(file_groups)
    elif Cconfig.platform == "zhihu" and file_groups:
        processed_content = process_zhihu_data(file_groups)
    elif Cconfig.platform == "xhs":
        processed_content = process_xhs_data(Cconfig)

    return processed_content.strip()


def create_session_config(session, original_config_path, url=None, task_type=None):
    """
    为会话创建特定的配置文件，修改数据存储路径
    """
    # 创建会话配置目录
    session_config_dir = os.path.join(session.session_dir, "config")
    os.makedirs(session_config_dir, exist_ok=True)

    # 会话特定的配置文件路径
    session_config_path = os.path.join(session_config_dir, "base_config.py")

    # 读取原始配置文件
    with open(original_config_path, "r", encoding="utf-8") as f:
        config_content = f.read()

    # 修改数据存储路径，将数据存储到会话目录中
    import re

    # 替换DATA_STORAGE_PATH定义
    config_content = re.sub(
        r'DATA_STORAGE_PATH = os\.environ\.get\("DATA_STORAGE_PATH", "data"\)',
        f'DATA_STORAGE_PATH = "sessions/{session.task_id}/data"',
        config_content,
    )

    # 替换DATA_DIR定义
    config_content = re.sub(
        r"DATA_DIR = DATA_STORAGE_PATH",
        f'DATA_DIR = "sessions/{session.task_id}/data"',
        config_content,
    )

    # 替换目录创建语句
    config_content = re.sub(
        r"os\.makedirs\(DATA_DIR, exist_ok=True\)",
        f'os.makedirs("sessions/{session.task_id}/data", exist_ok=True)',
        config_content,
    )

    # 根据任务类型更新URL配置
    if url and task_type:
        if task_type == "zhihu-question":
            config_content = re.sub(
                r'ZHIHU_QUESTION_URL = ".*?"',
                f'ZHIHU_QUESTION_URL = "{url}"',
                config_content,
            )
        elif task_type == "bili-video":
            bv_id = extract_bv_id_from_url(url)
            if bv_id:
                # 替换B站视频ID列表
                config_content = re.sub(
                    r"BILI_SPECIFIED_ID_LIST = \[.*?\]",
                    f'BILI_SPECIFIED_ID_LIST = ["{bv_id}"]',
                    config_content,
                    flags=re.DOTALL,
                )
        elif task_type == "xhs-detail":
            # 替换小红书笔记URL列表
            config_content = re.sub(
                r"XHS_SPECIFIED_NOTE_URL_LIST = \[.*?\]",
                f'XHS_SPECIFIED_NOTE_URL_LIST = ["{url}"]',
                config_content,
                flags=re.DOTALL,
            )

    # 将修改后的配置写入会话特定的配置文件
    with open(session_config_path, "w", encoding="utf-8") as f:
        f.write(config_content)

    return session_config_path


def extract_bv_id_from_url(url):
    """
    从B站URL中提取BV号
    """
    import re

    # 匹配BV号的正则表达式
    match = re.search(r"BV[0-9A-Za-z]+", url)
    if match:
        return match.group(0)
    return None


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

    # Cconfig = CrawlerConfig(logintype="qrcode ", platform="xhs", crawlertype="detail")
    Cconfig = CrawlerConfig(
        # logintype="cookie", platform="zhihu", crawlertype="question"
        logintype="cookie",
        platform="bilibili",
        crawlertype="detail",
    )

    try:
        asyncio.run(main(Cconfig))
    except KeyboardInterrupt:
        sys.exit()
