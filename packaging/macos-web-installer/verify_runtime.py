"""Post-install smoke test for the macOS native desktop runtime."""

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
        "onnxruntime": "onnxruntime",
        "cv2": "cv2",
        "numpy": "numpy",
        "imageio_ffmpeg": "imageio_ffmpeg",
        "PySide6": "PySide6",
        "QtMultimedia": "PySide6.QtMultimedia",
        "QtMultimediaWidgets": "PySide6.QtMultimediaWidgets",
    }
    versions: dict[str, str] = {}
    for label, module_name in modules.items():
        module = importlib.import_module(module_name)
        versions[label] = str(getattr(module, "__version__", "unknown"))

    import desktop_qt_app

    if not hasattr(desktop_qt_app, "ContourControlWindow"):
        raise RuntimeError("Native desktop entry point is missing.")

    print(json.dumps({"ok": True, "versions": versions}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
