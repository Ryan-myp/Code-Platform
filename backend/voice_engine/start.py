#!/usr/bin/env python3
"""启动 voice_engine（CosyVoice2 推理服务，端口 9888）
用法: python3 start.py [stop|restart|status]
"""
import os
import signal
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_PY = "/Users/yanping.ma/ai-models/cv-venv/bin/python"
LOG = "/tmp/voice_engine.log"
PID_FILE = "/tmp/voice_engine.pid"
PORT = 9888


def get_pid():
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            return int(f.read().strip())
    return None


def is_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def status():
    pid = get_pid()
    if is_alive(pid):
        print(f"voice_engine RUNNING pid={pid} port={PORT}")
        return 0
    print("voice_engine STOPPED")
    return 1


def stop():
    pid = get_pid()
    if is_alive(pid):
        os.kill(pid, signal.SIGTERM)
        print(f"voice_engine stopped pid={pid}")
    else:
        print("voice_engine not running")


def start():
    if is_alive(get_pid()):
        print("voice_engine already running")
        return
    env = dict(os.environ)
    env["PYTHONPATH"] = "/Users/yanping.ma/ai-models/CosyVoice"
    with open(LOG, "ab") as log:
        p = subprocess.Popen(
            [VENV_PY, os.path.join(ROOT, "server.py")],
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
            cwd=ROOT,
        )
    with open(PID_FILE, "w") as f:
        f.write(str(p.pid))
    print(f"voice_engine started pid={p.pid} port={PORT} log={LOG}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        stop()
        start()
    elif cmd == "status":
        sys.exit(status())
    else:
        print("usage: python3 start.py [start|stop|restart|status]")
