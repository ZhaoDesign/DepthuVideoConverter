#!/usr/bin/env python3
"""Desktop entry point for the packaged Depth Video Converter app."""

from __future__ import annotations

import ctypes
import json
import multiprocessing
import os
import signal
import socket
import subprocess
import sys
import time
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


def _open_interface(port: int) -> None:
    webbrowser.open(f"http://127.0.0.1:{port}/")


def _request_remote_shutdown(port: int) -> bool:
    body = json.dumps({"data": []}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    for route in ("/run/_shutdown_desktop_app", "/api/_shutdown_desktop_app"):
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{route}",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=1.5):
                return True
        except Exception:
            continue
    return False


def _terminate_listening_process(port: int) -> None:
    own_pid = os.getpid()
    pids: set[int] = set()

    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=creationflags,
        )
        for line in result.stdout.splitlines():
            columns = line.split()
            if len(columns) >= 5 and columns[1].endswith(f":{port}") and columns[3].upper() == "LISTENING":
                try:
                    pids.add(int(columns[4]))
                except ValueError:
                    pass
        for pid in pids:
            if pid != own_pid:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=creationflags,
                )
        return

    result = subprocess.run(
        ["lsof", "-nP", f"-tiTCP:{port}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        try:
            pids.add(int(line.strip()))
        except ValueError:
            pass

    for pid in pids:
        if pid == own_pid:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    time.sleep(0.5)
    for pid in pids:
        if pid == own_pid:
            continue
        try:
            os.kill(pid, 0)
        except OSError:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _show_macos_controller_window(port: int, owns_server: bool) -> bool:
    try:
        import objc
        from AppKit import (
            NSAlert,
            NSAlertFirstButtonReturn,
            NSApplication,
            NSApplicationActivationPolicyRegular,
            NSBackingStoreBuffered,
            NSBezelStyleRounded,
            NSButton,
            NSColor,
            NSFont,
            NSMakeRect,
            NSObject,
            NSTextField,
            NSView,
            NSWindow,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskMiniaturizable,
            NSWindowStyleMaskTitled,
        )
    except Exception:
        return False

    class ControllerDelegate(NSObject):
        def initWithPort_ownsServer_(self, app_port: int, app_owns_server: bool):
            self = objc.super(ControllerDelegate, self).init()
            if self is None:
                return None
            self.port = int(app_port)
            self.owns_server = bool(app_owns_server)
            self.window = None
            return self

        def showWindow(self) -> None:
            if self.window is not None:
                self.window.makeKeyAndOrderFront_(None)
                self.window.orderFrontRegardless()
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

        def openInterface_(self, sender) -> None:
            _open_interface(self.port)
            self.showWindow()

        def quitApp_(self, sender) -> None:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("彻底退出本地后台？")
            alert.setInformativeText_("退出后，网页操作页面也会停止运行。")
            alert.addButtonWithTitle_("退出")
            alert.addButtonWithTitle_("取消")
            if alert.runModal() != NSAlertFirstButtonReturn:
                return
            if not self.owns_server:
                if not _request_remote_shutdown(self.port):
                    _terminate_listening_process(self.port)
            os._exit(0)

        def windowShouldClose_(self, sender) -> bool:
            self.quitApp_(sender)
            return False

        def applicationShouldHandleReopen_hasVisibleWindows_(self, application, has_visible_windows) -> bool:
            self.showWindow()
            return True

        def applicationDidFinishLaunching_(self, notification) -> None:
            self.showWindow()

    try:
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        delegate = ControllerDelegate.alloc().initWithPort_ownsServer_(port, owns_server)
        app.setDelegate_(delegate)

        width = 440
        height = 230
        style_mask = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, width, height),
            style_mask,
            NSBackingStoreBuffered,
            False,
        )
        window.setTitle_(APP_TITLE)
        window.setReleasedWhenClosed_(False)
        window.setBackgroundColor_(NSColor.windowBackgroundColor())
        window.center()
        window.setDelegate_(delegate)
        delegate.window = window

        content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        window.setContentView_(content)

        title = NSTextField.labelWithString_("深度视频转换器正在运行")
        title.setFrame_(NSMakeRect(24, 158, 392, 26))
        title.setFont_(NSFont.boldSystemFontOfSize_(16))
        title.setTextColor_(NSColor.labelColor())
        content.addSubview_(title)

        status = NSTextField.labelWithString_("网页界面由本机后台提供，关闭浏览器后仍可从这里重新打开。")
        status.setFrame_(NSMakeRect(24, 112, 392, 40))
        status.setFont_(NSFont.systemFontOfSize_(13))
        status.setTextColor_(NSColor.secondaryLabelColor())
        status.setLineBreakMode_(0)
        status.setUsesSingleLineMode_(False)
        content.addSubview_(status)

        address = NSTextField.labelWithString_(f"http://127.0.0.1:{port}")
        address.setFrame_(NSMakeRect(24, 86, 392, 20))
        address.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12, 0))
        address.setTextColor_(NSColor.controlAccentColor())
        content.addSubview_(address)

        open_button = NSButton.buttonWithTitle_target_action_("打开操作页面", delegate, "openInterface:")
        open_button.setFrame_(NSMakeRect(24, 28, 132, 34))
        open_button.setBezelStyle_(NSBezelStyleRounded)
        content.addSubview_(open_button)

        quit_button = NSButton.buttonWithTitle_target_action_("彻底退出应用", delegate, "quitApp:")
        quit_button.setFrame_(NSMakeRect(284, 28, 132, 34))
        quit_button.setBezelStyle_(NSBezelStyleRounded)
        content.addSubview_(quit_button)

        app.finishLaunching()
        delegate.showWindow()
        app.run()
        return True
    except Exception:
        traceback.print_exc()
        return False


