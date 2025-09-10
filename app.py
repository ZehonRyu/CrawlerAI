# app.py
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from threading import Lock, Thread

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from main import CrawlerConfig
from main import main as run_crawler_main

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从环境变量获取配置
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 5000))
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 存储任务状态
task_status = {}
# 任务锁，防止并发问题
task_lock = Lock()
# 正在运行的任务
running_tasks = set()


# 提供前端页面
@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


# 提供CSS文件
@app.route("/css/<path:filename>")
def css(filename):
    return send_from_directory("frontend/css", filename)


# 提供JS文件
@app.route("/js/<path:filename>")
def js(filename):
    return send_from_directory("frontend/js", filename)


@app.route("/api/run-crawler", methods=["POST"])
def run_crawler():
    try:
        data = request.json
        task_id = data.get("task_id", "default")
        task_type = data.get("task-type")  # 获取任务类型

        # 检查任务是否已经在运行
        with task_lock:
            if task_id in running_tasks:
                return jsonify({"success": False, "message": "任务已在运行中，请勿重复点击"}), 400

            # 标记任务为正在运行
            running_tasks.add(task_id)

        # 获取参数
        logintype = data.get("logintype")
        platform = data.get("platform")
        crawlertype = data.get("crawlertype")

        # 根据任务类型获取相应URL
        url = None
        if task_type == "zhihu-question":
            url = data.get("question-url")
        elif task_type == "bili-video":
            url = data.get("video-url")
        elif task_type == "xhs-detail":
            url = data.get("post-url")

        # 记录任务状态
        task_status[task_id] = {"status": "running", "message": "正在运行爬虫和生成模型..."}

        # 在新线程中运行爬虫
        thread = Thread(
            target=execute_crawler,
            args=(logintype, platform, crawlertype, task_id, url, task_type),
        )
        thread.daemon = True  # 设置为守护线程
        thread.start()

        return jsonify({"success": True, "task_id": task_id, "message": "任务已启动"})
    except Exception as e:
        logger.error(f"运行爬虫时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


def execute_crawler(logintype, platform, crawlertype, task_id, url, task_type):
    try:
        # 如果提供了URL，则更新配置文件中的URL
        if url:
            update_config_url(platform, crawlertype, url, task_type)

        # 在运行爬虫之前删除对应的模型目录
        model_name = f"{platform}_model"
        model_dir = f"model_{model_name}"

        if os.path.exists(model_dir):
            import shutil

            shutil.rmtree(model_dir)
            logger.info(f"已删除已存在的模型目录: {model_dir}")

        # 创建爬虫配置
        config = CrawlerConfig(
            logintype=logintype, platform=platform, crawlertype=crawlertype
        )

        # 运行爬虫主程序
        # 注意: asyncio.run() 不能在已有事件循环的线程中运行
        # 所以我们需要创建一个新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # 增加重试机制和错误处理
        try:
            loop.run_until_complete(run_crawler_main(config))
        except Exception as e:
            # 记录详细错误信息
            logger.error(f"爬虫执行过程中发生错误: {str(e)}")
            # 尝试再次运行
            try:
                logger.info("尝试重新运行爬虫...")
                loop.run_until_complete(run_crawler_main(config))
            except Exception as retry_error:
                logger.error(f"重试后仍然失败: {str(retry_error)}")
                raise retry_error

        # 更新任务状态
        task_status[task_id] = {"status": "completed", "message": "爬虫运行完成，模型已生成"}
        logger.info(f"任务 {task_id} 完成")
    except Exception as e:
        task_status[task_id] = {"status": "error", "message": str(e)}
        logger.error(f"任务 {task_id} 出错: {str(e)}")
    finally:
        # 无论成功还是失败，都要从运行中任务集合中移除
        with task_lock:
            running_tasks.discard(task_id)


def extract_bv_id_from_url(url):
    """
    从B站URL中提取BV号
    """
    import re

    # 匹配BV号的正则表达式
    match = re.search(r"BV[0-9A-Za-z]+", url)
    if match:
        return match.group(0)
    return None


def update_config_url(platform, crawlertype, url, task_type):
    """
    根据平台和爬虫类型更新配置文件中的URL
    """
    config_path = os.path.join(
        os.path.dirname(__file__), "crawler", "config", "base_config.py"
    )

    try:
        # 读取配置文件
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # 根据任务类型确定要替换的配置项
        if task_type == "zhihu-question":
            # 更新知乎问题URL
            for i, line in enumerate(lines):
                if line.startswith("ZHIHU_QUESTION_URL ="):
                    lines[i] = f'ZHIHU_QUESTION_URL = "{url}"  # 替换为实际的问题URL\n'
                    break
        elif task_type == "bili-video":
            # 更新B站指定视频ID列表
            # 查找BILI_SPECIFIED_ID_LIST开始位置
            start_index = -1
            end_index = -1
            for i, line in enumerate(lines):
                if "BILI_SPECIFIED_ID_LIST = [" in line:
                    start_index = i
                elif start_index != -1 and line.strip() == "]" and end_index == -1:
                    end_index = i
                    break

            # 如果找到了列表定义，则替换它
            if start_index != -1 and end_index != -1:
                # 提取BV号（从URL中）
                bv_id = extract_bv_id_from_url(url)
                if bv_id:
                    lines[start_index] = "BILI_SPECIFIED_ID_LIST = [\n"
                    lines[start_index + 1] = f'    "{bv_id}"\n'
                    lines[start_index + 2] = "]\n"
                    # 删除多余的行
                    for _ in range(end_index - start_index - 2):
                        lines.pop(start_index + 3)
        elif task_type == "xhs-detail":
            # 更新小红书指定笔记URL列表
            # 查找XHS_SPECIFIED_NOTE_URL_LIST开始位置
            start_index = -1
            end_index = -1
            for i, line in enumerate(lines):
                if "XHS_SPECIFIED_NOTE_URL_LIST = [" in line:
                    start_index = i
                elif start_index != -1 and line.strip() == "]" and end_index == -1:
                    end_index = i
                    break

            # 如果找到了列表定义，则替换它
            if start_index != -1 and end_index != -1:
                lines[start_index] = "XHS_SPECIFIED_NOTE_URL_LIST = [\n"
                lines[start_index + 1] = f'    "{url}"\n'
                lines[start_index + 2] = "]\n"
                # 删除多余的行
                for _ in range(end_index - start_index - 2):
                    lines.pop(start_index + 3)

        # 写回配置文件
        with open(config_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        logger.info(f"已更新配置文件中的URL，任务类型: {task_type}")
    except Exception as e:
        logger.error(f"更新配置文件失败: {str(e)}")
        raise


@app.route("/api/task-status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    status = task_status.get(task_id, {"status": "unknown", "message": "任务不存在"})
    return jsonify(status)


@app.route("/api/summarize", methods=["POST"])
def summarize():
    try:
        data = request.json
        model_name = data.get("model_name")

        # 添加AI目录到路径以解决导入问题
        ai_dir = os.path.join(os.path.dirname(__file__), "AI")
        if ai_dir not in sys.path:
            sys.path.insert(0, ai_dir)

        # 动态导入AI模块以避免相对导入问题
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "use_model", os.path.join(ai_dir, "AI_rag", "use_model.py")
        )
        use_model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(use_model)

        # 直接使用传入的model_name（平台名+model后缀）
        summary_text = use_model.generate_summary(model_name)

        # 返回纯文本格式，去掉HTML标签
        return jsonify({"success": True, "summary": summary_text})
    except FileNotFoundError as e:
        logger.error(f"模型未找到: {str(e)}")
        return jsonify({"success": False, "message": f"模型未找到: {str(e)}"}), 404
    except Exception as e:
        logger.error(f"生成总结时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/ask", methods=["POST"])
def ask_question():
    try:
        data = request.json
        question = data.get("question", "")
        model_name = data.get("model_name")

        # 添加AI目录到路径以解决导入问题
        ai_dir = os.path.join(os.path.dirname(__file__), "AI")
        if ai_dir not in sys.path:
            sys.path.insert(0, ai_dir)

        # 动态导入AI模块以避免相对导入问题
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "use_model", os.path.join(ai_dir, "AI_rag", "use_model.py")
        )
        use_model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(use_model)

        # 直接使用传入的model_name（平台名+model后缀）
        answer_text = use_model.ask_question(question, model_name)

        return jsonify({"success": True, "answer": answer_text})
    except FileNotFoundError as e:
        logger.error(f"模型未找到: {str(e)}")
        return jsonify({"success": False, "message": f"模型未找到: {str(e)}"}), 404
    except Exception as e:
        logger.error(f"回答问题时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


# 添加一个测试路由，确保API正常工作
@app.route("/api/test", methods=["GET"])
def test_api():
    return jsonify({"message": "API 正常工作!"})


if __name__ == "__main__":
    # 使用环境变量配置应用
    try:
        app.run(debug=DEBUG, port=PORT, host=HOST, threaded=True)
    except SystemExit:
        logger.info("应用正常退出")
    except Exception as e:
        logger.error(f"应用运行出错: {str(e)}")
