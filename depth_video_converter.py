#!/usr/bin/env python3
"""
Depth Video Converter — Convert any video to a depth-map video using Depth Anything V2.

Features:
  - Gradio Web UI with MP4 / MOV upload
  - Depth Anything V2 (Small / Base / Large) — local .pth checkpoints
  - Auto-detect NVIDIA CUDA, Apple Silicon MPS, or fallback to CPU
  - Model size selection, output resolution, black/white inversion
  - Temporal smoothing (exponential moving average) to reduce flicker
  - Optional original audio preservation (requires ffmpeg)
  - Export as H.264 MP4 (via ffmpeg pipe)

Author: Claude Code
License: MIT
"""

from __future__ import annotations

import os
import sys
import threading

import gradio as gr
import torch

# Shared core library — all domain logic lives here
from depth_converter import (
    MODEL_DEFS,
    MODELS_DIR,
    detect_device,
    ffmpeg_available,
    process_video,
)


# ---------------------------------------------------------------------------
# Gradio adapter — catch RuntimeError and re-raise as gr.Error for the UI
# ---------------------------------------------------------------------------

CLOSE_TAB_CONFIRM_HEAD = """
<script>
(() => {
    window.addEventListener("beforeunload", (event) => {
        event.preventDefault();
        event.returnValue = "";
    });
})();
</script>
"""


def _is_desktop_mode() -> bool:
    return os.environ.get("DEPTH_DESKTOP_MODE") == "1"

def _process_video_for_gradio(
    input_video_path: str,
    model_size_label: str,
    resolution_choice: str,
    invert_bw: bool,
    smoothing_strength: float,
    preserve_audio: bool,
    progress: gr.Progress = gr.Progress(),
) -> str:
    """Call the shared processor and expose errors through the Gradio UI."""
    try:
        return process_video(
            input_video_path=input_video_path,
            model_size_label=model_size_label,
            resolution_choice=resolution_choice,
            invert_bw=invert_bw,
            smoothing_strength=smoothing_strength,
            preserve_audio=preserve_audio,
            progress=progress,
        )
    except RuntimeError as e:
        raise gr.Error(str(e))


def _shutdown_desktop_app() -> None:
    """Stop the packaged desktop process after Gradio sends the click response."""
    gr.Info("应用正在退出…")
    _schedule_desktop_shutdown()


def _shutdown_desktop_app_from_browser_close() -> None:
    """Stop the packaged desktop process after the browser tab is closed."""
    _schedule_desktop_shutdown(delay=0.35)


def _schedule_desktop_shutdown(delay: float = 0.75) -> None:
    timer = threading.Timer(delay, lambda: os._exit(0))
    timer.daemon = True
    timer.start()


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

CSS = """
.gradio-container { max-width: 720px !important; margin: 0 auto; }
.device-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 0.85em;
    font-weight: 600;
    margin: 8px 0;
}
.device-cuda { background: #76b900; color: #fff; }
.device-mps  { background: #0071e3; color: #fff; }
.device-cpu  { background: #e0e0e0; color: #333; }
"""


