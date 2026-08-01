"""Main depth-video processing pipeline.

This module is UI-agnostic — it knows nothing about Gradio, FastAPI, or any
specific interface.  Callers provide a progress callback that satisfies the
``ProgressCallback`` protocol.
"""

from __future__ import annotations

import gc
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional, Protocol

import cv2
import numpy as np
import torch

from .ffmpeg import (
    ffmpeg_available,
    extract_audio,
    has_audio_stream,
    merge_audio_video,
    write_video_ffmpeg,
)
from .models import (
    MODEL_DEFS,
    detect_device,
    ensure_checkpoint,
    load_model,
    output_size_for_resolution,
)
from .smoothing import TemporalSmoother, depth_to_grayscale


class ProgressCallback(Protocol):
    """Progress reporting protocol.

    Gradio's ``gr.Progress`` satisfies this natively (its ``__call__``
    accepts ``(fraction: float, desc: str)``).  FastAPI / CLI callers
    can pass a plain function with the same signature.
    """

    def __call__(self, fraction: float, description: str) -> None: ...


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def process_video(
    input_video_path: str,
    model_size_label: str,
    resolution_choice: str,
    invert_bw: bool,
    smoothing_strength: float,    # 0–100
    preserve_audio: bool,
    progress: ProgressCallback | None = None,
) -> str:
    """Run the full depth-conversion pipeline.  Returns path to output MP4.

    Parameters
    ----------
    input_video_path : str
        Path to the source video (.mp4 / .mov).
    model_size_label : str
        One of the keys in ``MODEL_DEFS``.
    resolution_choice : str
        One of the keys in ``RESOLUTION_PRESETS``.
    invert_bw : bool
        If True, swap near ↔ far in the output depth map.
    smoothing_strength : float
        0 = no temporal smoothing, 100 = maximum.
    preserve_audio : bool
        Whether to mux the original audio into the output file.
    progress : callable or None
        ``progress(fraction: float, desc: str)`` — called at key milestones.

    Returns
    -------
    str
        Path to the generated depth-map MP4 file.

    Raises
    ------
    RuntimeError
        If ffmpeg is missing, the video can't be opened, or other user errors.
    """

    def _report(frac: float, desc: str) -> None:
        if progress is not None:
            progress(frac, desc)

    # ------------------------------------------------------------------
    # 0. Validate inputs
    # ------------------------------------------------------------------
    if not input_video_path:
        raise RuntimeError("请先上传视频文件。")

    if not ffmpeg_available():
        raise RuntimeError(
            "需要 ffmpeg，但系统中未找到。\n\n"
            "macOS:  brew install ffmpeg\n"
            "Windows: winget install ffmpeg"
        )

    # ------------------------------------------------------------------
    # 1. Device & model
    # ------------------------------------------------------------------
    device_str, device_desc = detect_device()

    model = load_model(model_size_label, device_str, progress)

    # ------------------------------------------------------------------
    # 2. Open video
    # ------------------------------------------------------------------
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频文件：{input_video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if total_frames < 1:
        cap.release()
        raise RuntimeError("视频中没有可处理的画面。")

    if orig_w < 1 or orig_h < 1:
        cap.release()
        raise RuntimeError("无法读取视频尺寸。")

    out_w, out_h = output_size_for_resolution(orig_w, orig_h, resolution_choice)
    _report(0.54, f"输入尺寸 {orig_w}×{orig_h}｜输出尺寸 {out_w}×{out_h}")

    # ------------------------------------------------------------------
    # 3. Extract original audio (if requested)
    # ------------------------------------------------------------------
    tmp_dir = tempfile.mkdtemp(prefix="depth_video_")
    audio_path = os.path.join(tmp_dir, "audio.m4a") if preserve_audio else None
    has_audio = False
    if preserve_audio:
        _report(0.55, "正在提取原始音频…")
        has_audio = has_audio_stream(input_video_path)
        if has_audio:
            ok = extract_audio(input_video_path, str(audio_path))
            if not ok:
                has_audio = False

    # ------------------------------------------------------------------
    # 4. Read all frames into memory
    # ------------------------------------------------------------------
    _report(0.56, "正在读取视频画面…")
    raw_frames: list = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if out_w != orig_w or out_h != orig_h:
            frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LANCZOS4)
        raw_frames.append(frame)
    cap.release()
    n_frames = len(raw_frames)
    _report(0.58, f"已读取 {n_frames} 帧｜开始深度推理…")

    # ------------------------------------------------------------------
    # 5. Depth inference — uses the official infer_image method
    # ------------------------------------------------------------------
    depth_maps: list = []
    inference_start = time.time()
    for idx, frame_bgr in enumerate(raw_frames):
        frac = 0.58 + 0.30 * (idx / max(n_frames, 1))
        elapsed = time.time() - inference_start
        if idx > 0:
            eta = (elapsed / idx) * (n_frames - idx)
            eta_str = f"预计剩余 {eta:.0f} 秒"
        else:
            eta_str = "正在估算剩余时间…"
        _report(frac, f"深度推理 {idx + 1}/{n_frames}｜{eta_str}")

        depth = model.infer_image(frame_bgr)   # returns float32 ndarray (H, W)
        depth_maps.append(depth)

    _report(0.88, "深度推理完成｜正在进行后期处理…")

    if device_str == "cuda":
        torch.cuda.empty_cache()

    # ------------------------------------------------------------------
    # 6. Temporal smoothing + grayscale conversion
    # ------------------------------------------------------------------
    alpha = 1.0 - (smoothing_strength / 100.0) * 0.95
    smoother = TemporalSmoother(alpha)
    output_frames: list = []
    for idx, depth in enumerate(depth_maps):
        frac = 0.88 + 0.05 * (idx / max(n_frames, 1))
        _report(frac, f"正在应用平滑处理 {idx + 1}/{n_frames}")
        smoothed = smoother.smooth(depth)
        gray = depth_to_grayscale(smoothed, invert=invert_bw)
        # Grayscale → BGR for ffmpeg encoding
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        output_frames.append(bgr)

    del raw_frames, depth_maps
    gc.collect()

    # ------------------------------------------------------------------
    # 7. Encode output video (H.264 MP4 via ffmpeg pipe)
    # ------------------------------------------------------------------
    _report(0.93, "正在编码输出视频（H.264 MP4）…")
    video_no_audio = os.path.join(tmp_dir, "depth_video.mp4")
    stacked = np.stack(output_frames, axis=0)
    write_video_ffmpeg(stacked, fps, video_no_audio)
    del stacked, output_frames
    gc.collect()

    # ------------------------------------------------------------------
    # 8. Mux audio
    # ------------------------------------------------------------------
    if has_audio and audio_path and os.path.exists(str(audio_path)):
        _report(0.96, "正在合并原始音频…")
        final_path = os.path.join(tmp_dir, "depth_video_with_audio.mp4")
        merge_audio_video(video_no_audio, str(audio_path), final_path)
        result_path = final_path
    else:
        result_path = video_no_audio

    # ------------------------------------------------------------------
    # 9. Copy result to a stable location & clean up
    # ------------------------------------------------------------------
    output_dir = tempfile.mkdtemp(prefix="dv_output_")
    output_file = os.path.join(output_dir, "depth_output.mp4")
    shutil.copy2(result_path, output_file)

    try:
        shutil.rmtree(tmp_dir)
    except OSError:
        pass

    _report(1.0, "转换完成！")
    return output_file
