#!/usr/bin/env python3
"""Desktop entry point for the packaged Depth Video Converter app."""

from __future__ import annotations

import ctypes
import json
import multiprocessing
import os
import socket
import subprocess
import sys
import traceback
import urllib.request
import webbrowser
from pathlib import Path


APP_TITLE = "深度视频转换器"
APP_DIR_NAME = "DepthVideoConverter"
DEFAULT_PORT = 7860


def _user_data_dir() -> Path:
    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / APP_DIR_NAME


def _configure_runtime(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    models_dir = data_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("DEPTH_MODELS_DIR", str(models_dir))
    os.environ["DEPTH_DESKTOP_MODE"] = "1"
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    os.environ["no_proxy"] = "127.0.0.1,localhost"

    log_path = data_dir / "launcher.log"
    if sys.stdout is None:
        sys.stdout = log_path.open("a", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = log_path.open("a", encoding="utf-8", buffering=1)


def _server_title(port: int) -> str | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/config", timeout=0.75) as response:
            payload = json.load(response)
        return payload.get("title")
    except Exception:
        return None


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _find_port(start: int) -> int:
    for port in range(start, start + 20):
        if _port_is_free(port):
            return port
    raise RuntimeError("没有可用的本地端口，请关闭其他本地服务后重试。")


def _show_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)
        return
    if sys.platform == "darwin":
        script = (
            'on run argv\n'
            'display alert "深度视频转换器无法启动" message (item 1 of argv) as critical\n'
            'end run'
        )
        subprocess.run(["osascript", "-e", script, message], check=False)


def main() -> None:
    multiprocessing.freeze_support()
    data_dir = _user_data_dir()
    _configure_runtime(data_dir)

    requested_port = int(os.environ.get("DEPTH_PORT", str(DEFAULT_PORT)))
    for port in range(requested_port, requested_port + 20):
        if _server_title(port) == APP_TITLE:
            webbrowser.open(f"http://127.0.0.1:{port}/")
            return

    try:
        port = _find_port(requested_port)
        from depth_video_converter import create_ui
        from gradio import utils as gradio_utils

        gradio_utils.JSON_PATH = str(data_dir / "gradio-launches.json")
        demo = create_ui()
        demo.launch(
            server_name="127.0.0.1",
            server_port=port,
            share=False,
            show_error=True,
            inbrowser=os.environ.get("DEPTH_NO_BROWSER") != "1",
        )
    except Exception as exc:
        traceback.print_exc()
        _show_error(f"{type(exc).__name__}: {exc}\n\n日志位置：{data_dir / 'launcher.log'}")
        raise


if __name__ == "__main__":
    main()
