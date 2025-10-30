import os
import sys

from celery import Celery

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"ai_celery.py 被导入，Python路径: {sys.path}")

# 创建Celery实例
ai_celery_app = Celery("ai_celery")
print("Celery实例已创建")

# 配置
ai_celery_app.conf.update(
    broker_url="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_pool="solo" if sys.platform == "win32" else "prefork",
)

# 导入任务函数
try:
    print("正在导入AI模块...")
    from AI.AI_rag.build_model import build_and_save_model
    from AI.AI_rag.use_model import ask_question, generate_summary

    print("AI模块导入成功")
except Exception as e:
    print(f"导入AI模块失败: {e}")
    raise


@ai_celery_app.task(bind=True)
def build_model_task(
    self,
    data_path: str,
    model_name: str = "default_model",
    model_type: str = "default_model",
    session_id: str = None,
):
    print(
        f"执行build_model_task: data_path={data_path}, model_name={model_name}, session_id={session_id}"
    )
    try:
        build_and_save_model(
            data_path=data_path,
            model_name=model_name,
            model_type=model_type,
            session_id=session_id,
        )
        return {
            "status": "success",
            "message": f"模型 {model_name} 构建成功",
            "model_name": model_name,
            "session_id": session_id,
        }
    except Exception as exc:
        self.update_state(
            state="FAILURE",
            meta={"exc_type": type(exc).__name__, "exc_message": str(exc)},
        )
        raise


@ai_celery_app.task(bind=True)
def generate_summary_task(self, platform: str, session_id: str = None):
    print(f"执行generate_summary_task: platform={platform}, session_id={session_id}")
    try:
        summary = generate_summary(platform, session_id)
        return {
            "status": "success",
            "summary": summary,
            "platform": platform,
            "session_id": session_id,
        }
    except Exception as exc:
        self.update_state(
            state="FAILURE",
            meta={"exc_type": type(exc).__name__, "exc_message": str(exc)},
        )
        raise


@ai_celery_app.task(bind=True)
def ask_question_task(self, question: str, platform: str, session_id: str = None):
    print(
        f"执行ask_question_task: question={question}, platform={platform}, session_id={session_id}"
    )
    try:
        answer = ask_question(question, platform, session_id)
        return {
            "status": "success",
            "answer": answer,
            "question": question,
            "platform": platform,
            "session_id": session_id,
        }
    except Exception as exc:
        self.update_state(
            state="FAILURE",
            meta={"exc_type": type(exc).__name__, "exc_message": str(exc)},
        )
        raise


print("所有任务已定义")
