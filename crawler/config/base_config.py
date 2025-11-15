import os

DATA_STORAGE_PATH = os.environ.get("DATA_STORAGE_PATH", "data")
DATA_DIR = DATA_STORAGE_PATH

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)

PLATFORM = "zhihu"
KEYWORDS = "特斯拉"  # 关键词搜索配置，以英文逗号分隔
ZHIHU_QUESTION_URL = "https://www.zhihu.com/question/597875487"  # 替换为实际的问题URL
LOGIN_TYPE = "qrcode"  # qrcode or phone or cookie
COOKIES = ""
# 具体值参见media_platform.xxx.field下的枚举值，暂时只支持小红书
SORT_TYPE = "popularity_descending"
PUBLISH_TIME_TYPE = 0
CRAWLER_TYPE = "search"  # 爬取类型，search(关键词搜索) | detail(帖子详情)| creator(创作者主页数据)
# 自定义User Agent（暂时仅对XHS有效）
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"

# 是否开启 IP 代理
ENABLE_IP_PROXY = False
# ENABLE_IP_PROXY = True

# 未启用代理时的最大爬取间隔，单位秒（暂时仅对XHS有效）
CRAWLER_MAX_SLEEP_SEC = 4

# 代理IP池数量
IP_PROXY_POOL_COUNT = 2

# 代理IP提供商名称
# IP_PROXY_PROVIDER_NAME = "kuaidaili"
IP_PROXY_PROVIDER_NAME = None

# 设置为True不会打开浏览器（无头浏览器）
# 设置False会打开一个浏览器
# 小红书如果一直扫码登录不通过，打开浏览器手动过一下滑动验证码
# 抖音如果一直提示失败，打开浏览器看下是否扫码登录之后出现了手机号验证，如果出现了手动过一下再试。
HEADLESS = True

# 是否保存登录状态
SAVE_LOGIN_STATE = True

# 数据保存类型选项配置,支持三种类型：csv、db、json, 最好保存到DB，有排重的功能。
SAVE_DATA_OPTION = "json"  # csv or db or json

# 用户浏览器缓存的浏览器文件配置
USER_DATA_DIR = "%s_user_data_dir"  # %s will be replaced by platform name

# 爬取开始页数 默认从第一页开始
START_PAGE = 1

# 爬取视频/帖子的数量控制
CRAWLER_MAX_NOTES_COUNT = 15

# 并发爬虫数量控制
MAX_CONCURRENCY_NUM = 1

# 是否开启爬图片模式, 默认不开启爬图片
ENABLE_GET_AUDIO = True  # 启用音频下载
ENABLE_GET_IMAGES = True  # 禁用视频下载

# 是否开启爬评论模式, 默认开启爬评论
ENABLE_GET_COMMENTS = True

# 爬取一级评论的数量控制(单视频/帖子)
CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = 999

# 是否开启爬二级评论模式, 默认不开启爬二级评论
# 老版本项目使用了 db, 则需参考 schema/tables.sql line 287 增加表字段
ENABLE_GET_SUB_COMMENTS = False

# 已废弃⚠️⚠️⚠️指定小红书需要爬虫的笔记ID列表
# 已废弃⚠️⚠️⚠️ 指定笔记ID笔记列表会因为缺少xsec_token和xsec_source参数导致爬取失败
# XHS_SPECIFIED_ID_LIST = [
#     "66fad51c000000001b0224b8",
#     # ........................
# ]

# 指定小红书需要爬虫的笔记URL列表, 目前要携带xsec_token和xsec_source参数
XHS_SPECIFIED_NOTE_URL_LIST = [
    "https://www.xiaohongshu.com/explore/63eae198000000000800f19d?xsec_token=ABPtpE4YHbO9NzGZVUAyIIIo0xsJVRggpPh9lgG4fjH6c=&xsec_source=pc_feed"
]

# 指定抖音需要爬取的ID列表
DY_SPECIFIED_ID_LIST = [
    "7280854932641664319",
    "7202432992642387233",
    # ........................
]

