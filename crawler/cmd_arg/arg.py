import argparse

import config
from tools.utils import str2bool


async def parse_cmd():
    # 读取command arg
    parser = argparse.ArgumentParser(description="Media crawler program.")
    parser.add_argument(
        "--platform",
        type=str,
        help="Media platform select (xhs | dy | ks | bili | wb | tieba | zhihu)",  # 爬取平台
        choices=["xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"],
        default=config.PLATFORM,
    )
    parser.add_argument(
        "--lt",
        type=str,
        help="Login type (qrcode | phone | cookie)",  # 登录方式
        choices=["qrcode", "phone", "cookie"],
        default=config.LOGIN_TYPE,
    )
    parser.add_argument(
        "--type",
        type=str,
        help="crawler type (search | detail | creator | question | creator_audio)",  # 爬取类型
        choices=["search", "detail", "creator", "question", "creator_audio"],
        default=config.CRAWLER_TYPE,
    )
    parser.add_argument(
        "--start",
        type=int,  # 爬取起始页
        help="number of start page",
        default=config.START_PAGE,
    )
    parser.add_argument(
        "--keywords",
        type=str,  # 搜索关键词
        nargs="+",
        help="please input keywords",
        default=config.KEYWORDS,
    )
    parser.add_argument(
        "--get_comment",
        type=str2bool,  # 是否爬取一级评论
        help="""whether to crawl level one comment, supported values case insensitive ('yes', 'true', 't', 'y', '1', 'no', 'false', 'f', 'n', '0')""",
        default=config.ENABLE_GET_COMMENTS,
    )
    parser.add_argument(
        "--get_sub_comment",
        type=str2bool,  # 是否爬取二级评论
        help="""'whether to crawl level two comment, supported values case insensitive ('yes', 'true', 't', 'y', '1', 'no', 'false', 'f', 'n', '0')""",
        default=config.ENABLE_GET_SUB_COMMENTS,
    )
    parser.add_argument(
        "--save_data_option",
        type=str,  # 保存数据方式
        help="where to save the data (csv or db or json)",
        choices=["csv", "db", "json"],
        default=config.SAVE_DATA_OPTION,
    )
    parser.add_argument(
        "--cookies",
        type=str,  # 用于Cookie登录的Cookies字符串
        help="cookies used for cookie login type",
        default=config.COOKIES,
    )

    args = parser.parse_args()

    # override config
    config.PLATFORM = args.platform
    config.LOGIN_TYPE = args.lt
    config.CRAWLER_TYPE = args.type
    config.START_PAGE = args.start
    config.KEYWORDS = args.keywords
    config.ENABLE_GET_COMMENTS = args.get_comment
    config.ENABLE_GET_SUB_COMMENTS = args.get_sub_comment
    config.SAVE_DATA_OPTION = args.save_data_option
    config.COOKIES = args.cookies
