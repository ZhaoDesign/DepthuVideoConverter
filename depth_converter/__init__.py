"""DepthuVideoConverter — shared media depth-conversion library.

This package contains all domain logic for depth-video conversion.
It is UI-agnostic and is consumed by:

- ``depth_video_converter.py``  — Gradio web UI (original interface)
- ``server/``                    — FastAPI sidecar (for desktop app)
- Direct ``import``              — CLI scripts / library usage
"""

from .core import (
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    ProgressCallback,
    media_kind_for_path,
    process_image,
    process_media,
    process_video,
)
from .ffmpeg import ffmpeg_available
from .models import (
    MODEL_DEFS,
    MODELS_DIR,
    PROJECT_DIR,
    RESOLUTION_ALIASES,
    RESOLUTION_PRESETS,
    detect_device,
    download_with_progress,
    ensure_checkpoint,
    infer_depth,
    load_model,
    normalize_resolution_choice,
    output_size_for_resolution,
)
from .smoothing import TemporalSmoother, depth_to_grayscale

__all__ = [
    "process_video",
    "process_image",
    "process_media",
    "media_kind_for_path",
    "VIDEO_EXTENSIONS",
    "IMAGE_EXTENSIONS",
    "ProgressCallback",
    "ffmpeg_available",
    "MODEL_DEFS",
    "MODELS_DIR",
    "PROJECT_DIR",
    "RESOLUTION_ALIASES",
    "RESOLUTION_PRESETS",
    "detect_device",
    "download_with_progress",
    "ensure_checkpoint",
    "infer_depth",
    "load_model",
    "normalize_resolution_choice",
    "output_size_for_resolution",
    "TemporalSmoother",
    "depth_to_grayscale",
]
