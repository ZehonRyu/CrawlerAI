import asyncio
import json
import logging
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from threading import Lock, Thread

from celery.result import AsyncResult
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

from AI.AI_rag.build_model import build_and_save_model
from crawler_celery import celery_app
from main import CrawlerConfig
from main import main as run_crawler_main
from main import transmit_data

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从环境变量获取配置
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 5000))
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 存储任务状态
task_status = {}
# 任务锁，防止并发问题
task_lock = Lock()
# 正在运行的任务
running_tasks = set()


qr_code_queue = queue.Queue()
qr_code_storage = {}
qr_code_lock = threading.Lock()


def store_qr_code(task_id, qr_code_data):
    """
    存储二维码数据（线程安全）
    """
    with qr_code_lock:
        qr_code_storage[task_id] = qr_code_data
    logger.info(
        f"已存储任务 {task_id} 的二维码数据，存储大小: {len(qr_code_data) if qr_code_data else 0} 字符"
    )


def get_stored_qr_code(task_id):
    """
    获取存储的二维码数据（线程安全）
    """
    with qr_code_lock:
        qr_data = qr_code_storage.get(task_id)
    logger.info(
        f"获取任务 {task_id} 的二维码数据: {'存在' if qr_data else '不存在'}，存储大小: {len(qr_data) if qr_data else 0} 字符"
    )
    return qr_data


def list_qr_codes():
    """
    列出所有存储的二维码任务（用于调试）
    """
    with qr_code_lock:
        keys = list(qr_code_storage.keys())
    logger.info(f"当前qr_code_storage中的任务: {keys}")
    return keys


def clear_qr_code(task_id):
    """
    清除二维码数据
    """
    if task_id in qr_code_storage:
        del qr_code_storage[task_id]
        logger.info(f"已清除任务 {task_id} 的二维码数据")


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


