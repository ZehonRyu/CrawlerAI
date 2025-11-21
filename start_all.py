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


def start_celery_worker_direct():
    """直接启动Celery worker，显式包含模块"""
    try:
        # 构建完整的命令行参数
        cmd = [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "crawler_celery",
            "worker",
            "--loglevel=info",
            "--pool=solo",  # Windows兼容性
            "--without-gossip",
            "--without-mingle",
        ]

        # 设置环境变量确保模块可以被正确导入
        env = os.environ.copy()
        project_root = os.path.dirname(os.path.abspath(__file__))

        # 添加项目根目录到PYTHONPATH
        current_pythonpath = env.get("PYTHONPATH", "")
        if current_pythonpath:
            env["PYTHONPATH"] = project_root + os.pathsep + current_pythonpath
        else:
            env["PYTHONPATH"] = project_root

        print(f"使用PYTHONPATH: {env['PYTHONPATH']}")
        print(f"执行命令: {' '.join(cmd)}")

        process = subprocess.Popen(cmd, env=env, cwd=project_root)
        print(f"✓ crawler_celery worker已启动 (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"✗ 启动crawler_celery worker失败: {e}")
        import traceback

        traceback.print_exc()
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
        crawler_process = start_celery_worker_direct()
        if crawler_process:
            processes.append(crawler_process)
            time.sleep(5)  # 增加等待时间确保worker完全启动

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

    except Exception as e:
        print(f"启动过程中出现错误: {e}")
        import traceback

        traceback.print_exc()
        # 清理已启动的进程
        for process in processes:
            if process and process.poll() is None:
                process.terminate()
        sys.exit(1)


if __name__ == "__main__":
    main()
