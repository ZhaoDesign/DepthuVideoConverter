#!/usr/bin/env python3
"""CLI entry point for DepthuVideoConverter."""

from __future__ import annotations

import argparse
import os
import sys

from depth_converter import MODEL_DEFS, RESOLUTION_PRESETS, media_kind_for_path, process_media

MODEL_LABELS = list(MODEL_DEFS.keys())
DEFAULT_MODEL_LABEL = MODEL_LABELS[1] if len(MODEL_LABELS) > 1 else MODEL_LABELS[0]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a video or single image to a grayscale depth result using Depth Anything V2.",
    )
    parser.add_argument("input", help="Path to input video or image")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output path (default: <input>_depth.mp4 for video, <input>_depth.png for image)",
    )
    parser.add_argument(
        "-m", "--model",
        choices=MODEL_LABELS,
        default=DEFAULT_MODEL_LABEL,
        help="Model size (default: Base)",
    )
    parser.add_argument(
        "-r", "--resolution",
        choices=list(RESOLUTION_PRESETS.keys()),
        default="Original",
        help="Output resolution (default: Original)",
    )
    parser.add_argument(
        "--invert",
        action="store_true",
        help="Invert black & white (swap near <-> far)",
    )
    parser.add_argument(
        "-s", "--smoothing",
        type=float,
        default=60,
        help="Temporal smoothing 0-100 for video input (default: 60)",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Don't preserve original audio for video input",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    kind = media_kind_for_path(args.input)
    if kind is None:
        print("Error: unsupported file type. Use a video or image.", file=sys.stderr)
        sys.exit(1)

    default_ext = ".png" if kind == "image" else ".mp4"
    output = args.output or f"{os.path.splitext(args.input)[0]}_depth{default_ext}"

    print(f"Input:    {args.input}")
    print(f"Model:    {args.model}")
    print(f"Output:   {output}")
    print()

    result = process_media(
        input_path=args.input,
        model_size_label=args.model,
        resolution_choice=args.resolution,
        invert_bw=args.invert,
        smoothing_strength=args.smoothing,
        preserve_audio=not args.no_audio,
        progress=lambda f, d: print(f"  [{f*100:.0f}%] {d}"),
    )

    # Copy to requested output path if different
    import shutil
    if os.path.abspath(result) != os.path.abspath(output):
        shutil.copy2(result, output)

    print()
    print(f"Done: {output}")


if __name__ == "__main__":
    main()
