"""Depth Video Converter — shared core library.

This package contains all domain logic for depth-video conversion.
It is UI-agnostic and is consumed by:

- ``desktop_qt_app.py``          — supported native PySide6 desktop UI
- ``depth_video_converter.py``   — legacy Gradio compatibility UI
- Direct ``import``              — CLI scripts / library usage

The old ``server/`` FastAPI path is retained as historical compatibility code;
the supported local desktop path does not start a server or an online queue.
"""

from .core import process_video, ProgressCallback
from .ffmpeg import ffmpeg_available
from .models import (
    MODEL_DEFS,
    MODELS_DIR,
    PROJECT_DIR,
    RESOLUTION_PRESETS,
    detect_device,
    clear_model_cache,
    download_with_progress,
    ensure_checkpoint,
    load_model,
)
from .smoothing import TemporalSmoother, depth_to_grayscale

__all__ = [
    "process_video",
    "ProgressCallback",
    "ffmpeg_available",
    "MODEL_DEFS",
    "MODELS_DIR",
    "PROJECT_DIR",
    "RESOLUTION_PRESETS",
    "detect_device",
    "clear_model_cache",
    "download_with_progress",
    "ensure_checkpoint",
    "load_model",
    "TemporalSmoother",
    "depth_to_grayscale",
]
