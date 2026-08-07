#!/usr/bin/env python3
"""Native Qt desktop UI for DepthuVideoConverter."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.dont_write_bytecode = True


APP_TITLE = "DepthuVideoConverter"
APP_DIR_NAME = "DepthuVideoConverter"
LEGACY_APP_DIR_NAMES = ("DepthVideoConverter",)
GITHUB_URL = "https://github.com/ZhaoDesign/DepthuVideoConverter"
APP_ICON_ICO = "contour-control-tool.ico"
APP_ICON_PNG = "contour-control-tool.png"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}

WINDOW_WIDTH = 1110
WINDOW_HEIGHT = 852
TITLE_BAR_HEIGHT = 36
PANEL_WIDTH = 527
PANEL_HEIGHT = 792
INNER_WIDTH = 495
VIDEO_SURFACE_HEIGHT = 321
TRANSPORT_HEIGHT = 36
MEDIA_AREA_HEIGHT = VIDEO_SURFACE_HEIGHT + 12 + TRANSPORT_HEIGHT

MODEL_DISPLAY_LABELS = {
    "Small (fastest, ~99 MB)": "Small（最快，约 99 MB）",
    "Base (balanced, ~392 MB)": "Base（均衡，约 392 MB）",
    "Large (best quality, ~1.3 GB)": "Large（高质量，约 1.3 GB）",
}

_script_dir = str(Path(__file__).resolve().parent)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)


def _user_data_dir() -> Path:
    override = os.environ.get("DEPTH_APP_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    preferred = root / APP_DIR_NAME
    if preferred.exists():
        return preferred
    for legacy_name in LEGACY_APP_DIR_NAMES:
        legacy = root / legacy_name
        if legacy.exists():
            return legacy
    return preferred


def _configure_runtime() -> Path:
    data_dir = _user_data_dir()
    models_dir = data_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("DEPTH_MODELS_DIR", str(models_dir))
    os.environ["DEPTH_DESKTOP_MODE"] = "1"
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

    local_no_proxy = "127.0.0.1,localhost,::1"
    os.environ["NO_PROXY"] = _merge_proxy_bypass(os.environ.get("NO_PROXY"), local_no_proxy)
    os.environ["no_proxy"] = _merge_proxy_bypass(os.environ.get("no_proxy"), local_no_proxy)
    return data_dir


def _merge_proxy_bypass(current: str | None, required: str) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for raw_value in (current or "", required):
        for part in raw_value.split(","):
            value = part.strip()
            if value == "[::1]":
                value = "::1"
            key = value.lower()
            if value and key not in seen:
                values.append(value)
                seen.add(key)
    return ",".join(values)


DATA_DIR = _configure_runtime()


def _show_native_error(title: str, message: str) -> None:
    if sys.platform == "darwin":
        script = (
            'on run argv\n'
            'display alert (item 1 of argv) message (item 2 of argv) as critical buttons {"确定"} default button 1\n'
            'end run'
        )
        subprocess.run(["osascript", "-e", script, title, message], check=False)
        return
    if os.name == "nt":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        return
    print(f"{title}: {message}", file=sys.stderr)

try:
    from PySide6.QtCore import QPoint, QRectF, QObject, QSize, Qt, QThread, QTimer, QUrl, Signal  # noqa: E402
    from PySide6.QtGui import QAction, QBitmap, QColor, QDesktopServices, QDragEnterEvent, QDropEvent, QFont, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap  # noqa: E402
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer  # noqa: E402
    from PySide6.QtMultimediaWidgets import QVideoWidget  # noqa: E402
    from PySide6.QtWidgets import (  # noqa: E402
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QListView,
        QMainWindow,
        QMenu,
        QMenuBar,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QProgressBar,
        QSizePolicy,
        QSlider,
        QSpacerItem,
        QStackedLayout,
        QStyle,
        QStyledItemDelegate,
        QStyleOptionViewItem,
        QVBoxLayout,
        QWidget,
    )

    from depth_converter import (  # noqa: E402
        MODEL_DEFS,
        MODELS_DIR,
        RESOLUTION_PRESETS,
        detect_device,
        ffmpeg_available,
        process_video,
    )
except ImportError:
    msg = traceback.format_exc()
    log_path = DATA_DIR / "crash.log"
    try:
        log_path.write_text(msg, encoding="utf-8")
    except OSError:
        pass
    _show_native_error(
        APP_TITLE,
        f"运行环境加载失败，请检查安装是否完整。\n\n{msg}\n\n日志: {log_path}",
    )
    sys.exit(1)

MODEL_FILE_SUFFIXES = {Path(cfg["path"]).suffix.lower() for cfg in MODEL_DEFS.values()}
DEFAULT_MODEL_LABEL = next(iter(MODEL_DEFS))


def _asset_path(name: str) -> Path:
    app_dir = Path(__file__).resolve().parent
    candidates = [
        app_dir.parent / "assets" / name,
        app_dir / "assets" / name,
        Path.cwd() / "assets" / name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _load_icon(name: str) -> QIcon:
    p = _asset_path(name)
    if p.is_file():
        return QIcon(str(p))
    return QIcon()


def _set_icon(button: QPushButton, name: str, size: int = 16) -> None:
    button.setIcon(_load_icon(name))
    button.setIconSize(QSize(size, size))


def _default_output_dir(input_path: str | None) -> Path:
    if input_path:
        parent = Path(input_path).expanduser().resolve().parent
        if parent.is_dir():
            return parent
    return Path.home() / "Videos"


def _unique_output_path(input_path: str, output_dir: str) -> Path:
    source = Path(input_path)
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    base = target_dir / f"{source.stem}_depth.mp4"
    if not base.exists():
        return base
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return target_dir / f"{source.stem}_depth_{stamp}.mp4"


def _short_path(path: str, max_chars: int = 62) -> str:
    if len(path) <= max_chars:
        return path
    return "..." + path[-(max_chars - 3):]


class StyledDialog(QDialog):
    """Custom dialog matching the white Codex theme."""

    def __init__(self, parent, title: str, message: str, kind: str = "info"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(380)
        self.setStyleSheet("""
            QDialog { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; }
            QLabel#dialogTitle { color: #111827; font-size: 15px; font-weight: 600; }
            QLabel#dialogMsg { color: #374151; font-size: 13px; }
            QPushButton#dialogBtn {
                background: #111827; color: #FFFFFF; border: none;
                border-radius: 8px; padding: 10px 24px; font-weight: 600; font-size: 13px;
            }
            QPushButton#dialogBtn:hover { background: #374151; }
            QPushButton#dialogBtnSecondary {
                background: #F3F4F6; color: #374151; border: none;
                border-radius: 8px; padding: 10px 24px; font-weight: 600; font-size: 13px;
            }
            QPushButton#dialogBtnSecondary:hover { background: #E5E7EB; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        layout.addWidget(title_label)

        msg_label = QLabel(message)
        msg_label.setObjectName("dialogMsg")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        layout.addSpacing(8)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("dialogBtn")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)


def _show_dialog(parent, title: str, message: str, kind: str = "info") -> None:
    dlg = StyledDialog(parent, title, message, kind)
    dlg.exec()


