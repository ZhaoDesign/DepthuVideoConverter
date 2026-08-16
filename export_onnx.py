#!/usr/bin/env python3
"""Export Depth Anything V2 PyTorch checkpoints to ONNX format.

Usage:
    python export_onnx.py                    # export Small model only
    python export_onnx.py --all              # export all three sizes
    python export_onnx.py --model base       # export a specific size

Requires torch and the original depth_anything_v2 package.
The exported .onnx files are saved alongside the .pth files in the models/ directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from depth_anything_v2.dpt import DepthAnythingV2
from depth_converter.models import MODEL_DEFS, ensure_checkpoint


ENCODER_CONFIGS = {
    "vits": {"encoder": "vits", "features": 64, "out_channels": [48, 96, 192, 384]},
    "vitb": {"encoder": "vitb", "features": 128, "out_channels": [96, 192, 384, 768]},
    "vitl": {"encoder": "vitl", "features": 256, "out_channels": [256, 512, 1024, 1024]},
}


def export_model(label: str) -> Path:
    cfg = MODEL_DEFS[label]
    pth_path = ensure_checkpoint(label)
    onnx_path = pth_path.with_suffix(".onnx")

    print(f"Loading {label} from {pth_path}...")
    enc = ENCODER_CONFIGS[cfg["encoder"]]
    model = DepthAnythingV2(**enc)
    state_dict = torch.load(str(pth_path), map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()

    dummy = torch.randn(1, 3, 518, 518)

    print(f"Exporting to {onnx_path}...")
    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        opset_version=17,
        input_names=["image"],
        output_names=["depth"],
        dynamic_axes={
            "image": {2: "height", 3: "width"},
            "depth": {1: "height", 2: "width"},
        },
    )
    print(f"Done: {onnx_path} ({onnx_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return onnx_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Depth Anything V2 to ONNX")
    parser.add_argument("--model", choices=["small", "base", "large"], default="small")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    label_map = {
        "small": "Small (fastest, ~95 MB)",
        "base": "Base (balanced, ~372 MB)",
        "large": "Large (best quality, ~1.2 GB)",
    }

    if args.all:
        for key in label_map:
            export_model(label_map[key])
    else:
        export_model(label_map[args.model])


if __name__ == "__main__":
    main()
