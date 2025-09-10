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
import re
from html import unescape
from time import sleep
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlencode

import config
import httpx
from base.base_crawler import AbstractApiClient
from constant import zhihu as zhihu_constant
from httpx import Response
from model.m_zhihu import ZhihuComment, ZhihuContent, ZhihuCreator
from playwright.async_api import BrowserContext, Page
from tenacity import retry, stop_after_attempt, wait_fixed
from tools import utils

from .exception import DataFetchError, ForbiddenError
from .field import SearchSort, SearchTime, SearchType
from .help import ZhihuExtractor, sign


class ZhiHuClient(AbstractApiClient):
    def __init__(
        self,
        timeout=10,
        proxies=None,
        *,
        headers: Dict[str, str],
        playwright_page: Page,
        cookie_dict: Dict[str, str],
    ):
        self.proxies = proxies
        self.timeout = timeout
        self.default_headers = headers
        self.cookie_dict = cookie_dict
        self._extractor = ZhihuExtractor()

        self.playwright_page = playwright_page

    async def _pre_headers(self, url: str) -> Dict:
        """
        请求头参数签名
        Args:
            url:  请求的URL需要包含请求的参数
        Returns:

        """
        d_c0 = self.cookie_dict.get("d_c0")
        if not d_c0:
            raise Exception("d_c0 not found in cookies")
        sign_res = sign(url, self.default_headers["cookie"])
        headers = self.default_headers.copy()
        headers["x-zst-81"] = sign_res["x-zst-81"]
        headers["x-zse-96"] = sign_res["x-zse-96"]
        return headers

    # @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    # async def request(self, method, url, **kwargs) -> Union[str, Any]:
    #     """
    #     封装httpx的公共请求方法，对请求响应做一些处理
    #     Args:
    #         method: 请求方法
    #         url: 请求的URL
    #         **kwargs: 其他请求参数，例如请求头、请求体等

    #     Returns:

    #     """
    #     # return response.text
    #     return_response = kwargs.pop('return_response', False)

    #     async with httpx.AsyncClient(proxies=self.proxies, ) as client:
    #         response = await client.request(
    #             method, url, timeout=self.timeout,
    #             **kwargs
    #         )

    #     if response.status_code != 200:
    #         utils.logger.error(f"[ZhiHuClient.request] Requset Url: {url}, Request error: {response.text}")
    #         if response.status_code == 403:
    #             raise ForbiddenError(response.text)
    #         elif response.status_code == 404: # 如果一个content没有评论也是404
    #             return {}

    #         raise DataFetchError(response.text)

    #     if return_response:
    #         return response.text
    #     try:
    #         data: Dict = response.json()
    #         if data.get("error"):
    #             utils.logger.error(f"[ZhiHuClient.request] Request error: {data}")
    #             raise DataFetchError(data.get("error", {}).get("message"))
    #         return data
    #     except json.JSONDecodeError:
    #         utils.logger.error(f"[ZhiHuClient.request] Request error: {response.text}")
    #         raise DataFetchError(response.text)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def request(self, method, url, **kwargs) -> Union[str, Any]:
        """
        封装httpx的公共请求方法，对请求响应做一些处理
        Args:
            method: 请求方法
            url: 请求的URL
            **kwargs: 其他请求参数，例如请求头、请求体等

        Returns:

        """
        return_response = kwargs.pop("return_response", False)
        # +++ 兼容新旧版本代理设置 +++
        client_args = {}
        if self.proxies:
            # 新版 httpx (>=0.24.0) 使用 transport 参数
            if hasattr(httpx, "AsyncHTTPTransport"):
                client_args["transport"] = httpx.AsyncHTTPTransport(proxy=self.proxies)
            # 旧版 httpx (<0.24.0) 使用 proxies 参数
            else:
                client_args["proxies"] = self.proxies

        # +++ 添加调试信息 +++
        utils.logger.debug(f"[ZhiHuClient.request] 使用代理设置: {client_args}")

        async with httpx.AsyncClient(**client_args) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

            # +++ 新增响应日志 +++
            status = response.status_code
            content_type = response.headers.get("content-type", "")
            content_length = response.headers.get("content-length", "0")

            utils.logger.debug(
                f"[ZhiHuClient.request] 响应状态: {status}, "
                f"类型: {content_type}, "
                f"大小: {content_length}字节"
            )

        if response.status_code != 200:
            utils.logger.error(
                f"[ZhiHuClient.request] 请求URL: {url}, 错误: {response.text}"
            )
            if response.status_code == 403:
                raise ForbiddenError(response.text)
            elif response.status_code == 404:  # 如果一个content没有评论也是404
                return {}

            raise DataFetchError(response.text)

        if return_response:
            return response.text
        try:
            data: Dict = response.json()
            if data.get("error"):
                utils.logger.error(f"[ZhiHuClient.request] 请求错误: {data}")
                raise DataFetchError(data.get("error", {}).get("message"))
            return data
        except json.JSONDecodeError:
            utils.logger.error(f"[ZhiHuClient.request] JSON解析错误: {response.text}")
            raise DataFetchError(response.text)

    # async def get(self, uri: str, params=None, **kwargs) -> Union[Response, Dict, str]:
    #     """
    #     GET请求，对请求头签名
    #     Args:
    #         uri: 请求路由
    #         params: 请求参数

    #     Returns:

    #     """
    #     final_uri = uri
    #     if isinstance(params, dict):
    #         final_uri += '?' + urlencode(params)
    #     headers = await self._pre_headers(final_uri)
    #     base_url = (
    #         zhihu_constant.ZHIHU_URL
    #         if "/p/" not in uri
    #         else zhihu_constant.ZHIHU_ZHUANLAN_URL
    #     )
    #     return await self.request(method="GET", url=base_url + final_uri, headers=headers, **kwargs)

    async def get(self, uri: str, params=None, **kwargs) -> Union[Response, Dict, str]:
        """
        GET请求，对请求头签名
        Args:
            uri: 请求路由
            params: 请求参数

        Returns:

        """
        final_uri = uri
        if isinstance(params, dict):
            final_uri += "?" + urlencode(params)
        headers = await self._pre_headers(final_uri)
        base_url = (
            zhihu_constant.ZHIHU_URL
            if "/p/" not in uri
            else zhihu_constant.ZHIHU_ZHUANLAN_URL
        )
        url = base_url + final_uri

        # 调用请求方法
        response = await self.request(method="GET", url=url, headers=headers, **kwargs)

        # +++ 新增响应日志 +++
        if isinstance(response, str):
            # HTML响应内容
            preview = response[:500] + "..." if len(response) > 500 else response

            # 检查反爬提示
            if "验证码" in response:
                utils.logger.warning("[ZhiHuClient.get] 检测到反爬验证码页面")
            elif "<!DOCTYPE html>" in response:
                utils.logger.warning("[ZhiHuClient.get] 收到HTML页面而非API响应")

        elif isinstance(response, dict):
            # JSON响应内容
            utils.logger.debug(f"[ZhiHuClient.get] JSON响应预览: {str(response)[:500]}...")
        else:
            utils.logger.debug(f"[ZhiHuClient.get] 未知响应类型: {type(response)}")

        return response

    async def pong(self) -> bool:
        """
        用于检查登录态是否失效了
        Returns:

        """
        utils.logger.info("[ZhiHuClient.pong] Begin to pong zhihu...")
        ping_flag = False
        try:
            res = await self.get_current_user_info()
            if res.get("uid") and res.get("name"):
                ping_flag = True
                utils.logger.info("[ZhiHuClient.pong] Ping zhihu successfully")
            else:
                utils.logger.error(
                    f"[ZhiHuClient.pong] Ping zhihu failed, response data: {res}"
                )
        except Exception as e:
            utils.logger.error(
                f"[ZhiHuClient.pong] Ping zhihu failed: {e}, and try to login again..."
            )
            ping_flag = False
        return ping_flag

    async def update_cookies(self, browser_context: BrowserContext):
        """
        API客户端提供的更新cookies方法，一般情况下登录成功后会调用此方法
        Args:
            browser_context: 浏览器上下文对象

        Returns:

        """
        cookie_str, cookie_dict = utils.convert_cookies(await browser_context.cookies())
        self.default_headers["cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def get_current_user_info(self) -> Dict:
        """
        获取当前登录用户信息
        Returns:

        """
        params = {"include": "email,is_active,is_bind_phone"}
        return await self.get("/api/v4/me", params)

    async def get_note_by_keyword(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        sort: SearchSort = SearchSort.DEFAULT,
        note_type: SearchType = SearchType.DEFAULT,
        search_time: SearchTime = SearchTime.DEFAULT,
    ) -> List[ZhihuContent]:
        """
        根据关键词搜索
        Args:
            keyword: 关键词
            page: 第几页
            page_size: 分页size
            sort: 排序
            note_type: 搜索结果类型
            search_time: 搜索多久时间的结果

        Returns:

        """
        uri = "/api/v4/search_v3"
        params = {
            "gk_version": "gz-gaokao",
            "t": "general",
            "q": keyword,
            "correction": 1,
            "offset": (page - 1) * page_size,
            "limit": page_size,
            "filter_fields": "",
            "lc_idx": (page - 1) * page_size,
            "show_all_topics": 0,
            "search_source": "Filter",
            "time_interval": search_time.value,
            "sort": sort.value,
            "vertical": note_type.value,
        }
        search_res = await self.get(uri, params)
        utils.logger.info(
            f"[ZhiHuClient.get_note_by_keyword] Search result: {search_res}"
        )
        return self._extractor.extract_contents_from_search(search_res)

    async def get_root_comments(
        self,
        content_id: str,
        content_type: str,
        offset: str = "",
        limit: int = 10,
        order_by: str = "score",
    ) -> Dict:
        """
        获取内容的一级评论
        Args:
            content_id: 内容ID
            content_type: 内容类型(answer, article, zvideo)
            offset:
            limit:
            order_by:

        Returns:

        """
        uri = f"/api/v4/comment_v5/{content_type}s/{content_id}/root_comment"
        params = {"order": order_by, "offset": offset, "limit": limit}
        return await self.get(uri, params)
        # uri = f"/api/v4/{content_type}s/{content_id}/root_comments"
        # params = {
        #     "order": order_by,
        #     "offset": offset,
        #     "limit": limit
        # }
        # return await self.get(uri, params)

    async def get_child_comments(
        self,
        root_comment_id: str,
        offset: str = "",
        limit: int = 10,
        order_by: str = "sort",
    ) -> Dict:
        """
        获取一级评论下的子评论
        Args:
            root_comment_id:
            offset:
            limit:
            order_by:

        Returns:

        """
        uri = f"/api/v4/comment_v5/comment/{root_comment_id}/child_comment"
        params = {"order": order_by, "offset": offset, "limit": limit}
        return await self.get(uri, params)

    async def get_note_all_comments(
        self,
        content: ZhihuContent,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[ZhihuComment]:
        """
        获取指定帖子下的所有一级评论，该方法会一直查找一个帖子下的所有评论信息
        Args:
            content: 内容详情对象(问题｜文章｜视频)
            crawl_interval: 爬取一次笔记的延迟单位（秒）
            callback: 一次笔记爬取结束后

        Returns:

        """
        result: List[ZhihuComment] = []
        is_end: bool = False
        offset: str = ""
        limit: int = 10
        while not is_end:
            root_comment_res = await self.get_root_comments(
                content.content_id, content.content_type, offset, limit
            )
            if not root_comment_res:
                break
            paging_info = root_comment_res.get("paging", {})
            is_end = paging_info.get("is_end")
            offset = self._extractor.extract_offset(paging_info)
            comments = self._extractor.extract_comments(
                content, root_comment_res.get("data")
            )

            if not comments:
                break

            if callback:
                await callback(comments)

            result.extend(comments)
            await self.get_comments_all_sub_comments(
                content, comments, crawl_interval=crawl_interval, callback=callback
            )
            await asyncio.sleep(crawl_interval)
        return result

    async def get_comments_all_sub_comments(
        self,
        content: ZhihuContent,
        comments: List[ZhihuComment],
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[ZhihuComment]:
        """
        获取指定评论下的所有子评论
        Args:
            content: 内容详情对象(问题｜文章｜视频)
            comments: 评论列表
            crawl_interval: 爬取一次笔记的延迟单位（秒）
            callback: 一次笔记爬取结束后

        Returns:

        """
        if not config.ENABLE_GET_SUB_COMMENTS:
            return []

        all_sub_comments: List[ZhihuComment] = []
        for parment_comment in comments:
            if parment_comment.sub_comment_count == 0:
                continue

            is_end: bool = False
            offset: str = ""
            limit: int = 10
            while not is_end:
                child_comment_res = await self.get_child_comments(
                    parment_comment.comment_id, offset, limit
                )
                if not child_comment_res:
                    break
                paging_info = child_comment_res.get("paging", {})
                is_end = paging_info.get("is_end")
                offset = self._extractor.extract_offset(paging_info)
                sub_comments = self._extractor.extract_comments(
                    content, child_comment_res.get("data")
                )

                if not sub_comments:
                    break

                if callback:
                    await callback(sub_comments)

                all_sub_comments.extend(sub_comments)
                await asyncio.sleep(crawl_interval)
        return all_sub_comments

    async def get_creator_info(self, url_token: str) -> Optional[ZhihuCreator]:
        """
        获取创作者信息
        Args:
            url_token:

        Returns:

        """
        uri = f"/people/{url_token}"
        html_content: str = await self.get(uri, return_response=True)
        return self._extractor.extract_creator(url_token, html_content)

    async def get_creator_answers(
        self, url_token: str, offset: int = 0, limit: int = 20
    ) -> Dict:
        """
        获取创作者的回答
        Args:
            url_token:
            offset:
            limit:

        Returns:


        """
        uri = f"/api/v4/members/{url_token}/answers"
        params = {
            "include": "data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,excerpt,paid_info,reaction_instruction,is_labeled,label_info,relationship.is_authorized,voting,is_author,is_thanked,is_nothelp;data[*].vessay_info;data[*].author.badge[?(type=best_answerer)].topics;data[*].author.vip_info;data[*].question.has_publishing_draft,relationship",
            "offset": offset,
            "limit": limit,
            "order_by": "created",
        }
        return await self.get(uri, params)

    async def get_creator_articles(
        self, url_token: str, offset: int = 0, limit: int = 20
    ) -> Dict:
        """
        获取创作者的文章
        Args:
            url_token:
            offset:
            limit:

        Returns:

        """
        uri = f"/api/v4/members/{url_token}/articles"
        params = {
            "include": "data[*].comment_count,suggest_edit,is_normal,thumbnail_extra_info,thumbnail,can_comment,comment_permission,admin_closed_comment,content,voteup_count,created,updated,upvoted_followees,voting,review_info,reaction_instruction,is_labeled,label_info;data[*].vessay_info;data[*].author.badge[?(type=best_answerer)].topics;data[*].author.vip_info;",
            "offset": offset,
            "limit": limit,
            "order_by": "created",
        }
        return await self.get(uri, params)

    async def get_creator_videos(
        self, url_token: str, offset: int = 0, limit: int = 20
    ) -> Dict:
        """
        获取创作者的视频
        Args:
            url_token:
            offset:
            limit:

        Returns:

        """
        uri = f"/api/v4/members/{url_token}/zvideos"
        params = {
            "include": "similar_zvideo,creation_relationship,reaction_instruction",
            "offset": offset,
            "limit": limit,
            "similar_aggregation": "true",
        }
        return await self.get(uri, params)

    async def get_all_anwser_by_creator(
        self,
        creator: ZhihuCreator,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[ZhihuContent]:
        """
        获取创作者的所有回答
        Args:
            creator: 创作者信息
            crawl_interval: 爬取一次笔记的延迟单位（秒）
            callback: 一次笔记爬取结束后

        Returns:

        """
        all_contents: List[ZhihuContent] = []
        is_end: bool = False
        offset: int = 0
        limit: int = 20
        while not is_end:
            res = await self.get_creator_answers(creator.url_token, offset, limit)
            if not res:
                break
            utils.logger.info(
                f"[ZhiHuClient.get_all_anwser_by_creator] Get creator {creator.url_token} answers: {res}"
            )
            paging_info = res.get("paging", {})
            is_end = paging_info.get("is_end")
            contents = self._extractor.extract_content_list_from_creator(
                res.get("data")
            )
            if callback:
                await callback(contents)
            all_contents.extend(contents)
            offset += limit
            await asyncio.sleep(crawl_interval)
        return all_contents

    async def get_all_articles_by_creator(
        self,
        creator: ZhihuCreator,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[ZhihuContent]:
        """
        获取创作者的所有文章
        Args:
            creator:
            crawl_interval:
            callback:

        Returns:

        """
        all_contents: List[ZhihuContent] = []
        is_end: bool = False
        offset: int = 0
        limit: int = 20
        while not is_end:
            res = await self.get_creator_articles(creator.url_token, offset, limit)
            if not res:
                break
            paging_info = res.get("paging", {})
            is_end = paging_info.get("is_end")
            contents = self._extractor.extract_content_list_from_creator(
                res.get("data")
            )
            if callback:
                await callback(contents)
            all_contents.extend(contents)
            offset += limit
            await asyncio.sleep(crawl_interval)
        return all_contents

    async def get_all_videos_by_creator(
        self,
        creator: ZhihuCreator,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> List[ZhihuContent]:
        """
        获取创作者的所有视频
        Args:
            creator:
            crawl_interval:
            callback:

        Returns:

        """
        all_contents: List[ZhihuContent] = []
        is_end: bool = False
        offset: int = 0
        limit: int = 20
        while not is_end:
            res = await self.get_creator_videos(creator.url_token, offset, limit)
            if not res:
                break
            paging_info = res.get("paging", {})
            is_end = paging_info.get("is_end")
            contents = self._extractor.extract_content_list_from_creator(
                res.get("data")
            )
            if callback:
                await callback(contents)
            all_contents.extend(contents)
            offset += limit
            await asyncio.sleep(crawl_interval)
        return all_contents

    async def get_answer_info(
        self, question_id: str, answer_id: str
    ) -> Optional[ZhihuContent]:
        """
        获取回答信息
        Args:
            question_id:
            answer_id:

        Returns:

        """
        uri = f"/question/{question_id}/answer/{answer_id}"
        response_html = await self.get(uri, return_response=True)
        return self._extractor.extract_answer_content_from_html(response_html)

    # async def get_answer_info(self, question_id: str, answer_id: str) -> Optional[ZhihuContent]:
    #     if self.playwright_page.is_closed():
    #         utils.logger.error("Playwright 页面已关闭")
    #         return None

    #     try:
    #         page = self.playwright_page
    #         url = f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}"
    #         await page.goto(url, timeout=60000)
    #         await page.wait_for_selector(".ContentItem", state="attached", timeout=10000)

    #         # 方法1：从URL路径直接提取answer_id
    #         path_segments = (await page.evaluate("""() => window.location.pathname.split('/')"""))
    #         extracted_answer_id = path_segments[-1] if len(path_segments) >= 5 else answer_id

    #         # 方法2：从meta标签提取（备用方案）
    #         meta_content = await page.evaluate("""() => {
    #             const meta = document.querySelector('meta[itemprop="url"]');
    #             return meta ? meta.content : "";
    #         }""")

    #         if "/answer/" in meta_content:
    #             extracted_answer_id = meta_content.split("/")[-1]

    #         utils.logger.info(f"提取的回答ID: {extracted_answer_id}")
    #         return await self._get_answer_info_by_api(extracted_answer_id)

    #     except Exception as e:
    #         utils.logger.error(f"获取回答信息失败: {str(e)}")
    #         # 回退到原始HTML解析
    #         uri = f"/question/{question_id}/answer/{answer_id}"
    #         response_html = await self.get(uri, return_response=True)
    #         return self._extractor.extract_answer_content_from_html(response_html)

    # async def _get_answer_info_by_api(self, answer_id: str) -> Optional[ZhihuContent]:
    #     uri = f"/api/v4/answers/{answer_id}"
    #     params = {
    #         "include": "content,voteup_count,comment_count,created_time,updated_time,author,question"
    #     }

    #     try:
    #         api_data = await self.get(uri, params)

    #         # 提取原始 HTML 内容
    #         content_html = api_data.get("content", "")

    #         # 处理 HTML 内容：去除标签、处理转义字符、清理空白
    #         if content_html:
    #             # 去除所有 HTML 标签
    #             clean_text = re.sub(r'<[^>]+>', '', content_html)
    #             # 处理 HTML 转义字符（如 &nbsp; &lt; 等）
    #             clean_text = unescape(clean_text)
    #             # 替换多个连续空白字符为单个空格
    #             clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    #         else:
    #             clean_text = ""

    #         return ZhihuContent(
    #             content_id=str(api_data["id"]),
    #             content_type="answer",
    #             title=api_data["question"]["title"],
    #             content_text=api_data["content"],  # 保留原始 HTML 内容
    #             desc=clean_text,  # 存储处理后的纯文本
    #             voteup_count=api_data["voteup_count"],
    #             comment_count=api_data["comment_count"],
    #             # created_time=api_data.get("created_time", 0),
    #             # updated_time=api_data.get("updated_time", 0),
    #             creator=ZhihuCreator(
    #                 user_id=str(api_data["author"]["id"]),
    #                 name=api_data["author"]["name"],
    #                 url_token=api_data["author"]["url_token"]
    #             )
    #         )
    #     except Exception as e:
    #         utils.logger.error(f"API获取回答失败: {e}")
    #         return None

    async def _get_answer_info_by_api(self, answer_id: str) -> Optional[ZhihuContent]:
        uri = f"/api/v4/answers/{answer_id}"
        params = {
            "include": "content,voteup_count,comment_count,created_time,updated_time,author,question"
        }

        try:
            api_data = await self.get(uri, params)

            # 创建模型实例
            content = ZhihuContent()

            # 基础字段
            content.content_id = str(api_data.get("id", ""))
            content.content_type = "answer"
            content.content_text = api_data.get("content", "")  # ✅ 正确字段名
            content.question_id = str(api_data.get("question", {}).get("id", ""))
            content.title = api_data.get("question", {}).get("title", "")

            # 链接字段
            content.content_url = (
                f"{zhihu_constant.ZHIHU_URL}/question/"
                f"{content.question_id}/answer/{content.content_id}"
            )

            # 统计字段
            content.voteup_count = api_data.get("voteup_count", 0)
            content.comment_count = api_data.get("comment_count", 0)

            # 时间字段（保持原始数字类型）
            content.created_time = api_data.get("created_time", 0)
            content.updated_time = api_data.get("updated_time", 0)

            # 作者信息（直接赋值）
            author = api_data.get("author", {})
            content.user_id = str(author.get("id", ""))
            content.user_nickname = author.get("name", "")
            content.user_url_token = author.get("url_token", "")
            content.user_avatar = author.get("avatar_url", "")
            content.user_link = (
                f"{zhihu_constant.ZHIHU_URL}/people/" f"{content.user_url_token}"
            )

            return content

        except Exception as e:
            utils.logger.error(f"API获取回答失败: {e}")
            return None

    async def get_article_info(self, article_id: str) -> Optional[ZhihuContent]:
        """
        获取文章信息
        Args:
            article_id:

        Returns:

        """
        uri = f"/p/{article_id}"
        response_html = await self.get(uri, return_response=True)
        return self._extractor.extract_article_content_from_html(response_html)

    async def get_video_info(self, video_id: str) -> Optional[ZhihuContent]:
        """
        获取视频信息
        Args:
            video_id:

        Returns:

        """
        uri = f"/zvideo/{video_id}"
        response_html = await self.get(uri, return_response=True)
        return self._extractor.extract_zvideo_content_from_html(response_html)

    async def get_question_answers(
        self, question_id: str, offset: int = 0, limit: int = 20
    ) -> Dict:
        """
        获取问题的所有回答
        Args:
            question_id: 问题ID
            offset: 偏移量
            limit: 每页数量

        Returns:

        """
        uri = f"/api/v4/questions/{question_id}/answers"
        params = {
            "include": "data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,annotation_action,annotation_detail,collapse_reason,collapsed_by,suggest_edit,comment_count,can_comment,content,editable_content,attachment,voteup_count,reshipment_settings,comment_permission,created_time,updated_time,review_info,excerpt,paid_info,reaction_instruction,is_labeled,label_info",
            "offset": offset,
            "limit": limit,
            "order_by": "created",
        }
        return await self.get(uri, params)
