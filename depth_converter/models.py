"""Model loading, checkpoint management, and device detection.

Uses ONNX Runtime for inference — no PyTorch required at runtime.
"""

from __future__ import annotations

import gc
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.request import urlretrieve
import urllib.request
import socket

import cv2
import numpy as np
import onnxruntime as ort


PROJECT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = Path(os.environ.get("DEPTH_MODELS_DIR", PROJECT_DIR / "models")).expanduser()

_HF_MIRROR = os.environ.get("HF_MIRROR", "https://hf-mirror.com")

def _model_urls(repo: str, filename: str) -> list[str]:
    hf_path = f"{repo}/resolve/main/{filename}"
    return [
        f"{_HF_MIRROR}/{hf_path}",
        f"https://huggingface.co/{hf_path}",
        f"https://mirror.ghproxy.com/https://huggingface.co/{hf_path}",
    ]

MODEL_DEFS: Dict[str, dict] = {
    "Small (fastest, ~99 MB)": {
        "path": MODELS_DIR / "depth_anything_v2_vits.onnx",
        "urls": _model_urls("onnx-community/depth-anything-v2-small", "onnx/model.onnx"),
    },
    "Base (balanced, ~392 MB)": {
        "path": MODELS_DIR / "depth_anything_v2_vitb.onnx",
        "urls": _model_urls("onnx-community/depth-anything-v2-base", "onnx/model.onnx"),
    },
    "Large (best quality, ~1.3 GB)": {
        "path": MODELS_DIR / "depth_anything_v2_vitl.onnx",
        "urls": _model_urls("onnx-community/depth-anything-v2-large", "onnx/model.onnx"),
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


_cached_session: Optional[Tuple[ort.InferenceSession, str]] = None


def detect_device() -> Tuple[str, str]:
    """Return (provider_key, human_readable_description)."""
    providers = ort.get_available_providers()
    if "CUDAExecutionProvider" in providers:
        return "cuda", "CUDA (GPU 加速)"
    if "CoreMLExecutionProvider" in providers:
        return "coreml", "Apple Silicon (CoreML)"
    return "cpu", "CPU"


def _is_valid_model(path: Path, min_bytes: int = 1_000_000) -> bool:
    """Check if a file is a valid ONNX model."""
    if not path.is_file():
        return False
    if path.stat().st_size < min_bytes:
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(8)
            # ONNX files start with protobuf header (0x08 for field 1 varint)
            # or with the magic bytes for ONNX external data format
            if len(header) >= 4 and header[0] == 0x08:
                return True
            # Also accept ZIP (PK header) for PyTorch checkpoints if present
            if header[:2] == b"PK":
                return True
        return False
    except OSError:
        return False


def download_with_progress(urls: list[str], dest: Path, desc: str, progress) -> None:
    """Try each URL in order until one succeeds with a valid file."""

    dest.parent.mkdir(parents=True, exist_ok=True)

    if progress is not None:
        progress(0.0, f"正在下载模型：{desc}。首次使用可能需要几分钟。")

    timeout = int(os.environ.get("DOWNLOAD_TIMEOUT", "60"))

    last_error: Exception | None = None
    for i, url in enumerate(urls):
        source = "镜像" if i == 0 and len(urls) > 1 else "官方"
        if progress is not None and i > 0:
            progress(0.0, f"切换到{source}源重试下载：{desc}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DepthVideoConverter/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                last_pct = -1
                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress is not None and total_size > 0:
                            pct = int(min(downloaded / total_size, 1.0) * 100)
                            if pct != last_pct:
                                last_pct = pct
                                mb_done = downloaded / (1024 * 1024)
                                mb_total = total_size / (1024 * 1024)
                                progress(pct / 100 * 0.50, f"正在下载模型 ({mb_done:.1f}/{mb_total:.1f} MB)：{desc} [{source}]")

            if not _is_valid_model(dest):
                if dest.exists():
                    dest.unlink(missing_ok=True)
                raise RuntimeError(f"下载的文件无效（可能为网页错误或下载不完整）")
            if progress is not None:
                progress(0.50, f"模型下载完成：{desc}")
            return
        except Exception as exc:
            last_error = exc
            if dest.exists():
                dest.unlink(missing_ok=True)

    raise last_error or RuntimeError(f"所有下载地址均失败：{desc}\n\n如果网络无法访问 HuggingFace，可以设置环境变量 HF_MIRROR 指向可用镜像，或手动下载模型到:\n{dest}")


def ensure_checkpoint(model_size_label: str, progress=None) -> Path:
    """Return the checkpoint path, downloading the model if not already present."""
    cfg = MODEL_DEFS[model_size_label]
    path = cfg["path"]

    if path.is_file() and _is_valid_model(path):
        return path

    if path.exists():
        path.unlink(missing_ok=True)

    download_with_progress(
        urls=cfg["urls"],
        dest=path,
        desc=model_size_label,
        progress=progress,
    )
    return path


def _ort_providers(device_str: str) -> list[str]:
    """Return the ONNX Runtime execution providers for the given device."""
    if device_str == "cuda":
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if device_str == "coreml":
        return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def load_model(model_size_label: str, device_str: str, progress=None) -> ort.InferenceSession:
    """Return a loaded ONNX Runtime session, reusing cached instance when possible."""
    global _cached_session

    if _cached_session is not None and _cached_session[1] == model_size_label:
        return _cached_session[0]

    checkpoint_path = ensure_checkpoint(model_size_label, progress)
    if progress is not None:
        progress(0.52, f"正在加载模型：{model_size_label}")

    if _cached_session is not None:
        del _cached_session
        gc.collect()

    providers = _ort_providers(device_str)
    try:
        session = ort.InferenceSession(str(checkpoint_path), providers=providers)
    except Exception:
        checkpoint_path.unlink(missing_ok=True)
        if progress is not None:
            progress(0.0, "模型文件损坏，正在重新下载…")
        checkpoint_path = ensure_checkpoint(model_size_label, progress)
        if progress is not None:
            progress(0.52, f"正在加载模型：{model_size_label}")
        session = ort.InferenceSession(str(checkpoint_path), providers=providers)

    _cached_session = (session, model_size_label)
    return session


# ---------------------------------------------------------------------------
# Preprocessing & inference (pure numpy + cv2, no PyTorch needed)
# ---------------------------------------------------------------------------

_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _constrain_to_multiple(x: float, multiple: int, min_val: int) -> int:
    y = int(np.round(x / multiple) * multiple)
    if y < min_val:
        y = int(np.ceil(x / multiple) * multiple)
    return y


def preprocess_image(raw_image: np.ndarray, input_size: int = 518) -> Tuple[np.ndarray, int, int]:
    """Prepare a BGR frame for ONNX model input.

    Returns (input_tensor, orig_h, orig_w).
    input_tensor has shape [1, 3, H, W] in float32.
    """
    h, w = raw_image.shape[:2]

    scale = max(input_size / h, input_size / w)
    new_h = _constrain_to_multiple(scale * h, 14, input_size)
    new_w = _constrain_to_multiple(scale * w, 14, input_size)

    image = cv2.cvtColor(raw_image, cv2.COLOR_BGR2RGB)
    image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    image = image.astype(np.float32) / 255.0

    image = (image - _MEAN) / _STD

    image = np.transpose(image, (2, 0, 1))
    image = np.expand_dims(image, axis=0).astype(np.float32)

    return image, h, w


def infer_depth(session: ort.InferenceSession, raw_image: np.ndarray, input_size: int = 518) -> np.ndarray:
    """Run depth inference on a single BGR frame. Returns float32 depth map (H, W)."""
    input_tensor, orig_h, orig_w = preprocess_image(raw_image, input_size)

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    result = session.run([output_name], {input_name: input_tensor})[0]

    depth = result.squeeze()

    if depth.shape[0] != orig_h or depth.shape[1] != orig_w:
        depth = cv2.resize(depth, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

    return depth.astype(np.float32)
