"""Model loading, checkpoint management, and device detection."""

from __future__ import annotations

import gc
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.request import urlretrieve

import torch

from depth_anything_v2 import DepthAnythingV2

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = Path(os.environ.get("DEPTH_MODELS_DIR", PROJECT_DIR / "models")).expanduser()

_HF_MIRROR = os.environ.get("HF_MIRROR", "https://hf-mirror.com")

def _model_urls(repo: str, filename: str) -> list[str]:
    hf_path = f"{repo}/resolve/main/{filename}"
    return [
        f"{_HF_MIRROR}/{hf_path}",
        f"https://huggingface.co/{hf_path}",
    ]

MODEL_DEFS: Dict[str, dict] = {
    "Small (fastest, ~95 MB)": {
        "encoder": "vits",
        "features": 64,
        "out_channels": [48, 96, 192, 384],
        "path": MODELS_DIR / "depth_anything_v2_vits.pth",
        "urls": _model_urls("depth-anything/Depth-Anything-V2-Small", "depth_anything_v2_vits.pth"),
    },
    "Base (balanced, ~372 MB)": {
        "encoder": "vitb",
        "features": 128,
        "out_channels": [96, 192, 384, 768],
        "path": MODELS_DIR / "depth_anything_v2_vitb.pth",
        "urls": _model_urls("depth-anything/Depth-Anything-V2-Base", "depth_anything_v2_vitb.pth"),
    },
    "Large (best quality, ~1.2 GB)": {
        "encoder": "vitl",
        "features": 256,
        "out_channels": [256, 512, 1024, 1024],
        "path": MODELS_DIR / "depth_anything_v2_vitl.pth",
        "urls": _model_urls("depth-anything/Depth-Anything-V2-Large", "depth_anything_v2_vitl.pth"),
    },
}

RESOLUTION_PRESETS: Dict[str, Optional[int]] = {
    "Original": None,
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
}

RESOLUTION_ALIASES: Dict[str, str] = {
    "480p (854×480)": "480p",
    "720p (1280×720)": "720p",
    "1080p (1920×1080)": "1080p",
}


def normalize_resolution_choice(resolution_choice: str) -> str:
    """Return the canonical resolution preset name."""
    canonical = RESOLUTION_ALIASES.get(resolution_choice, resolution_choice)
    if canonical not in RESOLUTION_PRESETS:
        raise KeyError(resolution_choice)
    return canonical


def output_size_for_resolution(orig_w: int, orig_h: int, resolution_choice: str) -> Tuple[int, int]:
    """Return output size while preserving the uploaded video's aspect ratio."""
    canonical = normalize_resolution_choice(resolution_choice)
    target_h = RESOLUTION_PRESETS[canonical]

    if target_h is None:
        return orig_w, orig_h

    out_h = _even_dimension(target_h)
    out_w = _even_dimension(orig_w * (out_h / orig_h))
    return out_w, out_h


def _even_dimension(value: float) -> int:
    """H.264/yuv420p encoders generally require even dimensions."""
    return max(2, int(round(value / 2)) * 2)

# Global model cache — lazy load, keep at most one model in memory
_cached_model: Optional[Tuple[DepthAnythingV2, str]] = None  # (model, model_size_label)


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------

def detect_device() -> Tuple[str, str]:
    """Return (torch_device_str, human_readable_description)."""
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0) or "NVIDIA GPU"
        return "cuda", f"CUDA — {name}"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps", "Apple Silicon (MPS)"
    return "cpu", "CPU (no GPU acceleration)"


# ---------------------------------------------------------------------------
# Checkpoint download helpers
# ---------------------------------------------------------------------------

def download_with_progress(urls: list[str], dest: Path, desc: str, progress) -> None:
    """Try each URL in order until one succeeds."""

    dest.parent.mkdir(parents=True, exist_ok=True)

    if progress is not None:
        progress(0.0, f"正在下载模型：{desc}。首次使用可能需要几分钟。")

    last_error: Exception | None = None
    for url in urls:
        try:
            urlretrieve(url, str(dest))
            if progress is not None:
                progress(0.10, f"模型下载完成：{desc}")
            return
        except Exception as exc:
            last_error = exc
            if dest.exists():
                dest.unlink(missing_ok=True)

    raise last_error or RuntimeError(f"所有下载地址均失败：{desc}")


def ensure_checkpoint(model_size_label: str, progress=None) -> Path:
    """Return the checkpoint path, downloading the model if not already present."""
    cfg = MODEL_DEFS[model_size_label]
    path = cfg["path"]

    if path.is_file():
        return path

    download_with_progress(
        urls=cfg["urls"],
        dest=path,
        desc=model_size_label,
        progress=progress,
    )
    return path


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def load_model(model_size_label: str, device_str: str, progress=None) -> DepthAnythingV2:
    """Return a loaded DepthAnythingV2 model, reusing cached instance when possible."""
    global _cached_model

    # Reuse cached model if the same size was already loaded
    if _cached_model is not None and _cached_model[1] == model_size_label:
        return _cached_model[0]

    cfg = MODEL_DEFS[model_size_label]
    checkpoint_path = ensure_checkpoint(model_size_label, progress)
    if progress is not None:
        progress(0.10, f"正在加载模型：{model_size_label}")

    # Unload previous model to free memory
    if _cached_model is not None:
        del _cached_model
        gc.collect()
        if device_str == "cuda":
            torch.cuda.empty_cache()

    device = torch.device(device_str)
    model = DepthAnythingV2(
        encoder=cfg["encoder"],
        features=cfg["features"],
        out_channels=cfg["out_channels"],
    )

    state_dict = torch.load(str(checkpoint_path), map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model = model.to(device).eval()

    _cached_model = (model, model_size_label)
    return model
