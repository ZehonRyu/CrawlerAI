import os
from typing import Dict, List

import config
from tools import utils
from var import source_keyword_var

from .bilibili_store_impl import *
from .bilibilli_store_video import BilibiliVideo


# 这是一个模块级别的函数，不在任何类内部
async def store_video(aid, video_content, extension_file_name):
    """
    video video storage implementation
    Args:
        aid:
        video_content:
        extension_file_name:
    """
    utils.logger.info(f"[bilibili_store.store_video] Storing video for aid: {aid}")
    utils.logger.info(
        f"[bilibili_store.store_video] Video content size: {len(video_content) if video_content else 0} bytes"
    )
    utils.logger.info(
        f"[bilibili_store.store_video] Extension file name: {extension_file_name}"
    )

    try:
        # 创建 BilibiliVideo 类的实例
        video_store = BilibiliVideo()
        # 调用实例的 store_video 方法
        await video_store.store_video(
            {
                "aid": aid,
                "video_content": video_content,
                "extension_file_name": extension_file_name,
            }
        )
        utils.logger.info(
            f"[bilibili_store.store_video] Completed storing video for aid: {aid}"
        )
    except Exception as e:
        utils.logger.error(
            f"[bilibili_store.store_video] Error occurred while storing video: {str(e)}"
        )
        import traceback

        utils.logger.error(
            f"[bilibili_store.store_video] Traceback: {traceback.format_exc()}"
        )
        raise


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
    """
    update bilibili video info
    Args:
        video_item:

    Returns:

    """
    utils.logger.info(f"[store.bilibili.update_bilibili_video] Processing video item")
    utils.logger.info(
        f"[store.bilibili.update_bilibili_video] Using data directory: {getattr(config, 'DATA_DIR', 'data')}"
    )

    # 确保使用会话特定的数据目录
    base_data_dir = getattr(config, "DATA_DIR", "data")
    video_dir = f"{base_data_dir}/bilibili/json"

    # 确保目录存在
    import os

    os.makedirs(video_dir, exist_ok=True)
    utils.logger.info(
        f"[store.bilibili.update_bilibili_video] Video directory: {video_dir}"
    )

    # 保存视频数据到会话特定目录
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    video_file = f"{video_dir}/video_info_{today}.json"

    utils.logger.info(
        f"[store.bilibili.update_bilibili_video] Saving video info to: {video_file}"
    )

    # 读取现有数据（如果存在）
    video_list = []
    try:
        if os.path.exists(video_file):
            # 使用正确的工具函数
            video_list = utils.load_json(video_file)
            if not isinstance(video_list, list):
                video_list = []
    except Exception as e:
        utils.logger.error(
            f"[store.bilibili.update_bilibili_video] Error reading existing video file: {e}"
        )
        video_list = []

    # 添加新视频数据
    video_list.append(video_item)

    # 保存视频数据（使用Python内置json模块）
    try:
        import json

        with open(video_file, "w", encoding="utf-8") as f:
            json.dump(video_list, f, ensure_ascii=False, indent=4)
        utils.logger.info(
            f"[store.bilibili.update_bilibili_video] Bilibili video: {video_item.get('View', {}).get('aid')} saved successfully"
        )
    except Exception as e:
        utils.logger.error(
            f"[store.bilibili.update_bilibili_video] Error saving video data: {e}"
        )