def _show_tk_controller_window(port: int, owns_server: bool) -> bool:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        return False

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("420x220")
    root.minsize(400, 200)
    root.resizable(False, False)
    root.configure(bg="#F5F6F7")

    def focus_window() -> None:
        root.deiconify()
        root.lift()
        root.focus_force()

    if sys.platform == "darwin":
        try:
            root.createcommand("tk::mac::ReopenApplication", focus_window)
        except Exception:
            pass

    frame = tk.Frame(root, bg="#F5F6F7", padx=20, pady=20)
    frame.pack(fill="both", expand=True)

    title = tk.Label(
        frame,
        text="深度视频转换器正在运行",
        bg="#F5F6F7",
        fg="#1F2937",
        font=("Helvetica", 16, "bold"),
        anchor="w",
    )
    title.pack(fill="x")
    status = tk.Label(
        frame,
        text="网页界面已由本地后台提供，可随时重新打开。",
        bg="#F5F6F7",
        fg="#4B5563",
        justify="left",
        anchor="w",
        wraplength=360,
    )
    status.pack(fill="x", pady=(10, 0))
    address = tk.Label(
        frame,
        text=f"http://127.0.0.1:{port}",
        bg="#F5F6F7",
        fg="#2563EB",
        anchor="w",
    )
    address.pack(fill="x", pady=(8, 0))

    buttons = tk.Frame(frame, bg="#F5F6F7")
    buttons.pack(fill="x", pady=(18, 0))

    def quit_app() -> None:
        if not messagebox.askyesno(APP_TITLE, "确定要彻底退出本地后台吗？"):
            return
        if not owns_server:
            if not _request_remote_shutdown(port):
                _terminate_listening_process(port)
        os._exit(0)

    open_button = tk.Button(
        buttons,
        text="打开操作页面",
        command=lambda: _open_interface(port),
        bg="#E5E7EB",
        fg="#111827",
        activebackground="#D1D5DB",
        activeforeground="#111827",
        relief="flat",
        padx=14,
        pady=8,
        highlightthickness=0,
    )
    open_button.pack(side="left")
    quit_button = tk.Button(
        buttons,
        text="彻底退出应用",
        command=quit_app,
        bg="#DCFCE7",
        fg="#14532D",
        activebackground="#BBF7D0",
        activeforeground="#14532D",
        relief="flat",
        padx=14,
        pady=8,
        highlightthickness=0,
    )
    quit_button.pack(side="right")

    root.protocol("WM_DELETE_WINDOW", quit_app)
    focus_window()
    root.update_idletasks()
    root.after(50, focus_window)
    root.mainloop()
    return True


def _show_controller_window(port: int, owns_server: bool) -> bool:
    if sys.platform == "darwin" and _show_macos_controller_window(port, owns_server):
        return True
    return _show_tk_controller_window(port, owns_server)


def main() -> None:
    multiprocessing.freeze_support()
    data_dir = _user_data_dir()
    _configure_runtime(data_dir)

    requested_port = int(os.environ.get("DEPTH_PORT", str(DEFAULT_PORT)))
    for port in range(requested_port, requested_port + 20):
        if _server_title(port) == APP_TITLE:
            _open_interface(port)
            _show_controller_window(port, owns_server=False)
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
            inbrowser=False,
            prevent_thread_lock=True,
        )
        if os.environ.get("DEPTH_NO_BROWSER") != "1":
            _open_interface(port)
        if not _show_controller_window(port, owns_server=True):
            demo.block_thread()
    except Exception as exc:
        traceback.print_exc()
        _show_error(f"{type(exc).__name__}: {exc}\n\n日志位置：{data_dir / 'launcher.log'}")
        raise


if __name__ == "__main__":
    main()
