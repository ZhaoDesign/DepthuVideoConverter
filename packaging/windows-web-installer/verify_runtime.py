"""Post-install smoke test for the Windows web installer runtime."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_runtime.py <app_dir>")

    app_dir = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(app_dir))

    modules = {
        "gradio": "gradio",
        "fastapi": "fastapi",
        "starlette": "starlette",
        "torch": "torch",
        "torchvision": "torchvision",
        "cv2": "cv2",
        "numpy": "numpy",
        "imageio_ffmpeg": "imageio_ffmpeg",
    }
    versions: dict[str, str] = {}
    for label, module_name in modules.items():
        module = importlib.import_module(module_name)
        versions[label] = str(getattr(module, "__version__", "unknown"))

    from depth_video_converter import create_ui

    ui = create_ui()
    ui.close()

    print(json.dumps({"ok": True, "versions": versions}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