def create_ui() -> gr.Blocks:
    device_str, device_desc = detect_device()
    badge_class = {"cuda": "device-cuda", "mps": "device-mps"}.get(device_str, "device-cpu")
    if device_str == "mps":
        device_label = "Apple 芯片（MPS）"
    elif device_str == "cuda":
        device_label = f"NVIDIA 显卡（{device_desc}）"
    else:
        device_label = "CPU（无 GPU 加速）"
    device_html = f'<div class="device-badge {badge_class}">🖥  {device_label}</div>'

    head = CLOSE_TAB_CONFIRM_HEAD if _is_desktop_mode() else None

    with gr.Blocks(css=CSS, title="深度视频转换器", head=head) as demo:
        gr.Markdown(
            """# 🎥 深度视频转换器
使用 [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2)，
将 MP4 / MOV 视频转换为**灰度深度图视频**。
            """
        )
        gr.HTML(device_html)

        with gr.Row():
            with gr.Column(scale=1):
                input_video = gr.Video(
                    label="上传视频",
                    sources=["upload"],
                    format="mp4",
                )

                model_size = gr.Dropdown(
                    choices=list(MODEL_DEFS.keys()),
                    value="Small (fastest, ~95 MB)",
                    label="模型大小",
                    info="模型越大，深度图质量越高，但处理速度越慢。",
                )

                resolution = gr.Dropdown(
                    choices=[
                        ("原始分辨率", "Original"),
                        ("480p（按原视频比例，高度 480）", "480p"),
                        ("720p（按原视频比例，高度 720）", "720p"),
                        ("1080p（按原视频比例，高度 1080）", "1080p"),
                    ],
                    value="Original",
                    label="输出分辨率",
                    info="按上传视频比例缩放，不会强制改成 16:9。",
                )

                invert = gr.Checkbox(
                    value=False,
                    label="黑白反转",
                    info="交换远近区域的明暗。通常近处较亮，远处较暗。",
                )

                smoothing = gr.Slider(
                    minimum=0,
                    maximum=100,
                    value=60,
                    step=1,
                    label="时序平滑",
                    info="数值越高，画面闪烁越少，但可能出现拖影。",
                )

                preserve_audio = gr.Checkbox(
                    value=True,
                    label="保留原始音频",
                    info="将原视频音轨合并到深度视频中（需要 ffmpeg）。",
                )

                process_btn = gr.Button("⚙ 开始转换", variant="primary", size="lg")

            with gr.Column(scale=1):
                output_video = gr.Video(
                    label="输出深度视频",
                    format="mp4",
                    autoplay=True,
                )

        process_btn.click(
            fn=_process_video_for_gradio,
            inputs=[input_video, model_size, resolution, invert, smoothing, preserve_audio],
            outputs=output_video,
        )

        if _is_desktop_mode():
            shutdown_btn = gr.Button("退出应用", variant="secondary", size="sm")
            shutdown_btn.click(
                fn=_shutdown_desktop_app,
                inputs=None,
                outputs=None,
                show_progress="hidden",
            )
            demo.unload(_shutdown_desktop_app_from_browser_close)

        gr.Markdown(
            """---
### 📋 使用提示
- 首次使用时会从 Hugging Face **自动下载模型**，之后将直接加载本地 `models/` 目录中的模型。
- **时序平滑**会融合相邻深度帧以减少闪烁，建议从 60 开始调整。
- 开启**保留原始音频**后，原视频音轨会合并到输出视频中。
- 所有处理均在**本地运行**，视频不会上传到任何服务器。
            """
        )

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 58)
    print("  深度视频转换器 — Depth Anything V2 + Gradio")
    print("=" * 58)

    device_str, device_desc = detect_device()
    print(f"  检测到的设备    : {device_desc}")

    ffmpeg_found = ffmpeg_available()
    print(f"  ffmpeg           : {'✅ 已找到' if ffmpeg_found else '❌ 未找到'}")
    if not ffmpeg_found:
        print()
        print("  ⚠  视频编码和音频处理需要 ffmpeg。")
        print("     请先安装，再处理视频：")
        print("       macOS:   brew install ffmpeg")
        print("       Windows: winget install ffmpeg")
        print()

    # Check for model files
    print(f"  模型目录         : {MODELS_DIR}")
    for label, cfg in MODEL_DEFS.items():
        p = cfg["path"]
        if p.is_file():
            status = f"✅ ({p.stat().st_size / 1e6:.0f} MB)"
        else:
            status = "⬇  首次使用时自动下载"
        print(f"    {status}  {label}")

    print(f"  Python          : {sys.version.split()[0]}")
    print(f"  PyTorch         : {torch.__version__}")
    print(f"  Gradio          : {gr.__version__}")
    print("=" * 58)
    print()

    demo = create_ui()
    demo.launch(
        server_name=os.environ.get("DEPTH_HOST", "127.0.0.1"),
        server_port=int(os.environ.get("DEPTH_PORT", "7860")),
        share=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
