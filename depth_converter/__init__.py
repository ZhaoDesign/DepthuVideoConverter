"""DepthuVideoConverter — shared media depth-conversion library.

This package contains all domain logic for depth-video conversion.
It is UI-agnostic and is consumed by:

- ``desktop_qt_app.py``          — supported native PySide6 desktop UI
- ``depth_video_converter.py``   — legacy Gradio compatibility UI
- Direct ``import``              — CLI scripts / library usage

The old ``server/`` FastAPI path is retained as historical compatibility code;
the supported local desktop path does not start a server or an online queue.
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
    clear_model_cache,
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
    "clear_model_cache",
    "download_with_progress",
    "ensure_checkpoint",
    "infer_depth",
    "load_model",
    "normalize_resolution_choice",
    "output_size_for_resolution",
    "TemporalSmoother",
    "depth_to_grayscale",
]