async def update_up_info(video_item: Dict):
    """
    update up info
    Args:
        video_item:

    Returns:

    """
    utils.logger.info(f"[store.bilibili.update_up_info] Processing UP info")
    utils.logger.info(
        f"[store.bilibili.update_up_info] Using data directory: {getattr(config, 'DATA_DIR', 'data')}"
    )

    # 确保使用会话特定的数据目录
    base_data_dir = getattr(config, "DATA_DIR", "data")
    up_dir = f"{base_data_dir}/bilibili/json"

    # 确保目录存在
    import os

    os.makedirs(up_dir, exist_ok=True)
    utils.logger.info(f"[store.bilibili.update_up_info] UP directory: {up_dir}")

    # 保存UP主数据到会话特定目录
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    up_file = f"{up_dir}/up_info_{today}.json"

    utils.logger.info(f"[store.bilibili.update_up_info] Saving UP info to: {up_file}")

    # 提取UP主信息
    up_info = video_item.get("View").get("owner")
    if not up_info:
        utils.logger.warning(
            "[store.bilibili.update_up_info] No UP info found in video item"
        )
        return

    # 读取现有数据（如果存在）
    up_list = []
    try:
        if os.path.exists(up_file):
            # 使用正确的工具函数
            up_list = utils.load_json(up_file)
            if not isinstance(up_list, list):
                up_list = []
    except Exception as e:
        utils.logger.error(
            f"[store.bilibili.update_up_info] Error reading existing UP file: {e}"
        )
        up_list = []

    # 检查是否已存在该UP主信息
    exists = False
    for item in up_list:
        if item.get("mid") == up_info.get("mid"):
            exists = True
            break

    # 如果不存在则添加
    if not exists:
        up_list.append(up_info)
        try:
            # 使用Python内置json模块
            import json

            with open(up_file, "w", encoding="utf-8") as f:
                json.dump(up_list, f, ensure_ascii=False, indent=4)
            utils.logger.info(
                f"[store.bilibili.update_up_info] UP info: {up_info.get('mid')} saved successfully"
            )
        except Exception as e:
            utils.logger.error(
                f"[store.bilibili.update_up_info] Error saving UP data: {e}"
            )
    else:
        utils.logger.info(
            f"[store.bilibili.update_up_info] UP info: {up_info.get('mid')} already exists, skipping"
        )


async def batch_update_bilibili_video_comments(video_id: str, comments: List[Dict]):
    """
    batch update bilibili video comments
    Args:
        video_id: bilibili video id
        comments: bililibili video comments

    Returns:

    """
    utils.logger.info(
        f"[store.bilibili.batch_update_bilibili_video_comments] Processing comments for video: {video_id}"
    )
    utils.logger.info(
        f"[store.bilibili.batch_update_bilibili_video_comments] Using data directory: {getattr(config, 'DATA_DIR', 'data')}"
    )

    if not comments:
        utils.logger.warning(
            f"[store.bilibili.batch_update_bilibili_video_comments] No comments to process for video: {video_id}"
        )
        return

    # 确保使用会话特定的数据目录
    base_data_dir = getattr(config, "DATA_DIR", "data")
    comments_dir = f"{base_data_dir}/bilibili/json"

    # 确保目录存在
    import os

    os.makedirs(comments_dir, exist_ok=True)
    utils.logger.info(
        f"[store.bilibili.batch_update_bilibili_video_comments] Comments directory: {comments_dir}"
    )

    # 保存评论数据到会话特定目录
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    comment_file = f"{comments_dir}/video_{video_id}_comments_{today}.json"

    utils.logger.info(
        f"[store.bilibili.batch_update_bilibili_video_comments] Saving comments to: {comment_file}"
    )

    # 保存评论数据（使用Python内置json模块）
    try:
        import json

        with open(comment_file, "w", encoding="utf-8") as f:
            json.dump(comments, f, ensure_ascii=False, indent=4)
        utils.logger.info(
            f"[store.bilibili.batch_update_bilibili_video_comments] Successfully saved {len(comments)} comments for video: {video_id}"
        )
    except Exception as e:
        utils.logger.error(
            f"[store.bilibili.batch_update_bilibili_video_comments] Error saving comments: {e}"
        )


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

    # 确保存储使用会话特定的配置
    store = BiliStoreFactory.create_store()
    await store.store_comment(comment_item=save_comment_item)


async def store_audio(aid: str, audio_content: bytes, filename: str):
    """存储音频文件"""
    # 确保使用会话特定的数据目录
    base_data_dir = getattr(config, "DATA_DIR", "data")
    audio_dir = os.path.join(base_data_dir, "bilibili", "audios")
    os.makedirs(audio_dir, exist_ok=True)
    audio_path = os.path.join(audio_dir, f"{aid}_{filename}")

    with open(audio_path, "wb") as f:
        f.write(audio_content)

    utils.logger.info(f"音频已保存: {audio_path}")
