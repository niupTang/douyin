# -*- coding: utf-8 -*-
"""
太阳鸟自媒体自动化运营系统 - 桌面版启动器

双击 start_desktop.bat 即可打开桌面窗口，无需手动开终端。
流程：拉起后端(5409) + 前端静态服务(5173) -> WebView2 窗口加载前端
      -> 关闭窗口时自动清理全部子进程。

依赖：系统 Python(D:\\python) 已装好项目依赖，pip install pywebview 一次即可。
"""

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

PROJECT_DIR = Path(r"E:\social-auto-upload")
PYTHON = r"D:\python\python.exe"
FRONTEND_DIR = PROJECT_DIR / "sau_frontend" / "dist"
LOG_DIR = PROJECT_DIR / "desktop" / "logs"
BACKEND_PORT = 5409
FRONTEND_PORT = 5173
APP_TITLE = "太阳鸟自媒体自动化运营系统"
APP_URL = f"http://127.0.0.1:{FRONTEND_PORT}"
STARTUP_TIMEOUT = 90  # 秒


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_DIR / "launcher.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_port(port, timeout=STARTUP_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_in_use(port):
            return True
        time.sleep(0.5)
    return False


def make_env():
    """净化环境变量，规避 Playwright 的两个已知坑（详见项目 memory）。"""
    env = dict(os.environ)
    env.pop("NODE_OPTIONS", None)
    env.pop("PLAYWRIGHT_BROWSERS_PATH", None)
    return env


def start_backend(env):
    if port_in_use(BACKEND_PORT):
        log(f"后端端口 {BACKEND_PORT} 已被占用，复用现有实例（可能不是本启动器启动的）")
        return None
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out = open(LOG_DIR / "backend.log", "ab")
    log(f"启动后端: {PYTHON} sau_koubo_server.py (port {BACKEND_PORT})")
    proc = subprocess.Popen(
        [PYTHON, "sau_koubo_server.py"],
        cwd=str(PROJECT_DIR),
        env=env,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if not wait_port(BACKEND_PORT):
        log("后端启动超时，请查看 desktop/logs/backend.log")
        return None
    log("后端就绪")
    return proc


def start_frontend(env):
    if port_in_use(FRONTEND_PORT):
        log(f"前端端口 {FRONTEND_PORT} 已被占用，复用现有实例")
        return None
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out = open(LOG_DIR / "frontend.log", "ab")
    log(f"启动前端静态服务: http.server {FRONTEND_PORT} (serving {FRONTEND_DIR})")
    proc = subprocess.Popen(
        [PYTHON, "-m", "http.server", str(FRONTEND_PORT), "--bind", "127.0.0.1"],
        cwd=str(FRONTEND_DIR),
        env=env,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if not wait_port(FRONTEND_PORT):
        log("前端服务启动超时")
        return None
    log("前端就绪")
    return proc


def kill_tree(proc):
    """连同子进程树一起结束，避免 Playwright node driver 变孤儿进程。"""
    if proc is None or proc.poll() is not None:
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            timeout=10,
        )
    except Exception as e:
        log(f"结束进程 {proc.pid} 失败: {e}")


def main():
    if not Path(PYTHON).exists():
        log(f"找不到 Python: {PYTHON}")
        input("按回车退出...")
        return 1
    if not FRONTEND_DIR.exists():
        log(f"前端构建目录不存在: {FRONTEND_DIR}")
        input("按回车退出...")
        return 1

    env = make_env()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log("=" * 40)
    log("桌面版启动器开始运行")

    # 端口已被占用说明服务可能在跑，先确认后端能通
    backend_alive = port_in_use(BACKEND_PORT)
    backend = start_backend(env)
    frontend = start_frontend(env)

    # 启动 WebView2 窗口（无窗口服务也已就绪后再打开）
    import webview

    log(f"打开桌面窗口: {APP_TITLE} -> {APP_URL}")
    window = webview.create_window(
        APP_TITLE,
        APP_URL,
        width=1440,
        height=900,
        min_size=(1100, 700),
        background_color="#1e293b",
    )
    try:
        webview.start()
    except Exception as e:
        log(f"窗口异常退出: {e}")
    finally:
        log("窗口已关闭，清理子进程...")
        # 只清理本启动器拉起的进程；复用已有实例的不动
        if not backend_alive:
            kill_tree(backend)
        if frontend is not None:
            kill_tree(frontend)
        log("已退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
