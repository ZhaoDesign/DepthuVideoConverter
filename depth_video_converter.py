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

import gradio as gr
import torch

# Shared core library — all domain logic lives here
from depth_converter import (
    MODEL_DEFS,
    MODELS_DIR,
    RESOLUTION_PRESETS,
    detect_device,
    ffmpeg_available,
    process_video,
)


# ---------------------------------------------------------------------------
# Gradio adapter — catch RuntimeError and re-raise as gr.Error for the UI
# ---------------------------------------------------------------------------

def _process_video_for_gradio(
    input_video_path: str,
    model_size_label: str,
    resolution_choice: str,
    invert_bw: bool,
    smoothing_strength: float,
    preserve_audio: bool,
    progress: gr.Progress = gr.Progress(),
) -> str:
    """Thin adapter: calls the shared ``process_video``, wraps errors for Gradio."""
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
    device_html = f'<div class="device-badge {badge_class}">🖥  {device_desc}</div>'

    with gr.Blocks(css=CSS, title="Depth Video Converter") as demo:
        gr.Markdown(
            """# 🎥 Depth Video Converter
Convert any MP4 / MOV video into a **grayscale depth-map video**
using [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2).
            """
        )
        gr.HTML(device_html)

        with gr.Row():
            with gr.Column(scale=1):
                input_video = gr.Video(
                    label="Upload Video",
                    sources=["upload"],
                    format="mp4",
                )

                model_size = gr.Dropdown(
                    choices=list(MODEL_DEFS.keys()),
                    value="Small (fastest, ~95 MB)",
                    label="Model Size",
                    info="Larger models produce better depth maps but run slower.",
                )

                resolution = gr.Dropdown(
                    choices=list(RESOLUTION_PRESETS.keys()),
                    value="Original",
                    label="Output Resolution",
                    info="Downscale to speed up processing.",
                )

                invert = gr.Checkbox(
                    value=False,
                    label="Invert Black & White",
                    info="Swap near ↔ far.  Usually near = bright, far = dark.",
                )

                smoothing = gr.Slider(
                    minimum=0,
                    maximum=100,
                    value=60,
                    step=1,
                    label="Temporal Smoothing",
                    info="Higher values reduce flicker but may cause ghosting.",
                )

                preserve_audio = gr.Checkbox(
                    value=True,
                    label="Preserve Original Audio",
                    info="Copy the original audio track into the depth video (requires ffmpeg).",
                )

                process_btn = gr.Button("⚙ Process Video", variant="primary", size="lg")

            with gr.Column(scale=1):
                output_video = gr.Video(
                    label="Output Depth Video",
                    format="mp4",
                    autoplay=True,
                )

        process_btn.click(
            fn=_process_video_for_gradio,
            inputs=[input_video, model_size, resolution, invert, smoothing, preserve_audio],
            outputs=output_video,
        )

        gr.Markdown(
            """---
### 📋 Tips
- Models are **auto-downloaded on first use** from Hugging Face.  Subsequent runs load from the local `models/` directory instantly.
- **Temporal smoothing** blends consecutive depth frames to reduce flicker.  Start at 60 and adjust.
- **Audio preservation** copies the original audio into the output.
- Everything runs **100 % locally** — nothing is uploaded anywhere.
            """
        )

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 58)
    print("  Depth Video Converter — Depth Anything V2 + Gradio")
    print("=" * 58)

    device_str, device_desc = detect_device()
    print(f"  Detected device : {device_desc}")

    ffmpeg_found = ffmpeg_available()
    print(f"  ffmpeg          : {'found' if ffmpeg_found else 'NOT FOUND'}")
    if not ffmpeg_found:
        print()
        print("  Warning: ffmpeg is required for video encoding and audio handling.")
        print("     Install it before processing videos:")
        print("       macOS:   brew install ffmpeg")
        print("       Windows: winget install ffmpeg")
        print()

    # Check for model files
    print(f"  Models directory: {MODELS_DIR}")
    for label, cfg in MODEL_DEFS.items():
        p = cfg["path"]
        if p.is_file():
            status = f"ready ({p.stat().st_size / 1e6:.0f} MB)"
        else:
            status = "auto-download on first use"
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
