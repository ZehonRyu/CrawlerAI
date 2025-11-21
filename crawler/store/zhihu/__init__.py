from typing import List

import config
from base.base_crawler import AbstractStore
from model.m_zhihu import ZhihuComment, ZhihuContent, ZhihuCreator, ZhihuQuestionAnswer
from store.zhihu.zhihu_store_impl import (
    ZhihuCsvStoreImplement,
    ZhihuDbStoreImplement,
    ZhihuJsonStoreImplement,
)
from tools import utils
from var import source_keyword_var


class ZhihuStoreFactory:
    STORES = {
        "csv": ZhihuCsvStoreImplement,
        "db": ZhihuDbStoreImplement,
        "json": ZhihuJsonStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = ZhihuStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                "[ZhihuStoreFactory.create_store] Invalid save option only supported csv or db or json ..."
            )
        utils.logger.info(
            f"[ZhihuStoreFactory.create_store] Creating store of type: {config.SAVE_DATA_OPTION}"
        )
        return store_class()


async def batch_update_zhihu_contents(contents: List[ZhihuContent]):
    """
    批量更新知乎内容
    Args:
        contents:

    Returns:

    """
    if not contents:
        return

    for content_item in contents:
        await update_zhihu_content(content_item)


async def update_zhihu_content(content_item: ZhihuContent):
    """
    更新知乎内容
    Args:
        content_item:

    Returns:

    """
    content_item.source_keyword = source_keyword_var.get()
    local_db_item = content_item.model_dump()
    local_db_item.update({"last_modify_ts": utils.get_current_timestamp()})
    utils.logger.info(
        f"[store.zhihu.update_zhihu_content] zhihu content: {local_db_item}"
    )
    await ZhihuStoreFactory.create_store().store_content(local_db_item)


async def batch_update_zhihu_note_comments(comments: List[ZhihuComment]):
    """
    批量更新知乎内容评论
    Args:
        comments:

    Returns:

    """
    if not comments:
        return

    for comment_item in comments:
        await update_zhihu_content_comment(comment_item)


async def update_zhihu_content_comment(comment_item: ZhihuComment):
    """
    更新知乎内容评论
    Args:
        comment_item:

    Returns:

    """
    local_db_item = comment_item.model_dump()
    local_db_item.update({"last_modify_ts": utils.get_current_timestamp()})
    utils.logger.info(
        f"[store.zhihu.update_zhihu_note_comment] zhihu content comment:{local_db_item}"
    )
    await ZhihuStoreFactory.create_store().store_comment(local_db_item)


async def save_creator(creator: ZhihuCreator):
    """
    保存知乎创作者信息
    Args:
        creator:

    Returns:

    """
    if not creator:
        return
    local_db_item = creator.model_dump()
    local_db_item.update({"last_modify_ts": utils.get_current_timestamp()})
    await ZhihuStoreFactory.create_store().store_creator(local_db_item)


async def batch_update_zhihu_question_answers(
    question_answers: List[ZhihuQuestionAnswer],
):
    """
    批量更新知乎问题回答
    Args:
        question_answers:

    Returns:

    """
    utils.logger.info(
        f"[store.zhihu.batch_update_zhihu_question_answers] 开始批量更新 {len(question_answers)} 条知乎问题回答"
    )
    try:
        if not question_answers:
            utils.logger.info(
                "[store.zhihu.batch_update_zhihu_question_answers] 没有回答需要更新"
            )
            return

        for question_answer in question_answers:
            await update_zhihu_question_answer(question_answer)
        utils.logger.info("[store.zhihu.batch_update_zhihu_question_answers] 批量更新完成")
    except Exception as e:
        utils.logger.error(
            f"[store.zhihu.batch_update_zhihu_question_answers] 批量更新时出错: {e}"
        )
        import traceback

        utils.logger.error(
            f"[store.zhihu.batch_update_zhihu_question_answers] 错误追踪: {traceback.format_exc()}"
        )
        raise  # 重新抛出异常


async def update_zhihu_question_answer(question_answer: ZhihuQuestionAnswer):
    """
    更新知乎问题回答
    Args:
        question_answer:

    Returns:

    """
    try:
        utils.logger.debug(
            f"[store.zhihu.update_zhihu_question_answer] 开始处理回答: {question_answer.content_id}"
        )
        question_answer.source_keyword = source_keyword_var.get()
        local_db_item = question_answer.model_dump()
        local_db_item.update({"last_modify_ts": utils.get_current_timestamp()})
        utils.logger.debug(
            f"[store.zhihu.update_zhihu_question_answer] 准备存储的回答数据: {local_db_item}"
        )
        await ZhihuStoreFactory.create_store().store_content(local_db_item)
        utils.logger.info(
            f"[store.zhihu.update_zhihu_question_answer] 成功存储回答: {question_answer.content_id}"
        )
    except Exception as e:
        utils.logger.error(
            f"[store.zhihu.update_zhihu_question_answer] 存储回答 {question_answer.content_id} 时出错: {e}"
        )
        import traceback

        utils.logger.error(
            f"[store.zhihu.update_zhihu_question_answer] 错误追踪: {traceback.format_exc()}"
        )
        raise
