import os
import signal
import subprocess
import sys
import time

import redis


def check_redis():
    """检查Redis是否运行"""
    try:
        r = redis.Redis(host="localhost", port=6379, db=0, socket_connect_timeout=1)
        r.ping()
        print("✓ Redis服务器正在运行")
        return True
    except:
        print("✗ Redis服务器未运行，请先启动Redis")
        return False


def start_celery_worker(app_name, log_level="info"):
    """启动Celery worker"""
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                app_name,
                "worker",
                f"--loglevel={log_level}",
                "--pool=solo",
                "--without-gossip",
                "--without-mingle",
            ]
        )
        print(f"✓ {app_name} worker已启动 (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"✗ 启动{app_name} worker失败: {e}")
        return None


def start_flask_app():
    """启动Flask应用"""
    try:
        process = subprocess.Popen([sys.executable, "app.py"])
        print(f"✓ Flask应用已启动 (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"✗ 启动Flask应用失败: {e}")
        return None


def main():
    """主函数"""
    print("=== 启动所有服务 ===")

    # 检查Redis
    if not check_redis():
        return

    processes = []

    try:
        # 启动爬虫worker
        print("\n正在启动爬虫worker...")
        crawler_process = start_celery_worker("crawler_celery")
        if crawler_process:
            processes.append(crawler_process)
            time.sleep(3)  # 等待worker启动

        # 启动AI worker
        print("\n正在启动AI worker...")
        ai_process = start_celery_worker("ai_celery")
        if ai_process:
            processes.append(ai_process)
            time.sleep(3)  # 等待worker启动

        # 启动Flask应用
        print("\n正在启动Flask应用...")
        flask_process = start_flask_app()
        if flask_process:
            processes.append(flask_process)

        if not processes:
            print("没有成功启动任何服务")
            return

        print("\n=== 所有服务已启动 ===")
        print("按Ctrl+C停止所有服务")

        # 等待所有进程
        try:
            for process in processes:
                if process:
                    process.wait()
        except KeyboardInterrupt:
            print("\n\n正在停止所有服务...")
            for process in processes:
                if process and process.poll() is None:
                    process.terminate()

            # 等待进程结束
            for process in processes:
                if process:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

            print("所有服务已停止")

    except Exception as e:
        print(f"启动过程中出现错误: {e}")
        # 清理已启动的进程
        for process in processes:
            if process and process.poll() is None:
                process.terminate()
        sys.exit(1)


if __name__ == "__main__":
    main()