active_tasks = {}


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

        # 不再创建基于task_id的session文件夹，直接使用任务ID
        session_id = task_id  # 直接使用task_id作为session_id

        # 记录任务状态
        task_status[task_id] = {
            "status": "running",
            "message": "正在运行爬虫...",
            "platform": platform,
            "logintype": logintype,
            "crawlertype": crawlertype,
            "session_id": session_id,
            "last_heartbeat": datetime.now().isoformat(),
        }

        # 在新线程中运行爬虫
        thread = Thread(
            target=execute_crawler,
            args=(
                logintype,
                platform,
                crawlertype,
                task_id,
                url,
                task_type,
                session_id,
            ),
        )
        thread.daemon = True
        thread.start()

        # 记录活跃任务
        active_tasks[task_id] = {"thread": thread, "start_time": datetime.now()}

        return jsonify({"success": True, "task_id": task_id, "message": "任务已启动"})
    except Exception as e:
        logger.error(f"运行爬虫时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


# 添加心跳检测接口
@app.route("/api/task-heartbeat/<task_id>", methods=["POST"])
def task_heartbeat(task_id):
    task_info = task_status.get(task_id)
    if not task_info:
        return jsonify({"status": "unknown", "message": "任务不存在"})

    task_info["last_heartbeat"] = datetime.now().isoformat()
    return jsonify({"status": "success", "message": "心跳更新成功"})


# 添加取消任务接口
@app.route("/api/cancel-task/<task_id>", methods=["POST"])
def cancel_task(task_id):
    task_info = task_status.get(task_id)
    if not task_info:
        return jsonify({"success": False, "message": "任务不存在"})

    # 更新任务状态为取消
    task_info["status"] = "cancelled"
    task_info["message"] = "任务已被用户取消"

    # 从运行任务集合中移除
    with task_lock:
        running_tasks.discard(task_id)

    # 从活跃任务中移除
    if task_id in active_tasks:
        del active_tasks[task_id]

    logger.info(f"任务 {task_id} 已被取消")
    return jsonify({"success": True, "message": "任务已取消"})


# 添加定时检查任务心跳的函数
def check_task_heartbeats():
    while True:
        try:
            current_time = datetime.now()
            expired_tasks = []

            # 检查所有任务的心跳
            for task_id, task_info in task_status.items():
                last_heartbeat = task_info.get("last_heartbeat")
                if last_heartbeat:
                    heartbeat_time = datetime.fromisoformat(last_heartbeat)
                    time_diff = (current_time - heartbeat_time).total_seconds()
                    logger.info(
                        f"任务 {task_id} 上次心跳时间: {last_heartbeat}, 时间差: {time_diff}秒"
                    )
                    # 增加超时时间到60秒，给任务更多执行时间
                    if time_diff > 60:
                        expired_tasks.append(task_id)
                        logger.info(f"任务 {task_id} 被标记为过期")
                else:
                    logger.info(f"任务 {task_id} 没有心跳信息")

            # 取消过期任务
            for task_id in expired_tasks:
                logger.info(f"检测到任务 {task_id} 已断开连接，正在取消任务")
                task_status[task_id]["status"] = "cancelled"
                task_status[task_id]["message"] = "连接已断开，任务已取消"
                with task_lock:
                    running_tasks.discard(task_id)
                if task_id in active_tasks:
                    del active_tasks[task_id]
                    logger.info(f"任务 {task_id} 已从活跃任务中移除")

        except Exception as e:
            logger.error(f"检查任务心跳时出错: {e}")
            import traceback

            traceback.print_exc()

        # 每10秒检查一次
        time.sleep(10)


# 在应用启动时启动心跳检查线程
heartbeat_thread = Thread(target=check_task_heartbeats, daemon=True)
heartbeat_thread.start()


def execute_crawler(
    logintype, platform, crawlertype, task_id, url, task_type, session_id=None
):
    global task_status

    try:
        # 确保使用正确的任务ID作为session_id
        if session_id is None:
            session_id = task_id

        # 异步执行爬虫任务
        from main import run_crawler_internal

        # 传递task_id给Celery任务
        task = run_crawler_internal.delay(
            logintype, platform, crawlertype, url, task_type
        )

        # 更新任务状态
        task_status_update = {
            "status": "running",
            "celery_task_id": task.id,
            "message": "任务已提交到队列",
            "platform": platform,
            "logintype": logintype,
            "crawlertype": crawlertype,
            "session_id": session_id,
            "original_task_id": task_id,  # 保存原始任务ID
        }

        task_status[task_id].update(task_status_update)

        logger.info(f"任务 {task_id} 已提交，Celery任务ID: {task.id}，session_id: {session_id}")

    except Exception as e:
        task_status[task_id].update({"status": "error", "message": str(e)})
        logger.error(f"任务 {task_id} 提交失败: {str(e)}")


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
    logger.info(f"收到任务状态查询请求 - 任务ID: {task_id}")
    task_info = task_status.get(task_id)
    if not task_info:
        logger.warning(f"任务 {task_id} 不存在")
        return jsonify({"status": "unknown", "message": "任务不存在"})

    logger.info(f"任务 {task_id} 信息: {task_info}")

    # 如果有Celery任务ID，检查Celery任务状态
    if "celery_task_id" in task_info:
        celery_task_id = task_info["celery_task_id"]
        logger.info(f"检查Celery任务状态 - Celery任务ID: {celery_task_id}")
        # 确保使用正确的Celery应用实例
        celery_task = celery_app.AsyncResult(celery_task_id)

        try:
            logger.info(f"Celery任务状态: {celery_task.state}")
            if celery_task.state == "PENDING":
                response = {"status": "pending", "message": "任务等待中"}
            elif celery_task.state == "PROGRESS":
                response = {"status": "running", "message": "任务执行中"}
            elif celery_task.state == "STARTED":
                response = {"status": "running", "message": "任务正在执行中"}
            elif celery_task.state == "SUCCESS":
                result = celery_task.result
                logger.info(f"Celery任务成功完成，结果: {result}")
                # 确保我们正确处理了任务返回的结果
                if isinstance(result, dict) and result.get("status") == "success":
                    response = {
                        "status": "completed",
                        "message": "爬虫运行完成，请点击生成模型按钮生成模型",
                        "result_file": result.get("result_file"),
                    }
                    # 更新任务状态，存储结果文件路径和会话ID（如果有的话）
                    task_status[task_id].update(
                        {
                            "status": "completed",
                            "message": "爬虫运行完成，请点击生成模型按钮生成模型",
                            "result_file": result.get("result_file"),
                            "session_id": result.get(
                                "session_id", task_info.get("session_id")
                            ),
                            "task_id": result.get("task_id", task_id),  # 确保使用正确的task_id
                        }
                    )
                    # 更新task_file_mapping
                    from main import task_file_mapping

                    task_file_mapping[task_id] = result.get("result_file")
                    # 如果返回了新的task_id，也要更新映射
                    if result.get("task_id") and result["task_id"] != task_id:
                        task_file_mapping[result["task_id"]] = result.get("result_file")
                else:
                    response = {
                        "status": "completed",
                        "message": "爬虫运行完成，请点击生成模型按钮生成模型",
                    }
                    # 更新任务状态
                    task_status[task_id].update(
                        {"status": "completed", "message": "爬虫运行完成，请点击生成模型按钮生成模型"}
                    )
                logger.info(f"任务 {task_id} 已完成并更新状态")
            else:
                # 包括FAILURE状态和其他状态
                logger.info(f"Celery任务状态异常: {celery_task.info}")
                # 检查是否是worker崩溃的情况
                if (
                    isinstance(celery_task.info, dict)
                    and "pid" in celery_task.info
                    and "hostname" in celery_task.info
                ):
                    logger.error(f"Celery worker可能已崩溃: {celery_task.info}")
                    response = {
                        "status": "error",
                        "message": "Celery worker进程崩溃，请检查Celery worker日志",
                    }
                else:
                    response = {
                        "status": "error",
                        "message": str(celery_task.info)
                        if hasattr(celery_task, "info")
                        else "任务执行失败",
                    }
                # 更新任务状态
                task_status[task_id].update(
                    {"status": "error", "message": response["message"]}
                )
        except Exception as e:
            # 如果检查任务状态出现问题
            logger.error(f"检查Celery任务状态时出错: {str(e)}")
            response = {"status": "error", "message": f"检查任务状态时出错: {str(e)}"}
    else:
        response = task_info

    logger.info(f"返回任务状态: {response}")
    return jsonify(response)


# ... existing code ...
@app.route("/api/build-model/<task_id>", methods=["POST"])
def build_model(task_id):
    """
    根据任务ID构建模型（异步方式）
    """
    try:
        # 从任务状态中获取平台信息
        task_info = task_status.get(task_id)
        if not task_info:
            return jsonify({"success": False, "message": "任务不存在"}), 404

        # 获取平台信息
        platform = task_info.get("platform")
        logintype = task_info.get("logintype")
        crawlertype = task_info.get("crawlertype")
        session_id = task_info.get("session_id")

        if not platform or not logintype or not crawlertype:
            return jsonify({"success": False, "message": "任务信息不完整"}), 400

        # 查找处理后的数据文件
        processed_file_path = f"processed_{platform}_data.txt"

        if not os.path.exists(processed_file_path):
            return jsonify({"success": False, "message": "处理后的数据文件不存在"}), 400

        # 读取处理后的数据
        try:
            with open(processed_file_path, "r", encoding="utf-8") as f:
                processed_content = f.read()
        except Exception as e:
            return (
                jsonify({"success": False, "message": f"读取处理后的数据文件失败: {str(e)}"}),
                500,
            )

        if not processed_content:
            return jsonify({"success": False, "message": "没有有效的数据内容用于模型构建"}), 400

        # 创建临时文件用于模型构建
        temp_file_path = f"temp_{platform}_data.txt"
        try:
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(processed_content)

            model_name = platform + "_model"
            model_type = platform + "_model"

            # 异步执行模型构建任务，传递session_id
            from ai_celery import build_model_task

            task = build_model_task.delay(
                data_path=temp_file_path,
                model_name=model_name,
                model_type=model_type,
                session_id=session_id,
            )

            # 返回任务ID，前端可以轮询任务状态
            return jsonify(
                {"success": True, "message": "模型构建任务已提交", "task_id": task.id}
            )
        except Exception as e:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise e

    except Exception as e:
        logger.error(f"提交模型构建任务时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


# 添加一个新的端点用于通过上传的JSON文件构建模型
@app.route("/api/upload-and-build-model", methods=["POST"])
def upload_and_build_model():
    """
    通过上传的JSON文件构建模型（异步方式）
    """
    try:
        # 检查是否有文件上传
        if "file" not in request.files:
            return jsonify({"success": False, "message": "没有上传文件"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "message": "未选择文件"}), 400

        # 检查文件扩展名
        if not file.filename.endswith(".json"):
            return jsonify({"success": False, "message": "只支持JSON文件"}), 400

        # 获取平台类型
        platform = request.form.get("platform", "default")

        # 生成session_id用于组织模型文件
        session_id = f"upload_{int(time.time())}"

        # 保存上传的文件到临时位置
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file_path = os.path.join(temp_dir, file.filename)
        file.save(temp_file_path)

        # 使用上传的JSON文件异步构建模型
        model_name = platform + "_model"
        model_type = platform + "_model"

        from ai_celery import build_model_task

        task = build_model_task.delay(
            data_path=temp_file_path,
            model_name=model_name,
            model_type=model_type,
            session_id=session_id,
        )

        return jsonify({"success": True, "message": "模型构建任务已提交", "task_id": task.id})

    except Exception as e:
        logger.error(f"通过上传文件提交模型构建任务时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/build-model-status/<task_id>", methods=["GET"])
def get_build_model_status(task_id):
    """
    获取模型构建任务状态
    """
    try:
        from ai_celery import build_model_task

        task = build_model_task.AsyncResult(task_id)

        if task.state == "PENDING":
            # 任务等待中
            response = {"state": task.state, "status": "任务等待中"}
        elif task.state == "PROGRESS":
            # 任务进行中
            response = {"state": task.state, "status": "任务进行中"}
        elif task.state == "SUCCESS":
            # 任务成功完成
            response = {"state": task.state, "status": "任务完成", "result": task.info}
        elif task.state == "FAILURE":
            # 任务失败
            response = {"state": task.state, "status": "任务失败", "error": str(task.info)}
        else:
            # 其他状态
            response = {"state": task.state, "status": "未知状态"}

        return jsonify(response)
    except Exception as e:
        logger.error(f"获取模型构建任务状态时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/summarize", methods=["POST"])
def summarize():
    try:
        data = request.json
        model_name = data.get("model_name")

        # 异步执行内容总结任务
        from ai_celery import generate_summary_task

        platform = (
            model_name.replace("_model", "")
            if model_name.endswith("_model")
            else model_name
        )
        task = generate_summary_task.delay(platform)

        return jsonify({"success": True, "message": "内容总结任务已提交", "task_id": task.id})
    except Exception as e:
        logger.error(f"提交内容总结任务时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/summarize-status/<task_id>", methods=["GET"])
def get_summarize_status(task_id):
    """
    获取内容总结任务状态
    """
    try:
        from ai_celery import generate_summary_task

        task = generate_summary_task.AsyncResult(task_id)

        if task.state == "PENDING":
            # 任务等待中
            response = {"state": task.state, "status": "任务等待中"}
        elif task.state == "PROGRESS":
            # 任务进行中
            response = {"state": task.state, "status": "任务进行中"}
        elif task.state == "SUCCESS":
            # 任务成功完成
            response = {"state": task.state, "status": "任务完成", "result": task.info}
        elif task.state == "FAILURE":
            # 任务失败
            response = {"state": task.state, "status": "任务失败", "error": str(task.info)}
        else:
            # 其他状态
            response = {"state": task.state, "status": "未知状态"}

        return jsonify(response)
    except Exception as e:
        logger.error(f"获取内容总结任务状态时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/ask", methods=["POST"])
def ask_question():
    try:
        data = request.json
        question = data.get("question", "")
        model_name = data.get("model_name")

        # 确保平台名称正确
        if not model_name or model_name == "undefined":
            platform = "zhihu"  # 默认平台
        elif model_name.endswith("_model"):
            platform = model_name.replace("_model", "")
        else:
            platform = model_name

        # 异步执行问答任务，传递session_id
        from ai_celery import ask_question_task

        # 获取任务状态中的session_id
        session_id = None
        # 从任务状态中尝试获取session_id
        for task_info in task_status.values():
            if task_info.get("platform") == platform:
                session_id = task_info.get("session_id")
                break

        task = ask_question_task.delay(question, platform, session_id)

        return jsonify({"success": True, "message": "问答任务已提交", "task_id": task.id})
    except Exception as e:
        logger.error(f"提交问答任务时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/ask-status/<task_id>", methods=["GET"])
def get_ask_status(task_id):
    """
    获取问答任务状态
    """
    try:
        from ai_celery import ask_question_task

        task = ask_question_task.AsyncResult(task_id)

        if task.state == "PENDING":
            # 任务等待中
            response = {"state": task.state, "status": "任务等待中"}
        elif task.state == "PROGRESS":
            # 任务进行中
            response = {"state": task.state, "status": "任务进行中"}
        elif task.state == "SUCCESS":
            # 任务成功完成
            response = {"state": task.state, "status": "任务完成", "result": task.info}
        elif task.state == "FAILURE":
            # 任务失败
            response = {"state": task.state, "status": "任务失败", "error": str(task.info)}
        else:
            # 其他状态
            response = {"state": task.state, "status": "未知状态"}

        return jsonify(response)
    except Exception as e:
        logger.error(f"获取问答任务状态时出错: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


# 添加一个测试路由，确保API正常工作
@app.route("/api/test", methods=["GET"])
def test_api():
    return jsonify({"message": "API 正常工作!"})


@app.route("/api/download/<task_id>", methods=["GET"])
def download_result(task_id):
    """
    根据任务ID下载对应的爬虫结果文件
    """
    try:
        logger.info(f"Download request for task_id: {task_id}")

        # 首先尝试通过任务ID映射查找文件
        from main import task_file_mapping

        mapped_file = task_file_mapping.get(task_id)
        logger.info(f"Mapped file for task {task_id}: {mapped_file}")
        if mapped_file and os.path.exists(mapped_file):
            logger.info(f"Found mapped file for task {task_id}: {mapped_file}")
            return send_file(
                mapped_file,
                as_attachment=True,
                download_name=os.path.basename(mapped_file),
            )

        # 从任务状态中获取结果文件路径
        task_info = task_status.get(task_id)
        if task_info and "result_file" in task_info:
            result_file = task_info["result_file"]
            if os.path.exists(result_file):
                logger.info(f"Found result file from task info: {result_file}")
                # 更新映射以供下次快速查找
                task_file_mapping[task_id] = result_file
                return send_file(
                    result_file,
                    as_attachment=True,
                    download_name=os.path.basename(result_file),
                )

        # 如果没有映射或文件不存在，尝试查找会话特定的传输目录
        # 从任务状态中获取会话ID
        logger.info(f"Task info: {task_info}")
        if task_info and "session_id" in task_info:
            session_id = task_info["session_id"]
            session_transmit_dir = f"sessions/{session_id}/transmit_data"
            logger.info(f"Using session_id from task_info: {session_id}")
        else:
            # 回退到使用任务ID作为会话ID
            session_transmit_dir = f"sessions/{task_id}/transmit_data"
            logger.info(f"Using task_id as session_id: {task_id}")

        logger.info(f"Checking session transmit directory: {session_transmit_dir}")

        if os.path.exists(session_transmit_dir):
            logger.info(f"Found session transmit directory: {session_transmit_dir}")
            # 查找会话特定传输目录中的文件
            try:
                files_in_session_dir = os.listdir(session_transmit_dir)
                logger.info(
                    f"Files in session transmit directory: {files_in_session_dir}"
                )

                if files_in_session_dir:
                    # 优先查找与任务ID精确匹配的文件
                    for file in files_in_session_dir:
                        if task_id in file and file.endswith(".json"):
                            file_path = os.path.join(session_transmit_dir, file)
                            if os.path.exists(file_path):
                                logger.info(f"Found session-specific file: {file_path}")
                                # 更新映射以供下次快速查找
                                task_file_mapping[task_id] = file_path
                                return send_file(
                                    file_path,
                                    as_attachment=True,
                                    download_name=os.path.basename(file_path),
                                )

                    # 如果没有找到精确匹配的文件，返回最新的文件
                    file_times = []
                    for file in files_in_session_dir:
                        if file.endswith(".json"):
                            file_path = os.path.join(session_transmit_dir, file)
                            if os.path.exists(file_path):
                                file_times.append(
                                    (file_path, os.path.getmtime(file_path))
                                )

                    if file_times:
                        # 按修改时间排序，获取最新的文件
                        file_times.sort(key=lambda x: x[1], reverse=True)
                        file_path = file_times[0][0]
                        logger.info(
                            f"Found latest file in session directory: {file_path}"
                        )
                        # 更新映射以供下次快速查找
                        task_file_mapping[task_id] = file_path
                        return send_file(
                            file_path,
                            as_attachment=True,
                            download_name=os.path.basename(file_path),
                        )
            except Exception as e:
                logger.error(f"Error reading session transmit directory: {e}")
        else:
            logger.info(
                f"Session transmit directory does not exist: {session_transmit_dir}"
            )

        # 如果会话特定目录中没有找到，回退到原来的查找逻辑
        # 从任务状态中获取平台信息
        if not task_info:
            logger.error(f"Task not found: {task_id}")
            return jsonify({"success": False, "message": "任务不存在"}), 404

        # 获取平台信息
        platform = task_info.get("platform")
        logintype = task_info.get("logintype")
        crawlertype = task_info.get("crawlertype")

        logger.info(f"Task info - platform: {platform}, crawlertype: {crawlertype}")

        if not platform or not logintype or not crawlertype:
            logger.error(f"Incomplete task info for task_id: {task_id}")
            return jsonify({"success": False, "message": "任务信息不完整"}), 400

        # 查找传输目录中的文件
        transmit_dir = "transmit_data"
        logger.info(f"Checking default transmit directory: {transmit_dir}")
        if not os.path.exists(transmit_dir):
            logger.error(f"Transmit directory does not exist: {transmit_dir}")
            # 列出当前目录内容帮助调试
            try:
                current_dir_contents = os.listdir(".")
                logger.info(f"Current directory contents: {current_dir_contents}")
            except Exception as e:
                logger.error(f"Error listing current directory: {e}")
            # 尝试创建目录
            try:
                os.makedirs(transmit_dir, exist_ok=True)
                logger.info(f"Created transmit directory: {transmit_dir}")
            except Exception as e:
                logger.error(f"Failed to create transmit directory: {e}")
                return jsonify({"success": False, "message": "传输目录不存在且无法创建"}), 404

        # 查找与任务ID匹配的文件
        target_files = []
        for file in os.listdir(transmit_dir):
            if task_id in file and file.endswith(".json"):
                file_path = os.path.join(transmit_dir, file)
                target_files.append((file_path, os.path.getmtime(file_path)))

        # 如果没找到与任务ID匹配的文件，尝试查找与爬虫类型匹配的文件
        if not target_files:
            today = datetime.now().strftime("%Y-%m-%d")
            for file in os.listdir(transmit_dir):
                if (
                    file.startswith(f"{crawlertype}_")
                    and today in file
                    and file.endswith(".json")
                ):
                    file_path = os.path.join(transmit_dir, file)
                    target_files.append((file_path, os.path.getmtime(file_path)))

        # 如果仍然没找到文件
        if not target_files:
            all_files = os.listdir(transmit_dir) if os.path.exists(transmit_dir) else []
            logger.error(f"No matching files found. Files in transmit_dir: {all_files}")
            return (
                jsonify(
                    {"success": False, "message": f"未找到传输文件。传输目录中的文件: {all_files}"}
                ),
                404,
            )

        # 按修改时间排序，获取最新的文件
        target_files.sort(key=lambda x: x[1], reverse=True)
        file_path = target_files[0][0]
        logger.info(f"Found file for download: {file_path}")

        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return jsonify({"success": False, "message": "传输后的文件不存在"}), 404

        # 提供文件下载
        logger.info(f"Sending file: {file_path}")
        # 更新映射以供下次快速查找
        task_file_mapping[task_id] = file_path
        return send_file(
            file_path, as_attachment=True, download_name=os.path.basename(file_path)
        )
    except Exception as e:
        logger.error(f"下载文件时出错: {str(e)}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/qrcode/<task_id>", methods=["GET"])
def get_qr_code(task_id):
    """
    根据任务ID获取二维码
    """
    try:
        logger.info(f"尝试获取任务 {task_id} 的二维码")
        logger.info(f"任务ID类型: {type(task_id)}")

        # 显示当前存储的所有任务ID（调试用）
        logger.info(f"当前qr_code_storage中的任务: {list(qr_code_storage.keys())}")

        # 检查是否有存储的二维码数据
        qr_code_data = get_stored_qr_code(task_id)
        logger.info(f"任务 {task_id} 的二维码数据: {'存在' if qr_code_data else '不存在'}")

        if qr_code_data:
            logger.info(
                f"成功获取任务 {task_id} 的二维码，长度: {len(qr_code_data) if qr_code_data else 0}"
            )
            return jsonify(
                {"success": True, "qrcode": qr_code_data, "message": "二维码获取成功"}
            )
        else:
            logger.info(f"任务 {task_id} 的二维码仍在生成中")
            return jsonify({"success": False, "message": "二维码正在生成中，请稍候..."}), 400

    except Exception as e:
        logger.error(f"获取二维码时出错: {str(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "message": str(e)}), 500


def store_qr_code(task_id, qr_code_data):
    """
    存储二维码数据
    """
    qr_code_storage[task_id] = qr_code_data
    logger.info(
        f"已存储任务 {task_id} 的二维码数据，存储大小: {len(qr_code_data) if qr_code_data else 0} 字符"
    )


def get_stored_qr_code(task_id):
    """
    获取存储的二维码数据
    """
    qr_data = qr_code_storage.get(task_id)
    logger.info(
        f"获取任务 {task_id} 的二维码数据: {'存在' if qr_data else '不存在'}，存储大小: {len(qr_data) if qr_data else 0} 字符"
    )
    return qr_data


@app.route("/api/store-qr-code", methods=["POST"])
def store_qr_code_endpoint():
    """
    用于接收爬虫发送的二维码数据
    """
    try:
        data = request.json
        task_id = data.get("task_id")
        qr_code_data = data.get("qr_code_data")

        logger.info(
            f"收到二维码存储请求 - task_id: {task_id}, 数据大小: {len(qr_code_data) if qr_code_data else 0}"
        )

        if not task_id or not qr_code_data:
            logger.warning(f"存储二维码失败: 缺少task_id或qr_code_data")
            return (
                jsonify(
                    {"success": False, "message": "Missing task_id or qr_code_data"}
                ),
                400,
            )

        # 存储二维码数据
        store_qr_code(task_id, qr_code_data)
        logger.info(f"通过API成功存储了任务 {task_id} 的二维码数据，大小: {len(qr_code_data)} 字符")

        return jsonify({"success": True, "message": "QR code stored successfully"})
    except Exception as e:
        logger.error(f"通过API存储二维码时出错: {str(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    # 使用环境变量配置应用
    try:
        # 确定要排除监控的文件
        excluded_files = [
            os.path.join(
                os.path.dirname(__file__), "crawler", "config", "base_config.py"
            )
        ]

        # 启动应用，排除特定文件的监控
        app.run(
            debug=DEBUG, port=PORT, host=HOST, threaded=True, extra_files=excluded_files
        )
    except SystemExit:
        logger.info("应用正常退出")
    except Exception as e:
        logger.error(f"应用运行出错: {str(e)}")
