# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


# -*- coding: utf-8 -*-
import asyncio
import json
import os
import random
import re
from asyncio import Task
from typing import Dict, List, Optional, Tuple, cast

import config
from base.base_crawler import AbstractCrawler
from constant import zhihu as constant
from model.m_zhihu import ZhihuContent, ZhihuCreator, ZhihuQuestionAnswer
from playwright.async_api import BrowserContext, BrowserType, Page, async_playwright
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import zhihu as zhihu_store
from tools import utils
from var import crawler_type_var, source_keyword_var

from .client import ZhiHuClient
from .exception import DataFetchError
from .help import ZhihuExtractor, judge_zhihu_url
from .login import ZhiHuLogin


class ZhihuCrawler(AbstractCrawler):
    context_page: Page
    zhihu_client: ZhiHuClient
    browser_context: BrowserContext

    def __init__(self) -> None:
        # 检查初始化时的任务ID
        from var import crawler_type_var, task_id_var

        task_id = task_id_var.get()
        crawler_type = crawler_type_var.get()
        print(f"ZhihuCrawler.__init__ - Task ID: {task_id}")
        print(f"ZhihuCrawler.__init__ - Crawler type: {crawler_type}")

        self.index_url = "https://www.zhihu.com"
        # self.user_agent = utils.get_user_agent()
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self._extractor = ZhihuExtractor()

    async def start(self) -> None:
        """
        Start the crawler
        Returns:

        """
        # 检查任务ID和爬虫类型
        from var import crawler_type_var, task_id_var

        task_id = task_id_var.get()
        crawler_type = crawler_type_var.get()
        print(f"ZhihuCrawler start - Task ID: {task_id}")
        print(f"ZhihuCrawler start - Crawler type: {crawler_type}")
        print(f"ZhihuCrawler start - Config crawler type: {config.CRAWLER_TYPE}")

        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            ip_proxy_pool = await create_ip_pool(
                config.IP_PROXY_POOL_COUNT, enable_validate_ip=True
            )
            ip_proxy_info: IpInfoModel = await ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = self.format_proxy_info(
                ip_proxy_info
            )

        async with async_playwright() as playwright:  # 使用async_playwright启动浏览器上下文，并加载指定的用户代理和无头模式设置。
            # Launch a browser context.
            chromium = playwright.chromium
            current_file = os.path.abspath(__file__)
            crawler_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(current_file))
            )
            stealth_path = os.path.join(crawler_dir, "libs", "stealth.min.js")
            self.browser_context = await self.launch_browser(
                chromium, None, self.user_agent, headless=config.HEADLESS
            )
            # stealth.min.js is a js script to prevent the website from detecting the crawler.添加stealth.min.js脚本防止网站检测爬虫。
            # await self.browser_context.add_init_script(path="libs/stealth.min.js")
            await self.browser_context.add_init_script(path=stealth_path)

            self.context_page = await self.browser_context.new_page()
            # await self.context_page.goto(self.index_url, wait_until="domcontentloaded")
            await self.context_page.goto(self.index_url, wait_until="networkidle")
            # 增加额外等待时间确保页面完全加载
            await asyncio.sleep(5)

            # Create a client to interact with the zhihu website.
            self.zhihu_client = await self.create_zhihu_client(httpx_proxy_format)

            utils.logger.info(f"[ZhihuCrawler.start] 当前登录类型: {config.LOGIN_TYPE}")

            # 修改此处：无论是否已登录，只要配置为二维码登录就显示二维码
            try:
                if config.LOGIN_TYPE == "qrcode":
                    utils.logger.info("[ZhihuCrawler.start] 强制执行二维码登录流程")
                    login_obj = ZhiHuLogin(
                        login_type=config.LOGIN_TYPE,
                        login_phone="",  # input your phone number
                        browser_context=self.browser_context,
                        context_page=self.context_page,
                        cookie_str=config.COOKIES,
                    )
                    await login_obj.begin()
                    await self.zhihu_client.update_cookies(
                        browser_context=self.browser_context
                    )
                else:
                    utils.logger.info("[ZhihuCrawler.start] 开始检查登录状态...")
                    login_result = await self.zhihu_client.pong()  # 检测是否登录成功，如果失败，则进行登录
                    utils.logger.info(f"[ZhihuCrawler.start] 登录检查结果: {login_result}")
                    if not login_result:
                        utils.logger.info("[ZhihuCrawler.start] 需要重新登录，将调用登录流程...")
                        login_obj = ZhiHuLogin(
                            login_type=config.LOGIN_TYPE,
                            login_phone="",  # input your phone number
                            browser_context=self.browser_context,
                            context_page=self.context_page,
                            cookie_str=config.COOKIES,
                        )
                        await login_obj.begin()
                        await self.zhihu_client.update_cookies(
                            browser_context=self.browser_context
                        )
                    else:
                        utils.logger.info("[ZhihuCrawler.start] 已经登录，无需重新登录")
            except Exception as e:
                utils.logger.error(f"[ZhihuCrawler.start] 登录阶段出现异常: {e}")
                import traceback

                utils.logger.error(
                    f"[ZhihuCrawler.start] 登录阶段异常追踪: {traceback.format_exc()}"
                )
                raise

            # 知乎的搜索接口需要打开搜索页面之后cookies才能访问API，单独的首页不行
            utils.logger.info(
                f"[ZhihuCrawler.start] Zhihu跳转到搜索页面获取搜索页面的Cookies，该过程需要5秒左右,login_type={config.LOGIN_TYPE}"
            )
            await self.context_page.goto(
                f"{self.index_url}/search?q=python&search_source=Guess&utm_content=search_hot&type=content"
            )
            await asyncio.sleep(5)
            await self.zhihu_client.update_cookies(browser_context=self.browser_context)

            # 确保爬虫类型被正确设置
            if not crawler_type_var.get():
                crawler_type_var.set(config.CRAWLER_TYPE)

            utils.logger.info(f"[ZhihuCrawler.start] 当前配置的爬虫类型: {config.CRAWLER_TYPE}")
            utils.logger.info(
                f"[ZhihuCrawler.start] 当前变量中的爬虫类型: {crawler_type_var.get()}"
            )

            # 执行爬取任务
            try:
                utils.logger.info("[ZhihuCrawler.start] 开始执行爬取任务...")
                if config.CRAWLER_TYPE == "search":
                    # Search for notes and retrieve their comment information.
                    utils.logger.info("[ZhihuCrawler.start] 执行搜索任务")
                    await self.search()
                elif config.CRAWLER_TYPE == "detail":
                    # Get the information and comments of the specified post
                    utils.logger.info("[ZhihuCrawler.start] 执行详情任务")
                    await self.get_specified_notes()
                elif config.CRAWLER_TYPE == "creator":
                    # Get creator's information and their notes and comments
                    utils.logger.info("[ZhihuCrawler.start] 执行创作者任务")
                    await self.get_creators_and_notes()
                elif config.CRAWLER_TYPE == "question" or crawler_type == "question":
                    utils.logger.info("[ZhihuCrawler.start] 执行问题回答任务")
                    await self.get_question_and_notes()
                else:
                    utils.logger.warning(
                        f"[ZhihuCrawler.start] 未知的爬虫类型: {config.CRAWLER_TYPE}，使用默认的search类型"
                    )
                    await self.search()
                utils.logger.info("[ZhihuCrawler.start] 爬取任务执行完成")
            except Exception as e:
                utils.logger.error(f"[ZhihuCrawler.start] 爬取阶段出现异常: {e}")
                import traceback

                utils.logger.error(
                    f"[ZhihuCrawler.start] 爬取阶段异常追踪: {traceback.format_exc()}"
                )
                raise

            utils.logger.info("[ZhihuCrawler.start] Zhihu Crawler finished ...")

    async def search(self) -> None:
        """Search for notes and retrieve their comment information."""
        utils.logger.info("[ZhihuCrawler.search] Begin search zhihu keywords")
        zhihu_limit_count = 20  # zhihu limit page fixed value
        # 如果配置的最大笔记数量小于知乎分页限制值，则调整为分页限制值
        if config.CRAWLER_MAX_NOTES_COUNT < zhihu_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = zhihu_limit_count
        # 获取起始页码
        start_page = config.START_PAGE
        for keyword in config.KEYWORDS.split(","):
            source_keyword_var.set(keyword)
            utils.logger.info(
                f"[ZhihuCrawler.search] Current search keyword: {keyword}"
            )
            page = 1
            while (
                page - start_page + 1
            ) * zhihu_limit_count <= config.CRAWLER_MAX_NOTES_COUNT:
                # 跳过小于起始页码的页面
                if page < start_page:
                    utils.logger.info(f"[ZhihuCrawler.search] Skip page {page}")
                    page += 1
                    continue

                try:
                    # 记录当前搜索的关键词和页码
                    utils.logger.info(
                        f"[ZhihuCrawler.search] search zhihu keyword: {keyword}, page: {page}"
                    )

                    # 调用客户端方法获取指定关键词和页码的内容列表
                    content_list: List[
                        ZhihuContent
                    ] = await self.zhihu_client.get_note_by_keyword(
                        keyword=keyword,
                        page=page,
                    )
                    utils.logger.info(
                        f"[ZhihuCrawler.search] Search contents :{content_list}"
                    )
                    if not content_list:
                        utils.logger.info("No more content!")
                        break

                    page += 1
                    # 将搜索到的内容逐一更新到数据库中
                    for content in content_list:
                        await zhihu_store.update_zhihu_content(content)
                    # 批量获取当前内容列表的评论信息
                    await self.batch_get_content_comments(content_list)
                except DataFetchError:
                    utils.logger.error("[ZhihuCrawler.search] Search content error")
                    return

    async def batch_get_content_comments(self, content_list: List[ZhihuContent]):
        """
        Batch get content comments
        Args:
            content_list:
        Returns:
        """
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info(
                f"[ZhihuCrawler.batch_get_content_comments] Crawling comment mode is not enabled"
            )
            return

        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list: List[Task] = []
        for content_item in content_list:
            task = asyncio.create_task(
                self.get_comments(content_item, semaphore), name=content_item.content_id
            )
            task_list.append(task)
        await asyncio.gather(*task_list)

    async def get_comments(
        self, content_item: ZhihuContent, semaphore: asyncio.Semaphore
    ):
        """
        Get note comments with keyword filtering and quantity limitation
        Args:
            content_item:
            semaphore:

        Returns:

        """
        async with semaphore:
            utils.logger.info(
                f"[ZhihuCrawler.get_comments] Begin get note id comments {content_item.content_id}"
            )
            await self.zhihu_client.get_note_all_comments(
                content=content_item,
                crawl_interval=random.random(),
                callback=zhihu_store.batch_update_zhihu_note_comments,
            )

    async def get_creators_and_notes(self) -> None:
        """
        Get creator's information and their notes and comments
        Returns:

        """
        for user_link in config.ZHIHU_CREATOR_URL_LIST:
            utils.logger.info(
                f"[ZhihuCrawler.get_creators_and_notes] Begin get creator {user_link}"
            )
            user_url_token = user_link.split("/")[-1]
            # get creator detail info from web html content
            createor_info: ZhihuCreator = await self.zhihu_client.get_creator_info(
                url_token=user_url_token
            )
            if not createor_info:
                utils.logger.info(
                    f"[ZhihuCrawler.get_creators_and_notes] Creator {user_url_token} not found"
                )
                continue

            utils.logger.info(
                f"[ZhihuCrawler.get_creators_and_notes] Creator info: {createor_info}"
            )
            await zhihu_store.save_creator(creator=createor_info)

            # 默认只提取回答信息，如果需要文章和视频，把下面的注释打开即可

            # Get all anwser information of the creator
            all_content_list = await self.zhihu_client.get_all_anwser_by_creator(
                creator=createor_info,
                crawl_interval=random.random(),
                callback=zhihu_store.batch_update_zhihu_contents,
            )

            await self.batch_get_content_comments(all_content_list)

    async def get_note_detail(
        self, full_note_url: str, semaphore: asyncio.Semaphore
    ) -> Optional[ZhihuContent]:
        """
        Get note detail
        Args:
            full_note_url: str
            semaphore:

        Returns:

        """
        async with semaphore:
            utils.logger.info(
                f"[ZhihuCrawler.get_specified_notes] Begin get specified note {full_note_url}"
            )
            # judge note type
            note_type: str = judge_zhihu_url(full_note_url)
            if note_type == constant.ANSWER_NAME:
                question_id = full_note_url.split("/")[-3]
                answer_id = full_note_url.split("/")[-1]
                utils.logger.info(
                    f"[ZhihuCrawler.get_specified_notes] Get answer info, question_id: {question_id}, answer_id: {answer_id}"
                )
                return await self.zhihu_client.get_answer_info(question_id, answer_id)

            elif note_type == constant.ARTICLE_NAME:
                article_id = full_note_url.split("/")[-1]
                utils.logger.info(
                    f"[ZhihuCrawler.get_specified_notes] Get article info, article_id: {article_id}"
                )
                return await self.zhihu_client.get_article_info(article_id)

            elif note_type == constant.VIDEO_NAME:
                video_id = full_note_url.split("/")[-1]
                utils.logger.info(
                    f"[ZhihuCrawler.get_specified_notes] Get video info, video_id: {video_id}"
                )
                return await self.zhihu_client.get_video_info(video_id)

    async def get_specified_notes(self):
        """
        Get the information and comments of the specified post
        Returns:

        """
        get_note_detail_task_list = []
        for full_note_url in config.ZHIHU_SPECIFIED_ID_LIST:
            # remove query params
            full_note_url = full_note_url.split("?")[0]
            crawler_task = self.get_note_detail(
                full_note_url=full_note_url,
                semaphore=asyncio.Semaphore(config.MAX_CONCURRENCY_NUM),
            )
            get_note_detail_task_list.append(crawler_task)

        need_get_comment_notes: List[ZhihuContent] = []
        note_details = await asyncio.gather(*get_note_detail_task_list)
        for index, note_detail in enumerate(note_details):
            if not note_detail:
                utils.logger.info(
                    f"[ZhihuCrawler.get_specified_notes] Note {config.ZHIHU_SPECIFIED_ID_LIST[index]} not found"
                )
                continue

            note_detail = cast(ZhihuContent, note_detail)  # only for type check
            need_get_comment_notes.append(note_detail)
            await zhihu_store.update_zhihu_content(note_detail)

        await self.batch_get_content_comments(need_get_comment_notes)

    @staticmethod
    def format_proxy_info(
        ip_proxy_info: IpInfoModel,
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """format proxy info for playwright and httpx"""
        playwright_proxy = {
            "server": f"{ip_proxy_info.protocol}{ip_proxy_info.ip}:{ip_proxy_info.port}",
            "username": ip_proxy_info.user,
            "password": ip_proxy_info.password,
        }
        httpx_proxy = {
            f"{ip_proxy_info.protocol}": f"http://{ip_proxy_info.user}:{ip_proxy_info.password}@{ip_proxy_info.ip}:{ip_proxy_info.port}"
        }
        return playwright_proxy, httpx_proxy

    async def create_zhihu_client(self, httpx_proxy: Optional[str]) -> ZhiHuClient:
        """Create zhihu client"""
        utils.logger.info(
            "[ZhihuCrawler.create_zhihu_client] Begin create zhihu API client ..."
        )
        cookie_str, cookie_dict = utils.convert_cookies(
            await self.browser_context.cookies()
        )
        zhihu_client_obj = ZhiHuClient(
            proxies=httpx_proxy,
            headers={
                "accept": "*/*",
                "accept-language": "zh-CN,zh;q=0.9",
                "cookie": cookie_str,
                "priority": "u=1, i",
                "referer": "https://www.zhihu.com/search?q=python&time_interval=a_year&type=content",
                "user-agent": self.user_agent,
                "x-api-version": "3.0.91",
                "x-app-za": "OS=Web",
                "x-requested-with": "fetch",
                "x-zse-93": "101_3_3.0",
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
        )
        return zhihu_client_obj

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """Launch browser and create browser context"""
        utils.logger.info(
            "[ZhihuCrawler.launch_browser] Begin create browser context ..."
        )
        if config.SAVE_LOGIN_STATE:
            # feat issue #14
            # we will save login state to avoid login every time
            user_data_dir = os.path.join(
                os.getcwd(), "browser_data", config.USER_DATA_DIR % config.PLATFORM
            )  # type: ignore
            browser_context = await chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                accept_downloads=True,
                headless=headless,
                proxy=playwright_proxy,  # type: ignore
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
            )
            return browser_context
        else:
            browser = await chromium.launch(headless=headless, proxy=playwright_proxy)  # type: ignore
            browser_context = await browser.new_context(
                viewport={"width": 1920, "height": 1080}, user_agent=user_agent
            )
            return browser_context

    async def close(self):
        """Close browser context"""
        await self.browser_context.close()
        utils.logger.info("[ZhihuCrawler.close] Browser context closed ...")

    def calculate_median(self, numbers):
        """
        计算中位数
        Args:
            numbers: 数字列表

        Returns:
            中位数
        """
        if not numbers:
            return 0

        sorted_numbers = sorted(numbers)
        n = len(sorted_numbers)
        if n % 2 == 0:
            # 偶数个元素，取中间两个数的平均值
            return (sorted_numbers[n // 2 - 1] + sorted_numbers[n // 2]) // 2
        else:
            # 奇数个元素，取中间的数
            return sorted_numbers[n // 2]

    async def adaptive_delay(self, base_delay=1.0):
        """
        自适应延时
        Args:
            base_delay: 基础延时秒数
        """
        # 添加一些随机性避免被检测
        delay = base_delay + random.uniform(0.5, 2.0)
        utils.logger.debug(
            f"[ZhihuCrawler.adaptive_delay] Waiting for {delay:.2f} seconds"
        )
        await asyncio.sleep(delay)

    async def get_question_and_notes(self) -> None:
        """
        获取知乎问题和回答
        """
        utils.logger.info("[ZhihuCrawler.get_question_and_notes] 开始执行问题回答爬取任务")

        # 获取问题URL和ID
        if not config.ZHIHU_QUESTION_URL:
            utils.logger.error(
                "[ZhihuCrawler.get_question_and_notes] ZHIHU_QUESTION_URL is not set in config"
            )
            return

        question_url = config.ZHIHU_QUESTION_URL
        question_id = question_url.split("/")[-1]
        if not question_id:
            utils.logger.error(
                "[ZhihuCrawler.get_question_and_notes] Failed to parse question ID from URL"
            )
            return

        utils.logger.info(
            f"[ZhihuCrawler.get_question_and_notes] 解析到问题ID: {question_id}"
        )

        # 收集回答
        question_answers = []
        offset = 0
        limit = 20  # 知乎API最大限制
        total_collected = 0

        # 用于统计前20条回答的点赞数
        initial_voteup_counts = []
        has_collected_initial = False
        min_voteup_threshold = 0

        utils.logger.info("[ZhihuCrawler.get_question_and_notes] 开始爬取回答...")

        while total_collected < 200:  # 最多收集200条回答
            # 根据策略调整limit
            current_limit = 20 if not has_collected_initial else 20

            try:
                answers = await self.zhihu_client.get_question_answers(
                    question_id, offset=offset, limit=current_limit
                )
            except Exception as e:
                utils.logger.error(
                    f"[ZhihuCrawler.get_question_and_notes] 获取回答数据时出错: {e}"
                )
                break

            # 添加自适应延时
            await self.adaptive_delay(base_delay=1.0)

            if not answers:
                utils.logger.info(
                    f"[ZhihuCrawler.get_question_and_notes] No more answers found for question ID: {question_id}"
                )
                break

            answer_data_list = answers.get("data", [])
            if not answer_data_list:
                utils.logger.info(
                    "[ZhihuCrawler.get_question_and_notes] No answer data in response"
                )
                break

            # 处理回答数据
            for answer in answer_data_list:
                # 检查是否已达到200条限制
                if total_collected >= 200:
                    utils.logger.info(
                        "[ZhihuCrawler.get_question_and_notes] 已达到200条回答限制，停止爬取"
                    )
                    break

                answer_id = answer.get("id")
                if not answer_id:
                    continue

                voteup_count = answer.get("voteup_count", 0)

                # 收集前20条的点赞数
                if not has_collected_initial and len(initial_voteup_counts) < 20:
                    initial_voteup_counts.append(voteup_count)

                    # 当收集满20条后，计算中位数并设置阈值
                    if len(initial_voteup_counts) == 20:
                        median_voteup = self.calculate_median(initial_voteup_counts)
                        min_voteup_threshold = median_voteup // 2  # 设置阈值为中位数的一半
                        has_collected_initial = True
                        utils.logger.info(
                            f"[ZhihuCrawler.get_question_and_notes] Collected initial 20 answers. "
                            f"Median voteup count: {median_voteup}, Setting threshold: {min_voteup_threshold}"
                        )

                # 如果未达到阈值，跳过该回答
                if has_collected_initial and voteup_count < min_voteup_threshold:
                    utils.logger.debug(
                        f"[ZhihuCrawler.get_question_and_notes] Skipping answer {answer_id} "
                        f"with voteup count {voteup_count} < threshold {min_voteup_threshold}"
                    )
                    continue

                # 获取回答详情
                try:
                    answer_info = await self.zhihu_client.get_answer_info(
                        question_id, answer_id
                    )
                except Exception as e:
                    utils.logger.error(
                        f"[ZhihuCrawler.get_question_and_notes] 获取回答 {answer_id} 详细信息时出错: {e}"
                    )
                    continue

                if not answer_info:
                    continue

                try:
                    answer_dict = (
                        self.zhihu_client._extractor.extract_question_answer_fields(
                            answer
                        )
                    )
                    answer_dict["source_keyword"] = source_keyword_var.get() or ""
                    question_answer = ZhihuQuestionAnswer(**answer_dict)
                    question_answers.append(question_answer)
                    total_collected += 1
                    utils.logger.info(
                        f"[ZhihuCrawler.get_question_and_notes] 成功处理回答 {answer_id}"
                    )
                except Exception as e:
                    utils.logger.error(
                        f"[ZhihuCrawler.get_question_and_notes] 处理回答 {answer_id} 时出错: {e}"
                    )

            # 检查是否已达到200条限制
            if total_collected >= 300:
                utils.logger.info(
                    "[ZhihuCrawler.get_question_and_notes] 已达到200条回答限制，停止爬取"
                )
                break

            # 检查是否还有更多数据
            paging = answers.get("paging", {})
            if paging.get("is_end", True):
                utils.logger.info(
                    "[ZhihuCrawler.get_question_and_notes] Reached end of answers"
                )
                break

            # 更新offset
            offset += current_limit

            # 在批次之间添加较长的延时
            await self.adaptive_delay(base_delay=2.0)

        utils.logger.info(
            f"[ZhihuCrawler.get_question_and_notes] Total collected answers: {len(question_answers)}"
        )

        # 存储回答数据
        if question_answers:
            try:
                utils.logger.info("[ZhihuCrawler.get_question_and_notes] 开始存储回答数据")
                await zhihu_store.batch_update_zhihu_question_answers(question_answers)
                utils.logger.info("[ZhihuCrawler.get_question_and_notes] 成功存储回答数据")
            except Exception as e:
                utils.logger.error(
                    f"[ZhihuCrawler.get_question_and_notes] 存储回答数据时出错: {e}"
                )
                raise
        else:
            utils.logger.info("[ZhihuCrawler.get_question_and_notes] 没有收集到任何回答数据")
