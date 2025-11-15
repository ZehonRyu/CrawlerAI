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
    imports=("crawler_celery",),
)


# 定义任务
@celery_app.task(bind=True, name="crawler_celery.run_crawler_internal")
def run_crawler_internal(
    self,
    logintype: str,
    platform: str,
    crawlertype: str,
    url: str = None,
    task_type: str = None,
):
    """运行爬虫的Celery任务"""
    # 导入main模块并执行函数
    import main

    return main.run_crawler_internal(
        self, logintype, platform, crawlertype, url, task_type
    )


# 确保任务被导出
__all__ = ["celery_app", "run_crawler_internal"]

# 打印可用任务列表以供调试
logger.info("Available tasks: %s", list(celery_app.tasks.keys()))
logger.info(
    "Task 'crawler_celery.run_crawler_internal' registered: %s",
    "crawler_celery.run_crawler_internal" in celery_app.tasks,
)

if __name__ == "__main__":
    celery_app.start()
