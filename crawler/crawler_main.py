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

import cmd_arg
import config
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


async def run_single_test(login_type: str, platform: str, crawler_type: str):
    """运行单个测试组合"""
    print(
        f"\n=== 测试组合: login_type={login_type}, platform={platform}, crawler_type={crawler_type} ==="
    )

    try:
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

        print(f"✓ 完成: {login_type}-{platform}-{crawler_type}")

    except Exception as e:
        print(f"✗ 错误: {login_type}-{platform}-{crawler_type}, 错误信息: {e}")
        # 确保数据库连接关闭
        if config.SAVE_DATA_OPTION == "db":
            try:
                await db.close()
            except:
                pass


async def test_all_combinations():
    """测试所有组合"""
    # 使用你在 #selectedCode 中定义的列表
    login_type_list = ["cookie"]
    platform_list = ["bili", "zhihu"]
    crawler_type_list = ["search", "detail", "creator", "question", "creator_audio"]

    # 生成所有组合
    combinations = list(
        itertools.product(login_type_list, platform_list, crawler_type_list)
    )

    print(f"总共需要测试 {len(combinations)} 个组合")

    # 逐一测试
    for i, (login_type, platform, crawler_type) in enumerate(combinations, 1):
        print(f"\n[{i}/{len(combinations)}] 开始测试...")
        await run_single_test(login_type, platform, crawler_type)
        # 可选：添加延迟避免请求过于频繁
        # await asyncio.sleep(2)

    print(f"\n=== 所有测试完成 ===")


async def main(
    logintype: str = "cookie", platform: str = "zhihu", crawlertype: str = "question"
):
    # parse cmd
    await cmd_arg.parse_cmd()
    # 如果你只想运行原来的单个测试，可以注释掉上面一行，取消注释下面几行
    config.LOGIN_TYPE = logintype
    config.PLATFORM = platform
    config.CRAWLER_TYPE = crawlertype

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
