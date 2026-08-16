#!/usr/bin/env python3
"""Stable native desktop entry point for DepthuVideoConverter."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path


def main() -> int:
    project_dir = Path(__file__).resolve().parent
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from PySide6.QtWidgets import QApplication

    from desktop_qt_app import APP_TITLE, ContourControlWindow, apply_style

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("ZhaoDesign")
    apply_style(app)

    window = ContourControlWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        message = traceback.format_exc()
        log_path = Path.home() / "AppData" / "Local" / "DepthuVideoConverter" / "launcher.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(message, encoding="utf-8")
        except OSError:
            pass
        raise