class IconButton(QPushButton):
    """Icon-only button with consistent Figma sizing and no hover text."""

    def __init__(self, icon_name: str, parent=None, size: int = 36) -> None:
        super().__init__(parent)
        self.setObjectName("iconButton")
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        _set_icon(self, icon_name, 16)

    def set_icon_name(self, icon_name: str) -> None:
        _set_icon(self, icon_name, 16)


class FigmaComboBox(QComboBox):
    """Combo box whose popup geometry matches the Figma overlays."""

    def showPopup(self) -> None:  # type: ignore[override]
        super().showPopup()
        QTimer.singleShot(0, self._position_popup)

    def _position_popup(self) -> None:
        popup = self.view().window()
        if popup is None:
            return
        height = 4 + self.count() * 40
        top_left = self.mapToGlobal(QPoint(0, -57))
        popup.setGeometry(top_left.x(), top_left.y(), self.width(), height)
        self.view().setFixedSize(self.width(), height)


class ComboItemDelegate(QStyledItemDelegate):
    """Paint combo popup items with rounded hover and selected states."""

    _check_pixmap: QPixmap | None = None

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # type: ignore[override]
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        combo = self.parent()
        current_row = combo.currentIndex() if isinstance(combo, QComboBox) else -1
        selected = bool(opt.state & QStyle.StateFlag.State_Selected) or index.row() == current_row
        hovered = bool(opt.state & QStyle.StateFlag.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg_rect = opt.rect
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F9FAFB"))
            painter.drawRoundedRect(bg_rect, 8, 8)
        elif hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F3F4F6"))
            painter.drawRoundedRect(bg_rect, 8, 8)

        text_rect = opt.rect.adjusted(12, 0, -42, 0)
        painter.setPen(QColor("#344252"))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, opt.text)
        if selected:
            if ComboItemDelegate._check_pixmap is None:
                ComboItemDelegate._check_pixmap = QPixmap(str(_asset_path("icon-check-dark.png")))
            pixmap = ComboItemDelegate._check_pixmap
            if pixmap is not None and not pixmap.isNull():
                size = QSize(16, 16)
                x = opt.rect.x() + opt.rect.width() - 28
                y = opt.rect.center().y() - size.height() // 2
                painter.drawPixmap(x, y, size.width(), size.height(), pixmap)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # type: ignore[override]
        return QSize(super().sizeHint(option, index).width(), 36)


def _configure_combo(combo: QComboBox) -> None:
    view = QListView()
    view.setObjectName("comboPopup")
    view.setMouseTracking(True)
    view.setUniformItemSizes(False)
    view.setSpacing(2)
    combo.setView(view)
    combo.setItemDelegate(ComboItemDelegate(combo))
    combo.setMaxVisibleItems(8)
    combo.setFixedHeight(36)
    combo.setCursor(Qt.CursorShape.PointingHandCursor)
    combo.view().window().setWindowFlags(
        Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
    )


def _model_display_label(model_key: str) -> str:
    return MODEL_DISPLAY_LABELS.get(model_key, model_key)


def _combo_value(combo: QComboBox) -> str:
    data = combo.currentData()
    return str(data) if data is not None else combo.currentText()


def _set_combo_data(combo: QComboBox, value: str) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)
    else:
        combo.setCurrentText(value)


