import os
import pathlib
from typing import Dict

import aiofiles
import config
from base.base_crawler import AbstractStoreImage
from tools import utils

from .bilibili_store_impl import *
from .bilibilli_store_video import *


class BilibiliVideo(AbstractStoreImage):
    def __init__(self):
        # 使用配置中的数据目录，如果没有则使用默认值
        base_data_dir = getattr(config, "DATA_DIR", "data")
        self.video_store_path: str = f"{base_data_dir}/bilibili/videos"

    async def store_video(self, video_content_item: Dict):
        """
        store content
        Args:
            content_item:

        Returns:

        """
        await self.save_video(
            video_content_item.get("aid"),
            video_content_item.get("video_content"),
            video_content_item.get("extension_file_name"),
        )

    def make_save_file_name(self, aid: str, extension_file_name: str) -> str:
        """
        make save file name by store type
        Args:
            aid: aid
        Returns:

        """
        return f"{self.video_store_path}/{aid}/{extension_file_name}"

    async def save_video(self, aid: int, video_content: str, extension_file_name="mp4"):
        """
        save video to local
        Args:
            aid: aid
            video_content: video content

        Returns:

        """
        utils.logger.info(
            f"[BilibiliVideo.save_video] Start saving video for aid: {aid}"
        )
        utils.logger.info(
            f"[BilibiliVideo.save_video] Content size: {len(video_content) if video_content else 0} bytes"
        )

        try:
            dir_path = self.video_store_path + "/" + str(aid)
            utils.logger.info(
                f"[BilibiliVideo.save_video] Creating directory: {dir_path}"
            )
            pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)
            utils.logger.info(
                f"[BilibiliVideo.save_video] Directory creation completed"
            )

            save_file_name = self.make_save_file_name(str(aid), extension_file_name)
            utils.logger.info(
                f"[BilibiliVideo.save_video] Save file name: {save_file_name}"
            )

            # 写入文件
            async with aiofiles.open(save_file_name, "wb") as f:
                await f.write(video_content)
                utils.logger.info(
                    f"[BilibiliVideo.save_video] Video content written to file"
                )

            utils.logger.info(
                f"[BilibiliVideo.save_video] Video saved to {save_file_name}"
            )

            # 验证文件
            if os.path.exists(save_file_name):
                file_size = os.path.getsize(save_file_name)
                utils.logger.info(
                    f"[BilibiliVideo.save_video] File successfully saved. Size: {file_size} bytes"
                )
            else:
                utils.logger.error(
                    f"[BilibiliVideo.save_video] File was not found after saving attempt: {save_file_name}"
                )
                raise FileNotFoundError(f"Failed to save video file: {save_file_name}")

        except Exception as e:
            utils.logger.error(
                f"[BilibiliVideo.save_video] Error occurred while saving video: {str(e)}"
            )
            import traceback

            utils.logger.error(
                f"[BilibiliVideo.save_video] Traceback: {traceback.format_exc()}"
            )
            raise

    def make_save_file_name(self, aid: str, extension_file_name: str) -> str:
        """
        make save file name by store type
        Args:
            aid: aid
        Returns:

        """
        return f"{self.video_store_path}/{aid}/{extension_file_name}"

    async def save_video(self, aid: int, video_content: str, extension_file_name="mp4"):
        """
        save video to local
        Args:
            aid: aid
            video_content: video content

        Returns:

        """
        utils.logger.info(
            f"[BilibiliVideo.save_video] Start saving video for aid: {aid}"
        )
        utils.logger.info(
            f"[BilibiliVideo.save_video] Content size: {len(video_content) if video_content else 0} bytes"
        )

        dir_path = self.video_store_path + "/" + str(aid)
        utils.logger.info(f"[BilibiliVideo.save_video] Creating directory: {dir_path}")
        pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)
        utils.logger.info(f"[BilibiliVideo.save_video] Directory creation completed")

        save_file_name = self.make_save_file_name(str(aid), extension_file_name)
        utils.logger.info(
            f"[BilibiliVideo.save_video] Save file name: {save_file_name}"
        )

        try:
            async with aiofiles.open(save_file_name, "wb") as f:
                await f.write(video_content)
                utils.logger.info(
                    f"[BilibiliVideo.save_video] Video content written to file"
                )

            utils.logger.info(
                f"[BilibiliVideo.save_video] Video saved to {save_file_name}"
            )

            # 检查文件是否存在
            if os.path.exists(save_file_name):
                file_size = os.path.getsize(save_file_name)
                utils.logger.info(
                    f"[BilibiliVideo.save_video] File successfully saved. Size: {file_size} bytes"
                )
            else:
                utils.logger.error(
                    f"[BilibiliVideo.save_video] File was not found after saving attempt: {save_file_name}"
                )

        except Exception as e:
            utils.logger.error(
                f"[BilibiliVideo.save_video] Error occurred while saving video: {str(e)}"
            )
