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
    infer_depth,
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


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def media_kind_for_path(input_path: str) -> str | None:
    """Return ``video`` or ``image`` for a supported media path."""
    suffix = Path(input_path).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return None


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

    def _scale(start: float, span: float, current: int, total: int) -> float:
        if total <= 0:
            return start + span
        return start + span * (current / total)

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
    _report(0.0, f"正在分析视频信息…")
    _report(0.02, f"输入尺寸 {orig_w}×{orig_h}｜输出尺寸 {out_w}×{out_h}")

    # ------------------------------------------------------------------
    # 3. Extract original audio (if requested)
    # ------------------------------------------------------------------
    tmp_dir = tempfile.mkdtemp(prefix="depth_video_")
    audio_path = os.path.join(tmp_dir, "audio.m4a") if preserve_audio else None
    has_audio = False
    if preserve_audio:
        _report(0.04, "正在提取原始音频…")
        has_audio = has_audio_stream(input_video_path)
        if has_audio:
            ok = extract_audio(input_video_path, str(audio_path))
            if not ok:
                has_audio = False

    # ------------------------------------------------------------------
    # 4. Read all frames into memory
    # ------------------------------------------------------------------
    _report(0.05, f"正在读取视频画面 0/{total_frames}")
    raw_frames: list = []
    read_frames = 0
    read_report_step = max(1, total_frames // 40)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if out_w != orig_w or out_h != orig_h:
            frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LANCZOS4)
        raw_frames.append(frame)
        read_frames += 1
        if progress is not None and (read_frames == 1 or read_frames == total_frames or read_frames % read_report_step == 0):
            _report(
                _scale(0.05, 0.05, read_frames, total_frames),
                f"正在读取视频画面 {read_frames}/{total_frames}",
            )
    cap.release()
    n_frames = len(raw_frames)
    _report(0.10, f"已读取 {n_frames} 帧｜开始深度推理…")

    # ------------------------------------------------------------------
    # 5. Depth inference — uses the official infer_image method
    # ------------------------------------------------------------------
    depth_maps: list = []
    inference_start = time.time()
    infer_report_step = max(1, n_frames // 40)
    for idx, frame_bgr in enumerate(raw_frames):
        depth = infer_depth(model, frame_bgr)
        depth_maps.append(depth)

        completed = idx + 1
        frac = _scale(0.10, 0.70, completed, n_frames)
        elapsed = time.time() - inference_start
        if completed > 0:
            eta = (elapsed / completed) * (n_frames - completed)
            eta_str = f"预计剩余 {eta:.0f} 秒"
        else:
            eta_str = "正在估算剩余时间…"
        if completed == 1 or completed == n_frames or completed % infer_report_step == 0:
            _report(frac, f"深度推理 {completed}/{n_frames}｜{eta_str}")

    _report(0.80, "深度推理完成｜正在进行后期处理…")

    # ------------------------------------------------------------------
    # 6. Temporal smoothing + grayscale conversion
    # ------------------------------------------------------------------
    alpha = 1.0 - (smoothing_strength / 100.0) * 0.95
    smoother = TemporalSmoother(alpha)
    output_frames: list = []
    smooth_report_step = max(1, n_frames // 40)
    for idx, depth in enumerate(depth_maps):
        smoothed = smoother.smooth(depth)
        gray = depth_to_grayscale(smoothed, invert=invert_bw)
        # Grayscale → BGR for ffmpeg encoding
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        output_frames.append(bgr)

        completed = idx + 1
        frac = _scale(0.80, 0.10, completed, n_frames)
        if completed == 1 or completed == n_frames or completed % smooth_report_step == 0:
            _report(frac, f"正在应用平滑处理 {completed}/{n_frames}")

    del raw_frames, depth_maps
    gc.collect()

    # ------------------------------------------------------------------
    # 7. Encode output video (H.264 MP4 via ffmpeg pipe)
    # ------------------------------------------------------------------
    _report(0.90, "正在编码输出视频（H.264 MP4）…")
    video_no_audio = os.path.join(tmp_dir, "depth_video.mp4")
    stacked = np.stack(output_frames, axis=0)
    def encode_progress(done_fraction: float) -> None:
        if progress is not None:
            current = max(1, int(round(done_fraction * n_frames)))
            _report(_scale(0.90, 0.08, current, n_frames), f"正在编码输出视频 {current}/{n_frames}")

    write_video_ffmpeg(stacked, fps, video_no_audio, progress=encode_progress)
    del stacked, output_frames
    gc.collect()

    # ------------------------------------------------------------------
    # 8. Mux audio
    # ------------------------------------------------------------------
    if has_audio and audio_path and os.path.exists(str(audio_path)):
        _report(0.99, "正在合并原始音频…")
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


def process_image(
    input_image_path: str,
    model_size_label: str,
    resolution_choice: str,
    invert_bw: bool,
    progress: ProgressCallback | None = None,
) -> str:
    """Convert one image into a grayscale depth-map PNG."""

    def _report(frac: float, desc: str) -> None:
        if progress is not None:
            progress(frac, desc)

    if not input_image_path:
        raise RuntimeError("请先选择图片文件。")

    if media_kind_for_path(input_image_path) != "image":
        raise RuntimeError("输入文件不是支持的图片格式。")

    image = cv2.imread(input_image_path, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"无法打开图片文件：{input_image_path}")

    orig_h, orig_w = image.shape[:2]
    out_w, out_h = output_size_for_resolution(orig_w, orig_h, resolution_choice)
    _report(0.0, "正在分析图片信息…")
    _report(0.02, f"输入尺寸 {orig_w}×{orig_h}｜输出尺寸 {out_w}×{out_h}")

    device_str, _device_desc = detect_device()
    model = load_model(model_size_label, device_str, progress)

    if out_w != orig_w or out_h != orig_h:
        image = cv2.resize(image, (out_w, out_h), interpolation=cv2.INTER_LANCZOS4)

    _report(0.60, "正在进行图片深度推理…")
    depth = infer_depth(model, image)
    _report(0.86, "正在生成深度图…")
    grayscale = depth_to_grayscale(depth, invert=invert_bw)

    output_dir = tempfile.mkdtemp(prefix="dv_image_output_")
    output_file = os.path.join(output_dir, "depth_output.png")
    if not cv2.imwrite(output_file, grayscale):
        shutil.rmtree(output_dir, ignore_errors=True)
        raise RuntimeError("深度图保存失败。")

    _report(1.0, "图片深度图生成完成！")
    return output_file


def process_media(
    input_path: str,
    model_size_label: str,
    resolution_choice: str,
    invert_bw: bool,
    smoothing_strength: float,
    preserve_audio: bool,
    progress: ProgressCallback | None = None,
) -> str:
    """Dispatch a supported video or image to the matching pipeline."""
    if not input_path:
        raise RuntimeError("请先选择视频或图片文件。")
    kind = media_kind_for_path(input_path)
    if kind == "image":
        return process_image(
            input_image_path=input_path,
            model_size_label=model_size_label,
            resolution_choice=resolution_choice,
            invert_bw=invert_bw,
            progress=progress,
        )
    if kind == "video":
        return process_video(
            input_video_path=input_path,
            model_size_label=model_size_label,
            resolution_choice=resolution_choice,
            invert_bw=invert_bw,
            smoothing_strength=smoothing_strength,
            preserve_audio=preserve_audio,
            progress=progress,
        )
    raise RuntimeError("不支持的输入文件格式，请选择视频或图片。")