class StaticTransportControls(QFrame):
    """Non-playing controls used below the empty input drop target."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("transportControls")
        self.setFixedSize(INNER_WIDTH, TRANSPORT_HEIGHT)

        controls = QHBoxLayout(self)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(12)

        self._play_btn = IconButton("icon-play.png", self, size=32)
        controls.addWidget(self._play_btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(0)
        self._slider.setMinimumWidth(160)
        controls.addWidget(self._slider, 1)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setObjectName("muted")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_label.setFixedWidth(88)
        controls.addWidget(self._time_label)

        self._mute_btn = IconButton("icon-volume.png", self, size=32)
        controls.addWidget(self._mute_btn)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setObjectName("volumeSlider")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.setFixedWidth(88)
        controls.addWidget(self._volume_slider)


class FigmaPopupItem(QPushButton):
    def __init__(self, text: str, callback=None, submenu: "FigmaPopupMenu | None" = None, active: bool = False) -> None:
        super().__init__(text)
        self.callback = callback
        self.submenu = submenu
        self._more_icon = _load_icon("icon-more.png") if submenu is not None else QIcon()
        self.setObjectName("figmaPopupItem")
        self.setFixedHeight(25)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("active", active)
        self.setAutoFillBackground(False)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        parent_menu = self._parent_menu()
        if parent_menu is not None:
            parent_menu.set_active_item(self)
        if self.submenu is not None:
            self.submenu.show_at(self.mapToGlobal(QPoint(self.width() + 4, 0)))
        super().enterEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.callback is not None:
            menu = self._parent_menu()
            if menu is not None:
                menu.close_chain()
            self.callback()
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        active = bool(self.property("active"))
        if active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F9FAFB"))
            painter.drawRoundedRect(self.rect(), 4, 4)
        painter.setPen(QColor("#6C7583"))
        painter.setFont(self.font())
        painter.drawText(self.rect().adjusted(8, 0, -28, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        if not self._more_icon.isNull():
            pix = self._more_icon.pixmap(QSize(16, 16))
            painter.drawPixmap(self.width() - 24, (self.height() - 16) // 2, pix)

    def _parent_menu(self) -> "FigmaPopupMenu | None":
        widget = self.parentWidget()
        while widget is not None:
            if isinstance(widget, FigmaPopupMenu):
                return widget
            widget = widget.parentWidget()
        return None


class FigmaPopupMenu(QWidget):
    SHADOW_SPREAD = 8
    CORNER_RADIUS = 8

    def __init__(self, width: int = 126, parent: QWidget | None = None, spacing: int = 4) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("figmaPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._items: list[FigmaPopupItem] = []
        self._submenus: list[FigmaPopupMenu] = []
        self._active_item: FigmaPopupItem | None = None
        self._panel_width = width

        root = QVBoxLayout(self)
        root.setContentsMargins(
            self.SHADOW_SPREAD, self.SHADOW_SPREAD,
            self.SHADOW_SPREAD, self.SHADOW_SPREAD,
        )
        self.panel = QFrame(self)
        self.panel.setObjectName("figmaPopupPanel")
        self.panel.setFrameShape(QFrame.Shape.NoFrame)
        self.panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.panel.setAutoFillBackground(False)
        self.panel.setFixedWidth(width)
        self.panel_layout = QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(4, 4, 4, 4)
        self.panel_layout.setSpacing(spacing)
        root.addWidget(self.panel)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        spread = float(self.SHADOW_SPREAD)
        radius = float(self.CORNER_RADIUS)

        inner = rect.adjusted(spread, spread, -spread, -spread)
        shadow_img = self._render_shadow(rect, inner, radius, spread)

        clip = QPainterPath()
        clip.addRoundedRect(rect, radius + spread, radius + spread)
        clip.addRoundedRect(inner, radius, radius)
        clip.setFillRule(Qt.FillRule.OddEvenFill)
        painter.setClipPath(clip)

        painter.setOpacity(0.30)
        painter.drawImage(rect.topLeft(), shadow_img)
        painter.setOpacity(1.0)
        painter.setClipping(False)

        bg_path = QPainterPath()
        bg_path.addRoundedRect(inner, radius, radius)
        painter.fillPath(bg_path, QColor("#FFFFFF"))

    @staticmethod
    def _render_shadow(
        outer: QRectF, inner: QRectF, radius: float, spread: float
    ) -> QImage:
        w = int(outer.width())
        h = int(outer.height())
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(inner, radius, radius)
        p.fillPath(path, QColor(0, 0, 0, 255))
        p.end()

        src = img
        for _ in range(3):
            tmp = QImage(img.size(), QImage.Format.Format_ARGB32)
            tmp.fill(Qt.GlobalColor.transparent)
            p = QPainter(tmp)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.drawImage(QPoint(2, 0), src)
            p.drawImage(QPoint(-2, 0), src)
            p.drawImage(QPoint(0, 2), src)
            p.drawImage(QPoint(0, -2), src)
            p.drawImage(QPoint(1, 1), src)
            p.drawImage(QPoint(-1, -1), src)
            p.drawImage(QPoint(1, -1), src)
            p.drawImage(QPoint(-1, 1), src)
            p.drawImage(QPoint(0, 0), src)
            p.end()
            src = tmp

        return src

    def add_action_item(self, text: str, callback, active: bool = False) -> FigmaPopupItem:
        item = FigmaPopupItem(text, callback=callback, active=active)
        self._add_item(item)
        return item

    def add_submenu_item(self, text: str, submenu: "FigmaPopupMenu", active: bool = False) -> FigmaPopupItem:
        item = FigmaPopupItem(text, submenu=submenu, active=active)
        self._submenus.append(submenu)
        self._add_item(item)
        return item

    def add_separator(self) -> None:
        line = QFrame(self.panel)
        line.setObjectName("figmaPopupSeparator")
        line.setFrameShape(QFrame.Shape.NoFrame)
        line.setFixedHeight(1)
        self.panel_layout.addWidget(line)

    def _add_item(self, item: FigmaPopupItem) -> None:
        item.setParent(self.panel)
        item.setFixedWidth(self._panel_width - 8)
        self._items.append(item)
        self.panel_layout.addWidget(item)
        if item.property("active"):
            self._active_item = item

    def set_active_item(self, item: FigmaPopupItem) -> None:
        for current in self._items:
            current.setProperty("active", current is item)
            current.style().unpolish(current)
            current.style().polish(current)
            current.update()
            if current is not item and current.submenu is not None:
                current.submenu.hide_chain()
        self._active_item = item

    def show_at(self, panel_top_left: QPoint) -> None:
        self.adjustSize()
        self.move(panel_top_left - QPoint(self.SHADOW_SPREAD, self.SHADOW_SPREAD))
        self.show()
        self.raise_()

    def hide_chain(self) -> None:
        for submenu in self._submenus:
            submenu.hide_chain()
        self.hide()

    def close_chain(self) -> None:
        for submenu in self._submenus:
            submenu.close_chain()
        self.close()


class WindowControlButton(QPushButton):
    def __init__(self, control: str, parent=None) -> None:
        super().__init__(parent)
        self.control = control
        self.setObjectName("windowControlButton")
        self.setFixedSize(46, TITLE_BAR_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.underMouse():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F9FAFB"))
            painter.drawRect(self.rect())
        painter.setPen(QColor("#000000"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.control == "min":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#000000"))
            painter.drawRoundedRect(17, 18, 12, 1, 0.5, 0.5)
        elif self.control == "max":
            pen = painter.pen()
            pen.setWidthF(0.8)
            painter.setPen(pen)
            painter.drawRect(17, 12, 11, 11)
        else:
            pen = painter.pen()
            pen.setWidthF(0.8)
            painter.setPen(pen)
            painter.drawLine(17, 12, 28, 23)
            painter.drawLine(28, 12, 17, 23)


class TopBar(QFrame):
    """Figma-style title/menu bar with custom window controls."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window = window
        self._drag_offset: QPoint | None = None
        self.setObjectName("topBar")
        self.setFixedHeight(TITLE_BAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 0, 0)
        layout.setSpacing(8)

        self._menus: list[FigmaPopupMenu] = []
        layout.addWidget(self._menu_button("文件", self._file_menu()))
        layout.addWidget(self._menu_button("设置", self._settings_menu()))
        layout.addWidget(self._menu_button("模型", self._model_menu()))
        layout.addWidget(self._menu_button("帮助", self._help_menu()))
        layout.addStretch(1)

        self._min_btn = WindowControlButton("min", self)
        self._max_btn = WindowControlButton("max", self)
        self._close_btn = WindowControlButton("close", self)
        self._min_btn.clicked.connect(window.showMinimized)
        self._max_btn.clicked.connect(self._toggle_maximized)
        self._close_btn.clicked.connect(window.close)
        layout.addWidget(self._min_btn)
        layout.addWidget(self._max_btn)
        layout.addWidget(self._close_btn)

    def _menu(self, width: int = 126, spacing: int = 4) -> FigmaPopupMenu:
        menu = FigmaPopupMenu(width, self, spacing=spacing)
        self._menus.append(menu)
        return menu

    def _menu_button(self, text: str, menu: FigmaPopupMenu) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName("topMenuButton")
        button.setFixedSize(40, 28)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, b=button, m=menu: self._show_menu(b, m))
        return button

    def _show_menu(self, button: QPushButton, menu: FigmaPopupMenu) -> None:
        for current in self._menus:
            if current is not menu:
                current.hide_chain()
        menu.show_at(button.mapToGlobal(QPoint(8, button.height())))

    def _file_menu(self) -> FigmaPopupMenu:
        menu = self._menu()
        menu.add_action_item("打开视频", self._window._choose_input, active=True)
        menu.add_separator()
        menu.add_action_item("退出", self._window.close)
        return menu

    def _settings_menu(self) -> FigmaPopupMenu:
        menu = self._menu()
        menu.add_action_item("模型目录", self._window._change_model_dir, active=True)
        menu.add_action_item("输出目录", self._window._change_output_dir)
        menu.add_separator()
        menu.add_action_item("卸载应用", self._window._uninstall_app)
        return menu

    def _model_menu(self) -> FigmaPopupMenu:
        menu = self._menu(spacing=6)
        for name, cfg in MODEL_DEFS.items():
            sub = self._menu(spacing=6)
            for index, url in enumerate(cfg["urls"]):
                source = "镜像" if index == 0 else ("官方" if index == 1 else "代理")
                sub.add_action_item(f"{source}：{_short_path(url, 22)}", lambda u=url: QDesktopServices.openUrl(QUrl(u)), active=index == 0)
            menu.add_submenu_item(name.split(" (")[0], sub, active=name.startswith("Small"))
        return menu

    def _help_menu(self) -> FigmaPopupMenu:
        menu = self._menu()
        menu.add_action_item(
            "关于",
            lambda: _show_dialog(
                    self._window,
                    "关于",
                    f"{APP_TITLE}\n\n基于 Depth Anything V2 的视频深度图转换工具\n{GITHUB_URL}",
                ),
            active=True,
        )
        menu.add_action_item("Github", lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        return menu

    def _toggle_maximized(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
            self._window.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        else:
            self._window.showMaximized()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton and not self._window.isMaximized():
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class FullscreenVideoDialog(QDialog):
    """Simple fullscreen player used by both input and output previews."""

    def __init__(
        self,
        parent: QWidget | None,
        path: str,
        position: int,
        volume: float,
        muted: bool,
        should_play: bool,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._position = max(0, position)
        self._should_play = should_play
        self.setWindowTitle(APP_TITLE)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setStyleSheet("QDialog { background: #000000; } QVideoWidget { background: #000000; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._video = QVideoWidget(self)
        self._video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        layout.addWidget(self._video)

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(volume)
        self._audio.setMuted(muted)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video)
        self._player.mediaStatusChanged.connect(self._on_media_status)
        self._player.setSource(QUrl.fromLocalFile(path))
        QTimer.singleShot(0, self._start)

    def _start(self) -> None:
        if self._position:
            self._player.setPosition(self._position)
        self._player.play()
        if not self._should_play:
            QTimer.singleShot(180, self._player.pause)

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status in {
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        } and self._position:
            self._player.setPosition(self._position)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in {Qt.Key.Key_Escape, Qt.Key.Key_F}:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        self.close()
        event.accept()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._player.stop()
        self._player.setSource(QUrl())
        super().closeEvent(event)


class VideoPlayer(QFrame):
    """Native media player with audio, mute, volume, and seek controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("videoPlayer")
        self.setFixedSize(INNER_WIDTH, MEDIA_AREA_HEIGHT)
        self._duration = 0
        self._slider_dragging = False
        self._source_path: str | None = None

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(0.8)
        self._player.setAudioOutput(self._audio)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._video_box = QFrame()
        self._video_box.setObjectName("videoSurface")
        self._video_box.setFixedSize(INNER_WIDTH, VIDEO_SURFACE_HEIGHT)
        self._video_box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._apply_rounded_mask(self._video_box)
        self._video_stack = QStackedLayout(self._video_box)
        self._video_stack.setContentsMargins(6, 6, 6, 6)
        self._video_stack.setStackingMode(QStackedLayout.StackingMode.StackOne)

        self._placeholder = QLabel("尚未加载视频")
        self._placeholder.setObjectName("videoPlaceholder")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_stack.addWidget(self._placeholder)

        self._preview = QLabel()
        self._preview.setObjectName("videoPreview")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_stack.addWidget(self._preview)

        self._video = QVideoWidget()
        self._video.setObjectName("videoWidget")
        self._video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._video_stack.addWidget(self._video)
        self._video_stack.setCurrentWidget(self._placeholder)

        self._player.setVideoOutput(self._video)
        layout.addWidget(self._video_box, 1)

        self._fullscreen_btn = QPushButton(self)
        self._fullscreen_btn.setObjectName("fullscreenButton")
        self._fullscreen_btn.setFixedSize(24, 24)
        self._fullscreen_btn.move(INNER_WIDTH - 32, VIDEO_SURFACE_HEIGHT - 32)
        _set_icon(self._fullscreen_btn, "icon-fullscreen.png", 16)
        self._fullscreen_btn.clicked.connect(self._open_fullscreen)
        self._fullscreen_btn.hide()

        controls_widget = QFrame(self)
        controls_widget.setObjectName("transportControls")
        controls_widget.setFixedSize(INNER_WIDTH, TRANSPORT_HEIGHT)
        controls = QHBoxLayout(controls_widget)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(12)
        self._play_btn = IconButton("icon-play.png", self, size=32)
        self._play_btn.clicked.connect(self._toggle_play)
        controls.addWidget(self._play_btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setMinimumWidth(160)
        self._slider.sliderPressed.connect(self._on_slider_press)
        self._slider.sliderReleased.connect(self._on_slider_release)
        controls.addWidget(self._slider, 1)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setObjectName("muted")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_label.setFixedWidth(88)
        controls.addWidget(self._time_label)

        self._mute_btn = IconButton("icon-volume.png", self, size=32)
        self._mute_btn.clicked.connect(self._toggle_mute)
        controls.addWidget(self._mute_btn)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setObjectName("volumeSlider")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.setFixedWidth(88)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        controls.addWidget(self._volume_slider)

        layout.addWidget(controls_widget)

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.errorOccurred.connect(self._on_error)

    def _apply_rounded_mask(self, widget: QWidget) -> None:
        mask = QBitmap(widget.size())
        mask.fill(Qt.GlobalColor.color0)
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.GlobalColor.color1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(widget.rect(), 16, 16)
        painter.end()
        widget.setMask(mask)

    def load(self, path: str) -> None:
        self.stop()
        self._source_path = path
        self._duration = 0
        self._player.setSource(QUrl.fromLocalFile(path))
        self._show_preview(path)
        self._fullscreen_btn.show()
        self._fullscreen_btn.raise_()
        self._slider.setRange(0, 0)
        self._slider.setValue(0)
        self._time_label.setText("0:00 / 0:00")

    def stop(self) -> None:
        self._player.stop()
        self._play_btn.set_icon_name("icon-play.png")

    def _toggle_play(self) -> None:
        if self._player.source().isEmpty():
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._video_stack.setCurrentWidget(self._video)
            self._player.play()

    def _toggle_mute(self) -> None:
        self._audio.setMuted(not self._audio.isMuted())
        self._update_volume_icon()

    def _on_volume_changed(self, value: int) -> None:
        self._audio.setVolume(value / 100)
        if value > 0 and self._audio.isMuted():
            self._audio.setMuted(False)
        if value == 0 and not self._audio.isMuted():
            self._audio.setMuted(True)
        self._update_volume_icon()

    def _on_slider_press(self) -> None:
        self._slider_dragging = True

    def _on_slider_release(self) -> None:
        self._slider_dragging = False
        self._player.setPosition(self._slider.value())

    def _on_position_changed(self, position: int) -> None:
        if not self._slider_dragging:
            self._slider.setValue(position)
        self._update_time(position, self._duration)

    def _on_duration_changed(self, duration: int) -> None:
        self._duration = max(0, duration)
        self._slider.setRange(0, self._duration)
        self._update_time(self._player.position(), self._duration)

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        icon = "icon-pause.png" if state == QMediaPlayer.PlaybackState.PlayingState else "icon-play.png"
        self._play_btn.set_icon_name(icon)

    def _on_error(self, error, error_string: str) -> None:
        if error != QMediaPlayer.Error.NoError:
            self._placeholder.setText("无法播放视频")
            self._video_stack.setCurrentWidget(self._placeholder)
            self._fullscreen_btn.hide()
            self._time_label.setText("无法播放")

    def _show_preview(self, path: str) -> None:
        pixmap = self._first_frame_pixmap(path)
        if pixmap is None:
            self._placeholder.setText(Path(path).name)
            self._video_stack.setCurrentWidget(self._placeholder)
            return
        target = QSize(INNER_WIDTH - 12, VIDEO_SURFACE_HEIGHT - 12)
        self._preview.setPixmap(
            pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._preview.setText("")
        self._video_stack.setCurrentWidget(self._preview)

    def _first_frame_pixmap(self, path: str) -> QPixmap | None:
        try:
            import cv2

            cap = cv2.VideoCapture(path)
            ok, frame = cap.read()
            cap.release()
            if not ok or frame is None:
                return None
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, channels = rgb.shape
            image = QImage(rgb.data, w, h, channels * w, QImage.Format.Format_RGB888).copy()
            return QPixmap.fromImage(image)
        except Exception:
            return None

    def _open_fullscreen(self) -> None:
        if not self._source_path:
            return
        dialog = FullscreenVideoDialog(
            self.window(),
            self._source_path,
            self._player.position(),
            self._audio.volume(),
            self._audio.isMuted(),
            self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState,
        )
        dialog.showFullScreen()
        dialog.exec()

    def _update_volume_icon(self) -> None:
        muted = self._audio.isMuted() or self._volume_slider.value() == 0
        self._mute_btn.set_icon_name("icon-volume-muted.png" if muted else "icon-volume.png")

    def _update_time(self, position: int, duration: int) -> None:
        def fmt(ms: int) -> str:
            secs = max(0, int(ms / 1000))
            return f"{secs // 60}:{secs % 60:02d}"
        self._time_label.setText(f"{fmt(position)} / {fmt(duration)}")

    def cleanup(self) -> None:
        self.stop()
        self._player.setSource(QUrl())
        self._source_path = None
        self._preview.clear()
        self._placeholder.setText("尚未加载视频")
        self._video_stack.setCurrentWidget(self._placeholder)
        self._fullscreen_btn.hide()


class DropPanel(QFrame):
    file_dropped = Signal(str)
    browse_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropPanel")
        self.setAcceptDrops(True)
        self.setFixedSize(INNER_WIDTH, VIDEO_SURFACE_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("拖入视频文件")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("支持 MP4 / MOV / M4V / AVI / MKV / WEBM")
        subtitle.setObjectName("muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.choose_button = QPushButton("选择视频")
        self.choose_button.setObjectName("secondaryButton")
        self.choose_button.setFixedHeight(32)
        self.choose_button.clicked.connect(self.browse_requested.emit)

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.choose_button)
        layout.addStretch(1)

    def set_file(self, path: str | None) -> None:
        self.choose_button.setText(Path(path).name if path else "选择视频")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._first_video_path(event.mimeData().urls()):
            event.acceptProposedAction()
            self.setProperty("dragging", True)
            self.style().unpolish(self)
            self.style().polish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)
        path = self._first_video_path(event.mimeData().urls())
        if path:
            self.file_dropped.emit(path)
            event.acceptProposedAction()
        else:
            event.ignore()

    @staticmethod
    def _first_video_path(urls) -> str | None:
        for url in urls:
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in VIDEO_EXTENSIONS and path.is_file():
                return str(path)
        return None


class ConversionWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        input_path: str,
        output_dir: str,
        model_label: str,
        resolution: str,
        invert: bool,
        smoothing: int,
        preserve_audio: bool,
    ) -> None:
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.model_label = model_label
        self.resolution = resolution
        self.invert = invert
        self.smoothing = smoothing
        self.preserve_audio = preserve_audio

    def run(self) -> None:
        try:
            def report(fraction: float, description: str) -> None:
                percent = max(0, min(100, int(round(fraction * 100))))
                self.progress.emit(percent, description)

            report(0.0, "准备开始转换")
            temp_result = process_video(
                input_video_path=self.input_path,
                model_size_label=self.model_label,
                resolution_choice=self.resolution,
                invert_bw=self.invert,
                smoothing_strength=float(self.smoothing),
                preserve_audio=self.preserve_audio,
                progress=report,
            )

            final_path = _unique_output_path(self.input_path, self.output_dir)
            temp_dir = Path(temp_result).parent
            shutil.move(temp_result, final_path)
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.progress.emit(100, "转换完成")
            self.finished.emit(str(final_path))
        except Exception as exc:
            traceback.print_exc()
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ContourControlWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.input_path: str | None = None
        self.output_path: str | None = None
        self.worker_thread: QThread | None = None
        self.worker: ConversionWorker | None = None

        self.setWindowTitle(APP_TITLE)
        if sys.platform != "darwin":
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setMinimumSize(QSize(WINDOW_WIDTH, WINDOW_HEIGHT))
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        icon_path = _asset_path(APP_ICON_ICO)
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._build_ui()
        self._refresh_status()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        if sys.platform == "darwin":
            self._build_menubar()
        else:
            main.addWidget(TopBar(self))

        content = QHBoxLayout()
        top_margin = 16 if sys.platform == "darwin" else 4
        content.setContentsMargins(16, top_margin, 16, 16)
        content.setSpacing(24)
        content.addWidget(self._build_left_panel(), 0)
        content.addWidget(self._build_right_panel(), 0)
        main.addLayout(content)

    def _build_menubar(self) -> None:
        mb = self.menuBar()
        mb.clear()
        if sys.platform == "darwin":
            mb.setNativeMenuBar(True)
        else:
            mb.setStyleSheet("""
                QMenuBar { background: #FFFFFF; color: #374151; border-bottom: 1px solid #E5E7EB; padding: 2px 8px; }
                QMenuBar::item { padding: 6px 12px; border-radius: 4px; }
                QMenuBar::item:selected { background: #F3F4F6; }
                QMenu { background: #FFFFFF; color: #374151; border: 1px solid #E5E7EB; padding: 4px; margin: 0; }
                QMenu::item { padding: 8px 24px; border-radius: 4px; }
                QMenu::item:selected { background: #F3F4F6; }
                QMenu::separator { height: 1px; background: #E5E7EB; margin: 4px 12px; }
            """)

        file_menu = mb.addMenu("文件")
        open_act = QAction("打开视频", self)
        open_act.triggered.connect(self._choose_input)
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        quit_act = QAction("退出", self)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        settings_menu = mb.addMenu("设置")
        model_dir_act = QAction("模型目录...", self)
        model_dir_act.triggered.connect(self._change_model_dir)
        settings_menu.addAction(model_dir_act)
        output_dir_act = QAction("输出目录...", self)
        output_dir_act.triggered.connect(self._change_output_dir)
        settings_menu.addAction(output_dir_act)
        settings_menu.addSeparator()
        uninstall_act = QAction("卸载应用", self)
        uninstall_act.triggered.connect(self._uninstall_app)
        settings_menu.addAction(uninstall_act)

        model_menu = mb.addMenu("模型")
        for name, cfg in MODEL_DEFS.items():
            sub = model_menu.addMenu(name.split(" (")[0])
            for url in cfg["urls"]:
                label = "镜像" if "hf-mirror" in url else ("代理" if "ghproxy" in url else "官方")
                act = QAction(f"{label}: {url[:50]}...", self)
                act.triggered.connect(lambda checked, u=url: QDesktopServices.openUrl(QUrl(u)))
                sub.addAction(act)

        help_menu = mb.addMenu("帮助")
        about_act = QAction("关于", self)
        about_act.triggered.connect(lambda: _show_dialog(self, "关于", f"{APP_TITLE}\n\n基于 Depth Anything V2 的视频深度图转换工具\n{GITHUB_URL}"))
        help_menu.addAction(about_act)
        github_act = QAction("GitHub 主页", self)
        github_act.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        help_menu.addAction(github_act)

    def _uninstall_app(self) -> None:
        import subprocess
        candidates = [
            Path(__file__).resolve().parent.parent / "unins000.exe",
            Path(__file__).resolve().parent / "unins000.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / APP_TITLE / "unins000.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Contour Control Tool" / "unins000.exe",
        ]
        for uninstall_exe in candidates:
            if uninstall_exe.is_file():
                subprocess.Popen([str(uninstall_exe)])
                self.close()
                return
        _show_dialog(self, "卸载", "未找到卸载程序。\n请手动删除安装目录。")

    def _change_model_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择模型目录", str(MODELS_DIR))
        if d:
            os.environ["DEPTH_MODELS_DIR"] = d
            import depth_converter.models as _m
            _m.MODELS_DIR = Path(d)
            self._refresh_models()

    def _change_output_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择默认输出目录", str(Path.home() / "Desktop"))
        if d:
            self.output_dir = d
            self.output_dir_label.setText(f"输出到： {_short_path(d, 28)}")
            self.output_dir_label.setToolTip(d)

    def _open_model_dir(self) -> None:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(MODELS_DIR))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(MODELS_DIR)))
        self._refresh_models()

    def _refresh_models(self) -> None:
        current = _combo_value(self.model_combo)
        self.model_combo.clear()
        items = list(MODEL_DEFS.keys())
        for key in items:
            self.model_combo.addItem(_model_display_label(key), key)
        if MODELS_DIR.is_dir():
            for f in sorted(
                p for p in MODELS_DIR.iterdir() if p.is_file() and p.suffix.lower() in MODEL_FILE_SUFFIXES
            ):
                name = f.stem
                if not any(name == Path(cfg["path"]).stem for cfg in MODEL_DEFS.values()):
                    custom = f"{name} (自定义)"
                    items.append(custom)
                    self.model_combo.addItem(custom, custom)
        if current in items:
            _set_combo_data(self.model_combo, current)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(16)

        self.device_badge = QLabel("检测设备中")
        self.device_badge.setObjectName("badge")
        self.ffmpeg_badge = QLabel("FFmpeg")
        self.ffmpeg_badge.setObjectName("badge")

        header.addStretch(1)
        header.addWidget(self.device_badge)
        header.addWidget(self.ffmpeg_badge)
        return header

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedSize(PANEL_WIDTH, PANEL_HEIGHT)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        section = QLabel("输入视频")
        section.setObjectName("sectionTitle")
        section.setFixedHeight(20)
        layout.addWidget(section)

        media_area = QWidget()
        media_area.setFixedSize(INNER_WIDTH, MEDIA_AREA_HEIGHT)
        self.input_media_stack = QStackedLayout(media_area)
        self.input_media_stack.setContentsMargins(0, 0, 0, 0)

        empty_media = QWidget()
        empty_media.setFixedSize(INNER_WIDTH, MEDIA_AREA_HEIGHT)
        empty_layout = QVBoxLayout(empty_media)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setSpacing(12)
        self.drop_panel = DropPanel()
        self.drop_panel.file_dropped.connect(self._set_input_path)
        self.drop_panel.browse_requested.connect(self._choose_input)
        empty_layout.addWidget(self.drop_panel)
        empty_layout.addWidget(StaticTransportControls(self))
        self.input_media_stack.addWidget(empty_media)

        self._src_player = VideoPlayer()
        self.input_media_stack.addWidget(self._src_player)
        self.input_media_stack.setCurrentWidget(empty_media)
        layout.addWidget(media_area)

        settings_title = QLabel("转换参数")
        settings_title.setObjectName("sectionTitle")
        settings_title.setFixedHeight(20)
        layout.addWidget(settings_title)

        self.model_combo = FigmaComboBox()
        for key in MODEL_DEFS:
            self.model_combo.addItem(_model_display_label(key), key)
        _set_combo_data(self.model_combo, DEFAULT_MODEL_LABEL)
        _configure_combo(self.model_combo)

        self.model_folder_btn = IconButton("icon-folder.png", self)
        self.model_folder_btn.setFixedSize(32, 32)
        self.model_folder_btn.clicked.connect(self._open_model_dir)

        self.resolution_combo = FigmaComboBox()
        for key in RESOLUTION_PRESETS:
            self.resolution_combo.addItem(key, key)
        _set_combo_data(self.resolution_combo, "Original")
        _configure_combo(self.resolution_combo)

        self.smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setRange(0, 100)
        self.smoothing_slider.setValue(60)
        self.smoothing_slider.setMinimumWidth(320)
        self.smoothing_value = QLabel("60")
        self.smoothing_value.setObjectName("muted")
        self.smoothing_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.smoothing_value.setFixedWidth(28)
        self.smoothing_slider.valueChanged.connect(lambda value: self.smoothing_value.setText(str(value)))

        model_row_widget = QWidget()
        model_row_widget.setFixedSize(INNER_WIDTH, 40)
        model_row = QHBoxLayout(model_row_widget)
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.setSpacing(12)
        model_row.addWidget(self._field_label("模型"))
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        model_row.addWidget(self.model_combo, 1)
        model_row.addWidget(self.model_folder_btn)
        layout.addWidget(model_row_widget)

        resolution_row_widget = QWidget()
        resolution_row_widget.setFixedSize(INNER_WIDTH, 40)
        resolution_row = QHBoxLayout(resolution_row_widget)
        resolution_row.setContentsMargins(0, 0, 0, 0)
        resolution_row.setSpacing(12)
        resolution_row.addWidget(self._field_label("分辨率"))
        self.resolution_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        resolution_row.addWidget(self.resolution_combo, 1)
        layout.addWidget(resolution_row_widget)

        smoothing_row_widget = QWidget()
        smoothing_row_widget.setFixedSize(INNER_WIDTH, 24)
        smoothing_row = QHBoxLayout(smoothing_row_widget)
        smoothing_row.setContentsMargins(0, 0, 0, 0)
        smoothing_row.setSpacing(12)
        smoothing_row.addWidget(self._field_label("平滑"))
        self.smoothing_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        smoothing_row.addWidget(self.smoothing_slider, 1)
        smoothing_row.addWidget(self.smoothing_value)
        layout.addWidget(smoothing_row_widget)

        self.invert_check = QCheckBox("黑白反转")
        self.invert_check.setFixedHeight(24)
        self.preserve_audio_check = QCheckBox("保留原声")
        self.preserve_audio_check.setFixedHeight(24)
        self.preserve_audio_check.setChecked(True)
        layout.addWidget(self.invert_check)
        layout.addWidget(self.preserve_audio_check)

        output_row_widget = QWidget()
        output_row_widget.setFixedSize(INNER_WIDTH, 36)
        output_row = QHBoxLayout(output_row_widget)
        output_row.setContentsMargins(0, 0, 0, 0)
        self.output_dir_label = QLabel("输出到： 跟随输入视频")
        self.output_dir_label.setObjectName("muted")
        self.output_dir_label.setFixedHeight(36)
        self.output_btn = QPushButton("输出位置")
        self.output_btn.setObjectName("secondaryButton")
        self.output_btn.setFixedSize(84, 32)
        self.output_btn.clicked.connect(self._choose_output_dir)
        output_row.addWidget(self.output_dir_label, 1)
        output_row.addWidget(self.output_btn)
        layout.addWidget(output_row_widget)

        self.start_btn = QPushButton("开始转换")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setFixedHeight(48)
        self.start_btn.clicked.connect(self._start_conversion)
        layout.addWidget(self.start_btn)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedSize(PANEL_WIDTH, PANEL_HEIGHT)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("深度视频")
        title.setObjectName("sectionTitle")
        title.setFixedHeight(20)
        layout.addWidget(title)

        self._video_player = VideoPlayer()
        layout.addWidget(self._video_player)

        status_title = QLabel("任务状态")
        status_title.setObjectName("sectionTitle")
        status_title.setFixedHeight(20)
        layout.addWidget(status_title)
        self.state_label = QLabel("等待视频")
        self.state_label.setVisible(False)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedSize(INNER_WIDTH, 14)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("选择一个视频后开始转换。")
        self.progress_label.setObjectName("muted")
        self.progress_label.setFixedHeight(20)
        layout.addWidget(self.progress_label)

        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("logBox")
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("转换进度和模型下载状态会显示在这里")
        self.log_box.setFixedSize(INNER_WIDTH, 164)
        layout.addWidget(self.log_box)

        result = QFrame()
        result.setObjectName("resultPanel")
        result.setFixedSize(INNER_WIDTH, 72)
        result_layout = QHBoxLayout(result)
        result_layout.setContentsMargins(12, 10, 12, 10)
        result_layout.setSpacing(12)

        self.result_label = QLabel("尚未生成输出视频")
        self.result_label.setObjectName("resultText")
        self.result_label.setWordWrap(True)
        self.open_output_btn = QPushButton("打开视频")
        self.open_folder_btn = QPushButton("打开文件夹")
        for button in (self.open_output_btn, self.open_folder_btn):
            button.setObjectName("secondaryButton")
            button.setFixedSize(84, 32)
            button.setEnabled(False)
        self.open_output_btn.clicked.connect(self._open_output)
        self.open_folder_btn.clicked.connect(self._open_output_folder)

        result_layout.addWidget(self.result_label, 1)
        result_layout.addWidget(self.open_output_btn)
        result_layout.addWidget(self.open_folder_btn)
        layout.addWidget(result)
        return panel

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        label.setFixedWidth(44)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _refresh_status(self) -> None:
        device_type, device_desc = detect_device()
        self.device_type = device_type
        self.device_desc = device_desc
        self.ffmpeg_ready = ffmpeg_available()

    def _choose_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频",
            str(Path.home()),
            "Video files (*.mp4 *.mov *.m4v *.avi *.mkv *.webm);;All files (*.*)",
        )
        if path:
            self._set_input_path(path)

    def _set_input_path(self, path: str) -> None:
        self.input_path = path
        self.drop_panel.set_file(path)
        self.input_media_stack.setCurrentWidget(self._src_player)
        self._src_player.load(path)
        if not hasattr(self, "output_dir"):
            self.output_dir = str(_default_output_dir(path))
            self.output_dir_label.setText(f"输出到： {_short_path(self.output_dir, 28)}")
        self.output_dir_label.setToolTip(self.output_dir)
        self.progress_label.setText("选择一个视频后开始转换。")
        self.state_label.setText("已选择视频")

    def _choose_output_dir(self) -> None:
        start_dir = getattr(self, "output_dir", str(_default_output_dir(self.input_path)))
        path = QFileDialog.getExistingDirectory(self, "选择输出文件夹", start_dir)
        if path:
            self.output_dir = path
            self.output_dir_label.setText(f"输出到： {_short_path(path, 28)}")

    def _start_conversion(self) -> None:
        if self.worker_thread is not None and self.worker_thread.isRunning():
            return
        if not self.input_path or not Path(self.input_path).is_file():
            _show_dialog(self, APP_TITLE, "请先选择一个视频文件。")
            return
        if not ffmpeg_available():
            _show_dialog(self, APP_TITLE, "FFmpeg 未就绪，无法编码输出视频。")
            return

        output_dir = getattr(self, "output_dir", str(_default_output_dir(self.input_path)))
        self.output_path = None
        self.open_output_btn.setEnabled(False)
        self.open_folder_btn.setEnabled(False)
        self.result_label.setText("正在生成输出视频")
        self.progress_bar.setValue(0)
        self.state_label.setText("转换中")
        self._set_controls_enabled(False)
        self._append_log("开始转换。")

        self.worker_thread = QThread(self)
        self.worker = ConversionWorker(
            input_path=self.input_path,
            output_dir=output_dir,
            model_label=_combo_value(self.model_combo),
            resolution=_combo_value(self.resolution_combo),
            invert=self.invert_check.isChecked(),
            smoothing=self.smoothing_slider.value(),
            preserve_audio=self.preserve_audio_check.isChecked(),
        )
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._clear_worker)
        self.worker_thread.start()

    def _on_progress(self, percent: int, description: str) -> None:
        self.progress_bar.setValue(percent)
        self.progress_label.setText(description)
        if not description.startswith("正在下载模型"):
            self._append_log(f"{percent:3d}%  {description}")

    def _on_finished(self, output_path: str) -> None:
        self.output_path = output_path
        self.state_label.setText("已完成")
        self.result_label.setText(_short_path(output_path, 90))
        self.result_label.setToolTip(output_path)
        self.open_output_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(True)
        self._set_controls_enabled(True)
        self._append_log(f"完成：{output_path}")
        self._video_player.load(output_path)
        _show_dialog(self, APP_TITLE, "转换完成。")

    def _on_failed(self, message: str) -> None:
        self.state_label.setText("失败")
        self.progress_label.setText(message)
        self.result_label.setText("转换失败")
        self._set_controls_enabled(True)
        self._append_log(f"失败：{message}")
        _show_dialog(self, APP_TITLE, message)

    def _clear_worker(self) -> None:
        self.worker = None
        self.worker_thread = None

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.start_btn.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.model_folder_btn.setEnabled(enabled)
        self.resolution_combo.setEnabled(enabled)
        self.smoothing_slider.setEnabled(enabled)
        self.invert_check.setEnabled(enabled)
        self.preserve_audio_check.setEnabled(enabled)
        self.output_btn.setEnabled(enabled)

    def _append_log(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_box.appendPlainText(f"[{stamp}] {text}")

    def _open_output(self) -> None:
        if self.output_path and Path(self.output_path).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_path))

    def _open_output_folder(self) -> None:
        if self.output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.output_path).parent)))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker_thread is not None and self.worker_thread.isRunning():
            _show_dialog(self, APP_TITLE, "转换正在进行，请完成后再关闭。")
            event.ignore()
            return
        event.accept()


def apply_style(app: QApplication) -> None:
    base_font = "PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei UI"
    app.setFont(QFont(base_font, 10))
    check_icon = str(_asset_path("checkmark.png")).replace("\\", "/")
    chevron_icon = str(_asset_path("icon-chevron-down.png")).replace("\\", "/")
    right_arrow_icon = str(_asset_path("icon-chevron-right.png")).replace("\\", "/")
    app.setStyleSheet(
        """
        QWidget#root {
            background: #FFFFFF;
            color: #0F1828;
            font-family: "PingFang SC", "Microsoft YaHei UI", "Segoe UI";
            font-size: 12px;
        }
        QLabel {
            color: #0F1828;
        }
        QLabel#sectionTitle {
            color: #0F1828;
            font-size: 12px;
            font-weight: 500;
        }
        QLabel#muted {
            color: #6C7583;
            font-size: 12px;
            font-weight: 500;
        }
        QLabel#fieldLabel {
            color: #6C7583;
            font-size: 12px;
            font-weight: 500;
        }
        QFrame#topBar {
            background: #FFFFFF;
            border: none;
        }
        QPushButton#topMenuButton {
            background: transparent;
            color: #6C7583;
            border: none;
            border-radius: 4px;
            padding: 0;
            text-align: left;
            font-size: 12px;
            font-weight: 400;
        }
        QPushButton#topMenuButton:hover {
            background: transparent;
        }
        QPushButton#topMenuButton:pressed {
            background: transparent;
        }
        QPushButton#windowControlButton {
            background: transparent;
            color: #111111;
            border: none;
            border-radius: 0;
            padding: 0;
            font-size: 18px;
            font-weight: 400;
        }
        QPushButton#windowControlButton:hover {
            background: #F3F4F6;
        }
        QPushButton#windowControlButton[role="close"]:hover {
            background: #E81123;
            color: #FFFFFF;
        }
        QWidget#figmaPopup {
            background: transparent;
        }
        QFrame#figmaPopupPanel {
            background: transparent;
            border: none;
            border-radius: 0;
        }
        QPushButton#figmaPopupItem {
            background: transparent;
            color: #6C7583;
            border: none;
            border-radius: 4px;
            padding: 0;
            text-align: left;
            font-size: 12px;
            font-weight: 400;
        }
        QFrame#figmaPopupSeparator {
            background: #ECECEC;
            border: none;
        }
        QMenu {
            background: #FFFFFF;
            color: #6C7583;
            border: none;
            border-radius: 4px;
            padding: 4px;
            font-family: "PingFang SC", "Microsoft YaHei UI", "Segoe UI";
            font-size: 12px;
        }
        QMenu::item {
            height: 25px;
            min-width: 110px;
            padding: 0 4px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background: #F9FAFB;
            color: #6C7583;
        }
        QMenu::separator {
            height: 1px;
            background: #F3F4F6;
            margin: 4px;
        }
        QMenu::right-arrow {
            image: url(""" + right_arrow_icon + """);
            width: 16px;
            height: 16px;
            padding-right: 0;
        }
        QFrame#panel {
            background: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 16px;
        }
        QFrame#dropPanel {
            background: #F9FAFB;
            border: 2px dashed #D0D5DC;
            border-radius: 16px;
        }
        QFrame#dropPanel[dragging="true"] {
            background: #F3F4F6;
            border: 2px solid #D0D5DC;
        }
        QFrame#videoPlayer {
            background: transparent;
            border: none;
        }
        QFrame#transportControls {
            background: transparent;
            border: none;
        }
        QFrame#videoSurface {
            background: #000000;
            border-radius: 16px;
        }
        QVideoWidget#videoWidget {
            background: #000000;
            border-radius: 12px;
        }
        QLabel#videoPlaceholder {
            background: #000000;
            color: #9AA3B0;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        QLabel#videoPreview {
            background: #000000;
            border-radius: 12px;
        }
        QLabel#dropTitle {
            color: #0F1828;
            font-size: 14px;
            font-weight: 600;
        }
        QPushButton#fullscreenButton {
            background: rgba(0, 0, 0, 77);
            color: #FFFFFF;
            border: none;
            border-radius: 4px;
            padding: 0;
        }
        QPushButton#fullscreenButton:hover {
            background: rgba(0, 0, 0, 96);
        }
        QPushButton#fullscreenButton:pressed {
            background: rgba(0, 0, 0, 120);
        }
        QComboBox {
            background: #FFFFFF;
            color: #344252;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 0 34px 0 12px;
            font-size: 10px;
            font-weight: 500;
        }
        QComboBox:hover {
            border-color: #D0D5DC;
        }
        QComboBox:focus {
            border: 1px solid #D0D5DC;
        }
        QComboBox::drop-down {
            width: 30px;
            border: none;
        }
        QComboBox::down-arrow {
            image: url(""" + chevron_icon + """);
            width: 16px;
            height: 16px;
            margin-right: 12px;
        }
        QComboBox QAbstractItemView {
            background: #FFFFFF;
            color: #344252;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            selection-background-color: transparent;
            selection-color: #344252;
            outline: none;
            padding: 4px;
        }
        QCheckBox {
            spacing: 10px;
            color: #0F1828;
            font-size: 12px;
            font-weight: 500;
        }
        QCheckBox::indicator {
            width: 20px;
            height: 20px;
            border-radius: 4px;
            border: 1px solid #D0D5DC;
            background: #FFFFFF;
        }
        QCheckBox::indicator:hover {
            border-color: #6C7583;
        }
        QCheckBox::indicator:checked {
            background: #0F1828;
            border-color: #0F1828;
            image: url(""" + check_icon + """);
        }
        QSlider::groove:horizontal {
            height: 4px;
            border-radius: 2px;
            background: #E5E7EB;
        }
        QSlider::handle:horizontal {
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
            background: #121A2B;
        }
        QSlider::handle:horizontal:hover {
            background: #0F1828;
        }
        QSlider#volumeSlider::groove:horizontal {
            height: 4px;
            border-radius: 2px;
            background: #E5E7EB;
        }
        QSlider#volumeSlider::handle:horizontal {
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
            background: #121A2B;
        }
        QPushButton {
            border: none;
            border-radius: 8px;
            padding: 0 16px;
            font-size: 12px;
            font-weight: 600;
        }
        QPushButton#primaryButton {
            background: #0F1828;
            color: #FFFFFF;
            font-size: 14px;
        }
        QPushButton#primaryButton:hover {
            background: #121A2B;
        }
        QPushButton#primaryButton:pressed {
            background: #000000;
        }
        QPushButton#secondaryButton {
            background: #F3F4F6;
            color: #344252;
        }
        QPushButton#secondaryButton:hover {
            background: #E5E7EB;
        }
        QPushButton#secondaryButton:pressed {
            background: #D1D5DB;
        }
        QPushButton#iconButton {
            background: #F3F4F6;
            border: none;
            border-radius: 8px;
            padding: 0;
        }
        QPushButton#iconButton:hover {
            background: #E5E7EB;
        }
        QPushButton#iconButton:pressed {
            background: #D1D5DB;
        }
        QPushButton:disabled {
            background: #F9FAFB;
            color: #9CA3AF;
        }
        QProgressBar {
            background: #E5E7EB;
            border: none;
            border-radius: 6px;
        }
        QProgressBar::chunk {
            border-radius: 6px;
            background: #0F1828;
        }
        QPlainTextEdit#logBox {
            background: #FFFFFF;
            color: #344252;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 12px;
            font-family: "PingFang SC", "Microsoft YaHei UI", Consolas;
            font-size: 12px;
        }
        QFrame#resultPanel {
            background: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
        }
        QLabel#resultText {
            color: #6C7583;
            font-size: 12px;
            font-weight: 500;
        }
        QScrollBar:vertical {
            background: #F9FAFB;
            width: 8px;
            border: none;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background: #D1D5DB;
            min-height: 30px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background: #9CA3AF;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        QScrollBar:horizontal {
            height: 8px;
            background: #F9FAFB;
            border: none;
            border-radius: 4px;
        }
        QScrollBar::handle:horizontal {
            background: #D1D5DB;
            min-width: 30px;
            border-radius: 4px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #9CA3AF;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }
        """
    )


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("ZhaoDesign")
    apply_style(app)

    window = ContourControlWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        msg = traceback.format_exc()
        log_path = DATA_DIR / "crash.log"
        try:
            log_path.write_text(msg, encoding="utf-8")
        except OSError:
            pass
        _show_native_error(
            APP_TITLE,
            f"启动失败:\n\n{msg}\n\n日志: {log_path}",
        )
        sys.exit(1)
