#!/usr/bin/env python3
"""Verify the native Windows desktop delivery without changing project state."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def _check_files() -> None:
    required = (
        "desktop_launcher.py",
        "desktop_qt_app.py",
        "start_desktop.cmd",
        "assets/contour-control-tool.ico",
        "assets/icon-folder.png",
        "models/depth_anything_v2_vits.pth",
    )
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        _fail("缺少交付文件：" + ", ".join(missing))
    print(f"PASS: required files ({len(required)})")


def _check_compile() -> None:
    files = (
        "desktop_launcher.py",
        "desktop_qt_app.py",
        "depth_video_converter.py",
        "depth_converter/__init__.py",
        "depth_converter/core.py",
        "depth_converter/ffmpeg.py",
        "depth_converter/models.py",
        "depth_converter/smoothing.py",
    )
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", *files],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        _fail(result.stderr.strip() or "Python 编译检查失败")
    print(f"PASS: Python compile ({len(files)})")


def _check_core() -> None:
    sys.path.insert(0, str(ROOT))
    from depth_converter import MODEL_DEFS, MODELS_DIR, RESOLUTION_PRESETS, ffmpeg_available

    expected_models = {
        "Small (fastest, ~95 MB)",
        "Base (balanced, ~372 MB)",
        "Large (best quality, ~1.2 GB)",
    }
    if set(MODEL_DEFS) != expected_models:
        _fail(f"模型菜单不完整：{sorted(MODEL_DEFS)}")
    if not RESOLUTION_PRESETS:
        _fail("分辨率预设为空")
    if not ffmpeg_available():
        _fail("FFmpeg 不可用")
    small_model = ROOT / "models" / "depth_anything_v2_vits.pth"
    if not small_model.is_file() or small_model.stat().st_size < 50_000_000:
        _fail("Small 模型文件不存在或明显不完整")
    print(f"PASS: core, FFmpeg, model cache ({MODELS_DIR})")


def _check_ui() -> None:
    code = """
from PySide6.QtWidgets import QApplication
from desktop_qt_app import ContourControlWindow, MODEL_DEFS, WINDOW_HEIGHT, WINDOW_WIDTH
app = QApplication([])
window = ContourControlWindow()
assert window.width() == WINDOW_WIDTH, (window.width(), WINDOW_WIDTH)
assert window.height() == WINDOW_HEIGHT, (window.height(), WINDOW_HEIGHT)
assert len(MODEL_DEFS) == 3, MODEL_DEFS
assert window.model_combo.count() == 3, window.model_combo.count()
window.close()
app.quit()
print('UI_OK')
"""
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode or "UI_OK" not in result.stdout:
        _fail(result.stderr.strip() or result.stdout.strip() or "Qt 界面自检失败")
    print("PASS: native PySide6 window (1110x852, 3 models)")


def _check_launcher() -> None:
    launcher = (ROOT / "start_desktop.cmd").read_text(encoding="utf-8-sig")
    required_fragments = ("venv\\Scripts\\pythonw.exe", "desktop_launcher.py")
    if any(fragment not in launcher for fragment in required_fragments):
        _fail("start_desktop.cmd 未指向稳定桌面入口")
    print("PASS: Windows launcher entry")


def main() -> int:
    print(f"Checking native delivery: {ROOT}")
    _check_files()
    _check_compile()
    _check_core()
    _check_ui()
    _check_launcher()
    print("PASS: native desktop delivery is ready for local/venv distribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
