import os
import zipfile
from pathlib import Path

import requests


def download_from_github_release(
    repo_owner, repo_name, release_tag, file_name, local_path
):
    """
    从 GitHub Release 下载文件
    """
    url = f"https://github.com/{repo_owner}/{repo_name}/releases/download/{release_tag}/{file_name}"
    print(f"正在下载: {url}")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    # 确保目录存在
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)

    with open(local_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"文件已下载到: {local_path}")


def extract_model(zip_path, extract_to):
    """
    解压模型文件
    """
    print(f"正在解压 {zip_path} 到 {extract_to}")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    print("解压完成")


def main():
    # 配置信息 - 根据你的实际情况修改
    REPO_OWNER = "your_github_username"  # 替换为你的GitHub用户名
    REPO_NAME = "CrawlerAI"  # 替换为你的仓库名
    RELEASE_TAG = "v1.0"  # 替换为你创建的Release标签

    # 确保AI/audio_video目录存在
    Path("AI/audio_video").mkdir(parents=True, exist_ok=True)

    # 下载模型文件
    try:
        download_from_github_release(
            repo_owner=REPO_OWNER,
            repo_name=REPO_NAME,
            release_tag=RELEASE_TAG,
            file_name="faster_whisper_model.zip",
            local_path="AI/audio_video/faster_whisper_model.zip",
        )

        # 解压模型文件
        extract_model("AI/audio_video/faster_whisper_model.zip", "AI/audio_video/")

        # 删除压缩包以节省空间
        os.remove("AI/audio_video/faster_whisper_model.zip")
        print("模型下载和解压完成！")

    except Exception as e:
        print(f"下载或解压模型时出错: {e}")


if __name__ == "__main__":
    main()