# 指定快手平台需要爬取的ID列表
KS_SPECIFIED_ID_LIST = ["3xf8enb8dbj6uig", "3x6zz972bchmvqe"]

# 指定B站平台需要爬取的视频bvid列表
BILI_SPECIFIED_ID_LIST = ["BV1Zr4y1D7cf"]

TIEBA_SPECIFIED_ID_LIST = []

# 指定贴吧创作者URL列表
TIEBA_CREATOR_URL_LIST = [
    "https://tieba.baidu.com/home/main/?id=tb.1.7f139e2e.6CyEwxu3VJruH_-QqpCi6g&fr=frs",
    # ........................
]

# 指定小红书创作者ID列表
XHS_CREATOR_ID_LIST = [
    "63e36c9a000000002703502b",
    # ........................
]

# 指定Dy创作者ID列表(sec_id)
DY_CREATOR_ID_LIST = [
    "MS4wLjABAAAATJPY7LAlaa5X-c8uNdWkvz0jUGgpw4eeXIwu_8BhvqE",
    # ........................
]

# 指定bili创作者ID列表(sec_id)
BILI_CREATOR_ID_LIST = [
    # "20813884",
    "3546573373966625",
    # ........................
]

# 指定快手创作者ID列表
KS_CREATOR_ID_LIST = [
    "3x4sm73aye7jq7i",
    # ........................
]


# 指定知乎创作者主页url列表
ZHIHU_CREATOR_URL_LIST = [
    "https://www.zhihu.com/people/yd1234567",
    # ........................
]

# 指定知乎需要爬取的帖子ID列表
ZHIHU_SPECIFIED_ID_LIST = [
    "https://www.zhihu.com/question/597875487",  # 回答
    # "https://zhuanlan.zhihu.com/p/673461588", # 文章
    # "https://www.zhihu.com/zvideo/1539542068422144000" # 视频
]

# 词云相关
# 是否开启生成评论词云图
ENABLE_GET_WORDCLOUD = False
# 自定义词语及其分组
# 添加规则：xx:yy 其中xx为自定义添加的词组，yy为将xx该词组分到的组名。
CUSTOM_WORDS = {
    "零几": "年份",  # 将“零几”识别为一个整体
    "高频词": "专业术语",  # 示例自定义词
}

# 停用(禁用)词文件路径
STOP_WORDS_FILE = "./docs/hit_stopwords.txt"

# 中文字体文件路径
FONT_PATH = "./docs/STZHONGS.TTF"

# 爬取开始的天数，仅支持 bilibili 关键字搜索，YYYY-MM-DD 格式，若为 None 则表示不设置时间范围，按照默认关键字最多返回 1000 条视频的结果处理
START_DAY = "2024-01-01"

# 爬取结束的天数，仅支持 bilibili 关键字搜索，YYYY-MM-DD 格式，若为 None 则表示不设置时间范围，按照默认关键字最多返回 1000 条视频的结果处理
END_DAY = "2024-01-01"

# 是否开启按每一天进行爬取的选项，仅支持 bilibili 关键字搜索
# 若为 False，则忽略 START_DAY 与 END_DAY 设置的值
# 若为 True，则按照 START_DAY 至 END_DAY 按照每一天进行筛选，这样能够突破 1000 条视频的限制，最大程度爬取该关键词下的所有视频
ALL_DAY = False

# 音频下载配置
AUDIO_CUTOFF_DATE = None  # 截止日期，例如 datetime(2023, 1, 1)
MIN_VIEW_COUNT = 1  # 最小观看量
MIN_LIKE_COUNT = 1  # 最小点赞量

# 音频存储路径
AUDIO_STORE_DIR = "data/audios"

# 多用户支持配置
# import os

WORK_DIR = os.getenv("CRAWLER_WORK_DIR", ".")
# DATA_DIR = f"{WORK_DIR}/data" if WORK_DIR != "." else "data"
TRANSMIT_DIR = f"{WORK_DIR}/transmit_data" if WORK_DIR != "." else "transmit_data"
