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

MODEL_DEFS: Dict[str, dict] = {
    "Small (fastest, ~95 MB)": {
        "encoder": "vits",
        "features": 64,
        "out_channels": [48, 96, 192, 384],
        "path": MODELS_DIR / "depth_anything_v2_vits.pth",
        "url": "https://huggingface.co/depth-anything/Depth-Anything-V2-Small/resolve/main/depth_anything_v2_vits.pth",
    },
    "Base (balanced, ~372 MB)": {
        "encoder": "vitb",
        "features": 128,
        "out_channels": [96, 192, 384, 768],
        "path": MODELS_DIR / "depth_anything_v2_vitb.pth",
        "url": "https://huggingface.co/depth-anything/Depth-Anything-V2-Base/resolve/main/depth_anything_v2_vitb.pth",
    },
    "Large (best quality, ~1.2 GB)": {
        "encoder": "vitl",
        "features": 256,
        "out_channels": [256, 512, 1024, 1024],
        "path": MODELS_DIR / "depth_anything_v2_vitl.pth",
        "url": "https://huggingface.co/depth-anything/Depth-Anything-V2-Large/resolve/main/depth_anything_v2_vitl.pth",
    },
}

RESOLUTION_PRESETS: Dict[str, Optional[Tuple[int, int]]] = {
    "Original": None,
    "480p (854×480)": (854, 480),
    "720p (1280×720)": (1280, 720),
    "1080p (1920×1080)": (1920, 1080),
}

# Global model cache — lazy load, keep at most one model in memory
_cached_model: Optional[Tuple[DepthAnythingV2, str]] = None  # (model, model_size_label)


def clear_model_cache() -> None:
    """Release the currently cached model before changing its search path."""
    global _cached_model
    if _cached_model is None:
        return
    del _cached_model
    _cached_model = None
    gc.collect()


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

def download_with_progress(url: str, dest: Path, desc: str, progress) -> None:
    """Download a file with progress updates.  *progress* may be a callable(frac, desc) or None."""

    dest.parent.mkdir(parents=True, exist_ok=True)

    def _report(count: int, block_size: int, total_size: int) -> None:
        if total_size > 0 and progress is not None:
            frac = min(count * block_size / total_size, 0.10)
            downloaded = count * block_size
            progress(frac, desc=f"{desc}  ({downloaded / 1e6:.0f} / {total_size / 1e6:.0f} MB)")

    if progress is not None:
        progress(0.0, desc=f"{desc}  connecting…")
    urlretrieve(url, str(dest), reporthook=_report)
    if progress is not None:
        progress(0.10, desc=f"{desc}  complete")


def ensure_checkpoint(model_size_label: str, progress=None) -> Path:
    """Return the checkpoint path, downloading the model if not already present."""
    cfg = MODEL_DEFS[model_size_label]
    path = cfg["path"]

    if path.is_file():
        return path

    download_with_progress(
        url=cfg["url"],
        dest=path,
        desc=f"Downloading {model_size_label}",
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
