import asyncio
import itertools
import os
import sys

# 设置项目根目录和crawler目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
crawler_root = os.path.dirname(os.path.abspath(__file__))

# 将项目根目录和crawler目录添加到sys.path中
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if crawler_root not in sys.path:
    sys.path.insert(0, crawler_root)

# 添加crawler/libs目录到sys.path，确保能访问到zhihu.js
libs_path = os.path.join(crawler_root, "libs")
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

# 在crawler_main中也设置任务ID
try:
    from var import task_id_var
except ImportError:
    # 如果相对导入失败，尝试直接导入
    import var

    task_id_var = var.task_id_var

task_id_from_env = os.environ.get("CRAWLER_TASK_ID")
print(
    f"Task ID from environment: '{task_id_from_env}' (type: {type(task_id_from_env)})"
)
if task_id_from_env and not task_id_var.get():
    task_id_var.set(task_id_from_env)
    print(f"Crawler main set task ID from environment: {task_id_from_env}")
elif task_id_var.get():
    print(f"Crawler main task ID already set: {task_id_var.get()}")
else:
    print("No task ID available in crawler main")
    # 设置默认任务ID
    if not task_id_var.get():
        default_task_id = "default_task_id"
        task_id_var.set(default_task_id)
        print(f"Set default task ID: {default_task_id}")

# 尝试导入配置模块
try:
    import config
except ImportError:
    # 如果直接导入失败，尝试相对导入
    try:
        from . import config
    except ImportError:
        # 最后的备选方案
        config_path = os.path.join(crawler_root, "config")
        if config_path not in sys.path:
            sys.path.insert(0, config_path)
        import base_config as config

import cmd_arg
import db
from base.base_crawler import AbstractCrawler
from media_platform.bilibili import BilibiliCrawler
from media_platform.douyin import DouYinCrawler
from media_platform.kuaishou import KuaishouCrawler
from media_platform.tieba import TieBaCrawler
from media_platform.weibo import WeiboCrawler
from media_platform.xhs import XiaoHongShuCrawler
from media_platform.zhihu import ZhihuCrawler


class CrawlerFactory:
    CRAWLERS = {
        "xhs": XiaoHongShuCrawler,
        "dy": DouYinCrawler,
        "ks": KuaishouCrawler,
        "bili": BilibiliCrawler,
        "wb": WeiboCrawler,
        "tieba": TieBaCrawler,
        "zhihu": ZhihuCrawler,
    }

    @staticmethod
    def create_crawler(platform: str) -> AbstractCrawler:
        crawler_class = CrawlerFactory.CRAWLERS.get(platform)
        if not crawler_class:
            raise ValueError(
                "Invalid Media Platform Currently only supported xhs or dy or ks or bili ..."
            )
        return crawler_class()


async def main(
    login_type: str,
    platform: str,
    crawler_type: str,
):
    """
    爬虫主函数，根据参数运行不同的爬虫实现
    Args:
        login_type: 登类型
        platform: 平台名称
        crawler_type: 爬虫类型

    Returns:
    """

    # 检查是否有会话特定的配置
    session_config_path = os.environ.get("CRAWLER_SESSION_CONFIG")
    if session_config_path and os.path.exists(session_config_path):
        print(f"Using session-specific config: {session_config_path}")
        # 动态替换配置模块
        import importlib.util
        import sys

        # 从会话特定的配置文件加载配置
        spec = importlib.util.spec_from_file_location(
            "session_config", session_config_path
        )
        session_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(session_config)

        # 更新当前配置模块的属性
        import config

        for attr in dir(session_config):
            if not attr.startswith("__"):
                setattr(config, attr, getattr(session_config, attr))
        print(f"Updated config ZHIHU_QUESTION_URL: {config.ZHIHU_QUESTION_URL}")
    else:
        print("Using default config")

    # 确保任务ID已设置
    from var import task_id_var

    task_id_from_env = os.environ.get("CRAWLER_TASK_ID")
    current_task_id = task_id_var.get()
    print(f"Main function - Task ID from environment: '{task_id_from_env}'")
    print(f"Main function - Current task ID in var: '{current_task_id}'")

    if task_id_from_env and not current_task_id:
        task_id_var.set(task_id_from_env)
        print(f"Main function set task ID from environment: {task_id_from_env}")

    print(f"Main function - Final Task ID: {task_id_var.get()}")
    print(f"Main function - Crawler type: {crawler_type}")

    # 设置爬虫类型
    from var import crawler_type_var

    crawler_type_var.set(crawler_type)

    # 设置配置
    config.LOGIN_TYPE = login_type
    config.PLATFORM = platform
    config.CRAWLER_TYPE = crawler_type

    # init db
    if config.SAVE_DATA_OPTION == "db":
        await db.init_db()

    crawler = CrawlerFactory.create_crawler(platform=config.PLATFORM)
    await crawler.start()

    if config.SAVE_DATA_OPTION == "db":
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
        # asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        sys.exit()
