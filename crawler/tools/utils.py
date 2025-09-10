import argparse
import logging
import os

from .crawler_util import *
from .slider_util import *
from .time_util import *


def get_project_root():
    """获取项目根目录（CrawlerAI 目录）"""
    # 获取当前文件的绝对路径（utils.py 位于 crawler/tools/）
    current_file = os.path.abspath(__file__)
    # 向上回溯两级：tools → crawler → CrawlerAI
    return os.path.dirname(os.path.dirname(os.path.dirname(current_file)))


def get_crawler_root():
    """获取爬虫项目根目录（crawler 目录）"""
    current_file = os.path.abspath(__file__)
    # 向上回溯一级：tools → crawler
    return os.path.dirname(os.path.dirname(current_file))


def get_resource_path(relative_path):
    """获取资源文件的绝对路径"""
    # 自动判断相对路径类型
    if relative_path.startswith("crawler/"):
        base_dir = get_crawler_root()  # 获取 crawler 目录
        return os.path.join(base_dir, relative_path[8:])  # 去掉 "crawler/" 前缀
    else:
        return os.path.join(get_project_root(), relative_path)  # 从项目根目录开始


def validate_file_path(file_path):
    """验证文件是否存在，不存在则记录错误"""
    if not os.path.exists(file_path):
        logging.error(f"文件不存在: {file_path}")
        return False
    return True


# 保留原有的 logger 和其他工具函数
logger = logging.getLogger("utils")


def init_loging_config():
    level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s (%(filename)s:%(lineno)d) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _logger = logging.getLogger("MediaCrawler")
    _logger.setLevel(level)
    return _logger


logger = init_loging_config()


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")
