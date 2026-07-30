#!/usr/bin/env python3
"""CLI entry point for Contour Control Tool."""

from __future__ import annotations

import argparse
import os
import sys

from depth_converter import MODEL_DEFS, RESOLUTION_PRESETS, process_video


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert any video to a depth-map control video using Depth Anything V2.",
    )
    parser.add_argument("input", help="Path to input video (.mp4 / .mov)")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output path (default: <input>_depth.mp4)",
    )
    parser.add_argument(
        "-m", "--model",
        choices=list(MODEL_DEFS.keys()),
        default="Base (balanced, ~372 MB)",
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
        help="Temporal smoothing 0-100 (default: 60)",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Don't preserve original audio",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    output = args.output or f"{os.path.splitext(args.input)[0]}_depth.mp4"

    print(f"Input:    {args.input}")
    print(f"Model:    {args.model}")
    print(f"Output:   {output}")
    print()

    result = process_video(
        input_video_path=args.input,
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
