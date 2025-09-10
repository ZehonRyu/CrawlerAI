from typing import List

import config
from var import source_keyword_var

from .bilibili_store_impl import *
from .bilibilli_store_video import *


class BiliStoreFactory:
    STORES = {
        "csv": BiliCsvStoreImplement,
        "db": BiliDbStoreImplement,
        "json": BiliJsonStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = BiliStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                "[BiliStoreFactory.create_store] Invalid save option only supported csv or db or json ..."
            )
        return store_class()


async def update_bilibili_video(video_item: Dict):
    video_item_view: Dict = video_item.get("View")
    video_user_info: Dict = video_item_view.get("owner")
    video_item_stat: Dict = video_item_view.get("stat")
    video_id = str(video_item_view.get("aid"))
    save_content_item = {
        "video_id": video_id,
        "video_type": "video",
        "title": video_item_view.get("title", "")[:500],
        "desc": video_item_view.get("desc", "")[:500],
        "create_time": video_item_view.get("pubdate"),
        "user_id": str(video_user_info.get("mid")),
        "nickname": video_user_info.get("name"),
        "avatar": video_user_info.get("face", ""),
        "liked_count": str(video_item_stat.get("like", "")),
        "video_play_count": str(video_item_stat.get("view", "")),
        "video_danmaku": str(video_item_stat.get("danmaku", "")),
        "video_comment": str(video_item_stat.get("reply", "")),
        "last_modify_ts": utils.get_current_timestamp(),
        "video_url": f"https://www.bilibili.com/video/av{video_id}",
        "video_cover_url": video_item_view.get("pic", ""),
        "source_keyword": source_keyword_var.get(),
    }
    utils.logger.info(
        f"[store.bilibili.update_bilibili_video] bilibili video id:{video_id}, title:{save_content_item.get('title')}"
    )
    await BiliStoreFactory.create_store().store_content(content_item=save_content_item)


async def update_up_info(video_item: Dict):
    video_item_card_list: Dict = video_item.get("Card")
    video_item_card: Dict = video_item_card_list.get("card")
    saver_up_info = {
        "user_id": str(video_item_card.get("mid")),
        "nickname": video_item_card.get("name"),
        "avatar": video_item_card.get("face"),
        "last_modify_ts": utils.get_current_timestamp(),
        "total_fans": video_item_card.get("fans"),
        "total_liked": video_item_card_list.get("like_num"),
        "user_rank": video_item_card.get("level_info").get("current_level"),
        "is_official": video_item_card.get("official_verify").get("type"),
    }
    utils.logger.info(
        f"[store.bilibili.update_up_info] bilibili user_id:{video_item_card.get('mid')}"
    )
    await BiliStoreFactory.create_store().store_creator(creator=saver_up_info)


# async def batch_update_bilibili_video_comments(video_id: str, comments: List[Dict]):
#     if not comments:
#         return
#     for comment_item in comments:
#         await update_bilibili_video_comment(video_id, comment_item)


async def batch_update_bilibili_video_comments(video_id: str, comments: List[Dict]):
    utils.logger.info(
        f"[batch_update_bilibili_video_comments] 收到 {len(comments)} 条评论准备处理"
    )
    if not comments:
        utils.logger.info("[batch_update_bilibili_video_comments] 没有评论需要处理")
        return
    for index, comment_item in enumerate(comments):
        utils.logger.info(
            f"[batch_update_bilibili_video_comments] 正在处理第 {index+1} 条评论，comment_id: {comment_item.get('rpid')}"
        )
        await update_bilibili_video_comment(video_id, comment_item)
    utils.logger.info(
        f"[batch_update_bilibili_video_comments] 完成处理 {len(comments)} 条评论"
    )


# async def update_bilibili_video_comment(video_id: str, comment_item: Dict):
#     comment_id = str(comment_item.get("rpid"))
#     parent_comment_id = str(comment_item.get("parent", 0))
#     content: Dict = comment_item.get("content")
#     user_info: Dict = comment_item.get("member")
#     save_comment_item = {
#         "comment_id": comment_id,
#         "parent_comment_id": parent_comment_id,
#         "create_time": comment_item.get("ctime"),
#         "video_id": str(video_id),
#         "content": content.get("message"),
#         "user_id": user_info.get("mid"),
#         "nickname": user_info.get("uname"),
#         "avatar": user_info.get("avatar"),
#         "sub_comment_count": str(comment_item.get("rcount", 0)),
#         "last_modify_ts": utils.get_current_timestamp(),
#     }
#     utils.logger.info(
#         f"[store.bilibili.update_bilibili_video_comment] Bilibili video comment: {comment_id}, content: {save_comment_item.get('content')}")
#     await BiliStoreFactory.create_store().store_comment(comment_item=save_comment_item)


async def update_bilibili_video_comment(video_id: str, comment_item: Dict):
    utils.logger.debug(f"[update_bilibili_video_comment] 原始评论数据: {comment_item}")

    comment_id = str(comment_item.get("rpid"))
    # 添加检查
    if not comment_id:
        utils.logger.warning(f"[update_bilibili_video_comment] 评论ID为空，跳过处理")
        return

    parent_comment_id = str(comment_item.get("parent", 0))
    content: Dict = comment_item.get("content", {})
    user_info: Dict = comment_item.get("member", {})

    # 添加数据完整性检查
    if not content or not user_info:
        utils.logger.warning(
            f"[update_bilibili_video_comment] 评论数据不完整，comment_id: {comment_id}"
        )
        return

    save_comment_item = {
        "comment_id": comment_id,
        "parent_comment_id": parent_comment_id,
        "create_time": comment_item.get("ctime"),
        "video_id": str(video_id),
        "content": content.get("message", ""),
        "user_id": user_info.get("mid", ""),
        "nickname": user_info.get("uname", ""),
        "avatar": user_info.get("avatar", ""),
        "sub_comment_count": str(comment_item.get("rcount", 0)),
        "last_modify_ts": utils.get_current_timestamp(),
    }

    # 检查关键字段是否为空
    if not save_comment_item["content"]:
        utils.logger.warning(
            f"[update_bilibili_video_comment] 评论内容为空，comment_id: {comment_id}"
        )

    utils.logger.info(
        f"[store.bilibili.update_bilibili_video_comment] Bilibili video comment: {comment_id}, content: {save_comment_item.get('content')[:50]}..."
    )
    await BiliStoreFactory.create_store().store_comment(comment_item=save_comment_item)


async def store_video(aid, video_content, extension_file_name):
    """
    video video storage implementation
    Args:
        aid:
        video_content:
        extension_file_name:
    """
    await BilibiliVideo().store_video(
        {
            "aid": aid,
            "video_content": video_content,
            "extension_file_name": extension_file_name,
        }
    )


async def store_audio(aid: str, audio_content: bytes, filename: str):
    """存储音频文件"""
    audio_dir = os.path.join(config.STORE_DIR, "bilibili", "audios")
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, f"{aid}_{filename}")

    with open(audio_path, "wb") as f:
        f.write(audio_content)

    utils.logger.info(f"音频已保存: {audio_path}")
