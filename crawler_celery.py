import logging
import os
import sys

from celery import Celery

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 创建Celery实例
celery_app = Celery("crawler_tasks")

# 使用环境变量配置Redis URL，如果没有设置则使用默认值
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
    # 添加worker配置
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    # Windows兼容性配置
    worker_pool="solo" if sys.platform == "win32" else "prefork",
    # 确保任务可以被worker识别
    imports=("main",),
)

# 不要在这里直接导入任务，避免循环导入
# 我们会在worker启动时导入

if __name__ == "__main__":
    # 启动worker时导入任务模块
    from main import run_crawler_internal

    celery_app.start()
