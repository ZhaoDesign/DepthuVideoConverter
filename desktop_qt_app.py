#!/usr/bin/env python3
"""Native Qt desktop UI for Contour Control Tool."""

from __future__ import annotations

import os
import shutil
import sys
import time
import traceback
from pathlib import Path


APP_TITLE = "视频深度控制图工具"
APP_DIR_NAME = "DepthVideoConverter"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}

_script_dir = str(Path(__file__).resolve().parent)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)


def _user_data_dir() -> Path:
    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / APP_DIR_NAME


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

try:
    from PySide6.QtCore import QPoint, QObject, QSize, Qt, QThread, QUrl, Signal  # noqa: E402
    from PySide6.QtGui import QAction, QColor, QDesktopServices, QDragEnterEvent, QDropEvent, QFont, QIcon, QPainter  # noqa: E402
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer  # noqa: E402
    from PySide6.QtMultimediaWidgets import QVideoWidget  # noqa: E402
    from PySide6.QtWidgets import (  # noqa: E402
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QGraphicsDropShadowEffect,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QListView,
        QMainWindow,
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
    import ctypes

    msg = traceback.format_exc()
    log_path = DATA_DIR / "crash.log"
    try:
        log_path.write_text(msg, encoding="utf-8")
    except OSError:
        pass
    ctypes.windll.user32.MessageBoxW(
        0,
        f"运行环境加载失败，请检查安装是否完整。\n\n{msg}\n\n日志: {log_path}",
        APP_TITLE,
        0x10,
    )
    sys.exit(1)


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


def _set_icon(button: QPushButton, name: str, size: int = 20) -> None:
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


class FloatingToolTip(QFrame):
    """Small rounded tooltip with a controlled shadow."""

    def __init__(self, text: str) -> None:
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("floatingTip")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(17, 24, 39, 48))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        label = QLabel(text)
        label.setObjectName("floatingTipText")
        label.setWordWrap(False)
        layout.addWidget(label)


class IconButton(QPushButton):
    """Icon-only button with consistent size and custom tooltip styling."""

    def __init__(self, icon_name: str, tooltip_text: str, parent=None, size: int = 36) -> None:
        super().__init__(parent)
        self._tip = FloatingToolTip(tooltip_text)
        self.setObjectName("iconButton")
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        _set_icon(self, icon_name)

    def set_icon_name(self, icon_name: str) -> None:
        _set_icon(self, icon_name)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._tip.adjustSize()
        pos = self.mapToGlobal(QPoint((self.width() - self._tip.width()) // 2, self.height() + 8))
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            if pos.x() + self._tip.width() > available.right():
                pos.setX(available.right() - self._tip.width() - 8)
            if pos.x() < available.left():
                pos.setX(available.left() + 8)
        self._tip.move(pos)
        self._tip.show()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._tip.hide()
        super().leaveEvent(event)


class ComboItemDelegate(QStyledItemDelegate):
    """Paint combo popup items with rounded hover and selected states."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # type: ignore[override]
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        hovered = bool(opt.state & QStyle.StateFlag.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg_rect = opt.rect.adjusted(6, 3, -6, -3)
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#111827"))
            painter.drawRoundedRect(bg_rect, 7, 7)
        elif hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F3F4F6"))
            painter.drawRoundedRect(bg_rect, 7, 7)

        text_rect = opt.rect.adjusted(16, 0, -16, 0)
        painter.setPen(QColor("#FFFFFF" if selected else "#374151"))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, opt.text)
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
    combo.setMinimumHeight(38)
    combo.setCursor(Qt.CursorShape.PointingHandCursor)
    combo.view().window().setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)


class VideoPlayer(QFrame):
    """Native media player with audio, mute, volume, and seek controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("videoPlayer")
        self._duration = 0
        self._slider_dragging = False

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(0.8)
        self._player.setAudioOutput(self._audio)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._video_box = QFrame()
        self._video_box.setObjectName("videoSurface")
        self._video_box.setMinimumHeight(200)
        self._video_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_stack = QStackedLayout(self._video_box)
        self._video_stack.setContentsMargins(0, 0, 0, 0)
        self._video_stack.setStackingMode(QStackedLayout.StackingMode.StackOne)

        self._placeholder = QLabel("尚未加载视频")
        self._placeholder.setObjectName("videoPlaceholder")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_stack.addWidget(self._placeholder)

        self._video = QVideoWidget()
        self._video.setObjectName("videoWidget")
        self._video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._video_stack.addWidget(self._video)
        self._video_stack.setCurrentWidget(self._placeholder)

        self._player.setVideoOutput(self._video)
        layout.addWidget(self._video_box, 1)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self._play_btn = IconButton("icon-play.png", "播放 / 暂停", self)
        self._play_btn.clicked.connect(self._toggle_play)
        controls.addWidget(self._play_btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.sliderPressed.connect(self._on_slider_press)
        self._slider.sliderReleased.connect(self._on_slider_release)
        controls.addWidget(self._slider, 1)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setObjectName("muted")
        self._time_label.setFixedWidth(100)
        controls.addWidget(self._time_label)

        self._mute_btn = IconButton("icon-volume.png", "开启 / 关闭声音", self, size=32)
        self._mute_btn.clicked.connect(self._toggle_mute)
        controls.addWidget(self._mute_btn)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setObjectName("volumeSlider")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.setFixedWidth(86)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        controls.addWidget(self._volume_slider)

        layout.addLayout(controls)

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.errorOccurred.connect(self._on_error)

    def load(self, path: str) -> None:
        self.stop()
        self._duration = 0
        self._player.setSource(QUrl.fromLocalFile(path))
        self._video_stack.setCurrentWidget(self._video)
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
            self._time_label.setText("无法播放")

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
        self._placeholder.setText("尚未加载视频")
        self._video_stack.setCurrentWidget(self._placeholder)


class DropPanel(QFrame):
    file_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropPanel")
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        title = QLabel("拖入视频文件")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("支持 MP4 / MOV / M4V / AVI / MKV / WEBM")
        subtitle.setObjectName("muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.file_label = QLabel("尚未选择视频")
        self.file_label.setObjectName("filePill")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.file_label)
        layout.addStretch(1)

    def set_file(self, path: str | None) -> None:
        self.file_label.setText(Path(path).name if path else "尚未选择视频")

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
            shutil.copy2(temp_result, final_path)
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
        self.setMinimumSize(QSize(980, 680))
        self.resize(1120, 760)
        icon_path = _asset_path("depth-video-converter.ico")
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._build_ui()
        self._build_menubar()
        self._refresh_status()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(28, 24, 28, 24)
        main.setSpacing(20)

        main.addLayout(self._build_header())

        content = QHBoxLayout()
        content.setSpacing(20)
        content.addWidget(self._build_left_panel(), 0)
        content.addWidget(self._build_right_panel(), 1)
        main.addLayout(content, 1)

    def _build_menubar(self) -> None:
        mb = self.menuBar()
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

        model_menu = mb.addMenu("模型下载")
        for name, cfg in MODEL_DEFS.items():
            sub = model_menu.addMenu(name.split(" (")[0])
            for url in cfg["urls"]:
                label = "镜像" if "hf-mirror" in url else ("代理" if "ghproxy" in url else "官方")
                act = QAction(f"{label}: {url[:50]}...", self)
                act.triggered.connect(lambda checked, u=url: QDesktopServices.openUrl(QUrl(u)))
                sub.addAction(act)

        help_menu = mb.addMenu("帮助")
        about_act = QAction("关于", self)
        about_act.triggered.connect(lambda: _show_dialog(self, "关于", f"{APP_TITLE}\n\n基于 Depth Anything V2 的视频深度图转换工具\nhttps://github.com/ZhaoDesign/contour-control-tool"))
        help_menu.addAction(about_act)
        github_act = QAction("GitHub 主页", self)
        github_act.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/ZhaoDesign/contour-control-tool")))
        help_menu.addAction(github_act)

    def _uninstall_app(self) -> None:
        import subprocess
        uninstall_exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Contour Control Tool" / "unins000.exe"
        if uninstall_exe.is_file():
            subprocess.Popen([str(uninstall_exe)])
            self.close()
        else:
            _show_dialog(self, "卸载", f"未找到卸载程序。\n请手动删除安装目录。")

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
            self.output_dir_label.setText(f"输出到：{_short_path(d, 28)}")

    def _open_model_dir(self) -> None:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(MODELS_DIR))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(MODELS_DIR)))
        self._refresh_models()

    def _refresh_models(self) -> None:
        current = self.model_combo.currentText()
        self.model_combo.clear()
        items = list(MODEL_DEFS.keys())
        for f in sorted(MODELS_DIR.glob("*.onnx")):
            name = f.stem
            if not any(name in str(cfg["path"]) for cfg in MODEL_DEFS.values()):
                items.append(f"{name} (自定义)")
        self.model_combo.addItems(items)
        if current in items:
            self.model_combo.setCurrentText(current)

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
        panel.setFixedWidth(420)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        section = QLabel("输入视频")
        section.setObjectName("sectionTitle")
        layout.addWidget(section)

        self.drop_panel = DropPanel()
        self.drop_panel.file_dropped.connect(self._set_input_path)
        layout.addWidget(self.drop_panel)

        self._src_player = VideoPlayer()
        self._src_player.setVisible(False)
        layout.addWidget(self._src_player, 1)

        browse_btn = QPushButton("选择视频")
        browse_btn.setObjectName("secondaryButton")
        browse_btn.clicked.connect(self._choose_input)
        layout.addWidget(browse_btn)

        settings_title = QLabel("转换参数")
        settings_title.setObjectName("sectionTitle")
        layout.addWidget(settings_title)

        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(14)

        self.model_combo = QComboBox()
        self.model_combo.addItems(list(MODEL_DEFS.keys()))
        self.model_combo.setCurrentText("Small (fastest, ~99 MB)")
        _configure_combo(self.model_combo)

        self.model_folder_btn = IconButton("icon-folder.png", "打开模型目录", self)
        self.model_folder_btn.clicked.connect(self._open_model_dir)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(list(RESOLUTION_PRESETS.keys()))
        self.resolution_combo.setCurrentText("Original")
        _configure_combo(self.resolution_combo)

        self.smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setRange(0, 100)
        self.smoothing_slider.setValue(60)
        self.smoothing_value = QLabel("60")
        self.smoothing_slider.valueChanged.connect(lambda value: self.smoothing_value.setText(str(value)))

        form.addWidget(self._field_label("模型"), 0, 0)
        form.addWidget(self.model_combo, 0, 1)
        form.addWidget(self.model_folder_btn, 0, 2)
        form.addWidget(self._field_label("分辨率"), 1, 0)
        form.addWidget(self.resolution_combo, 1, 1, 1, 2)
        form.addWidget(self._field_label("平滑"), 2, 0)
        form.addWidget(self.smoothing_slider, 2, 1)
        form.addWidget(self.smoothing_value, 2, 2)
        layout.addLayout(form)

        self.invert_check = QCheckBox("黑白反转")
        self.preserve_audio_check = QCheckBox("保留原始音频")
        self.preserve_audio_check.setChecked(True)
        layout.addWidget(self.invert_check)
        layout.addWidget(self.preserve_audio_check)

        output_row = QHBoxLayout()
        self.output_dir_label = QLabel("输出到：跟随输入视频")
        self.output_dir_label.setObjectName("muted")
        output_btn = QPushButton("输出位置")
        output_btn.setObjectName("secondaryButton")
        output_btn.clicked.connect(self._choose_output_dir)
        output_row.addWidget(self.output_dir_label, 1)
        output_row.addWidget(output_btn)
        layout.addLayout(output_row)

        self.start_btn = QPushButton("开始转换")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setMinimumHeight(44)
        self.start_btn.clicked.connect(self._start_conversion)
        layout.addWidget(self.start_btn)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        title = QLabel("深度视频")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self._video_player = VideoPlayer()
        layout.addWidget(self._video_player, 2)

        # Task status section
        top = QHBoxLayout()
        status_title = QLabel("任务状态")
        status_title.setObjectName("sectionTitle")
        self.state_label = QLabel("等待视频")
        self.state_label.setObjectName("statePill")
        top.addWidget(status_title)
        top.addStretch(1)
        top.addWidget(self.state_label)
        layout.addLayout(top)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("选择一个视频后开始转换。")
        self.progress_label.setObjectName("muted")
        layout.addWidget(self.progress_label)

        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("logBox")
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("转换进度和模型下载状态会显示在这里")
        layout.addWidget(self.log_box, 1)

        result = QFrame()
        result.setObjectName("resultPanel")
        result_layout = QHBoxLayout(result)
        result_layout.setContentsMargins(16, 14, 16, 14)
        result_layout.setSpacing(14)

        self.result_label = QLabel("尚未生成输出视频")
        self.result_label.setObjectName("resultText")
        self.result_label.setWordWrap(True)
        self.open_output_btn = QPushButton("打开视频")
        self.open_folder_btn = QPushButton("打开文件夹")
        for button in (self.open_output_btn, self.open_folder_btn):
            button.setObjectName("secondaryButton")
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
        return label

    def _refresh_status(self) -> None:
        device_type, device_desc = detect_device()
        self.device_badge.setText(device_desc)
        self.device_badge.setProperty("kind", device_type)
        self.ffmpeg_badge.setText("FFmpeg 已就绪" if ffmpeg_available() else "FFmpeg 未就绪")
        self.ffmpeg_badge.setProperty("kind", "ok" if ffmpeg_available() else "warn")
        for badge in (self.device_badge, self.ffmpeg_badge):
            badge.style().unpolish(badge)
            badge.style().polish(badge)

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
        self.drop_panel.setVisible(False)
        self._src_player.setVisible(True)
        self._src_player.load(path)
        if not hasattr(self, "output_dir"):
            self.output_dir = str(_default_output_dir(path))
            self.output_dir_label.setText(f"输出到：{_short_path(self.output_dir, 28)}")
        self.progress_label.setText(_short_path(path))
        self.state_label.setText("已选择视频")
        self._append_log(f"输入：{path}")

    def _choose_output_dir(self) -> None:
        start_dir = getattr(self, "output_dir", str(_default_output_dir(self.input_path)))
        path = QFileDialog.getExistingDirectory(self, "选择输出文件夹", start_dir)
        if path:
            self.output_dir = path
            self.output_dir_label.setText(f"输出到：{_short_path(path, 28)}")

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
            model_label=self.model_combo.currentText(),
            resolution=self.resolution_combo.currentText(),
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
        self.resolution_combo.setEnabled(enabled)
        self.smoothing_slider.setEnabled(enabled)
        self.invert_check.setEnabled(enabled)
        self.preserve_audio_check.setEnabled(enabled)

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
    app.setFont(QFont("Microsoft YaHei UI", 10))
    check_icon = str(_asset_path("checkmark.png")).replace("\\", "/")
    chevron_icon = str(_asset_path("icon-chevron-down.png")).replace("\\", "/")
    app.setStyleSheet(
        """
        QWidget#root {
            background: #FFFFFF;
            color: #374151;
        }
        QLabel {
            color: #374151;
        }
        QLabel#appTitle {
            color: #111827;
            font-size: 20px;
            font-weight: 600;
        }
        QLabel#sectionTitle {
            color: #111827;
            font-size: 13px;
            font-weight: 600;
        }
        QLabel#muted {
            color: #6B7280;
        }
        QLabel#fieldLabel {
            color: #6B7280;
            font-weight: 500;
        }
        QLabel#appIcon {
            background: #F3F4F6;
            border: 1px solid #E5E7EB;
            border-radius: 10px;
        }
        QFrame#panel {
            background: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 10px;
        }
        QFrame#dropPanel {
            background: #F9FAFB;
            border: 2px dashed #D1D5DB;
            border-radius: 10px;
        }
        QFrame#dropPanel[dragging="true"] {
            background: #F3F4F6;
            border: 2px solid #9CA3AF;
        }
        QFrame#videoPlayer {
            background: transparent;
        }
        QFrame#videoSurface {
            background: #000000;
            border-radius: 8px;
        }
        QVideoWidget#videoWidget {
            background: #000000;
        }
        QLabel#videoPlaceholder {
            background: #000000;
            color: #9CA3AF;
            border-radius: 8px;
            font-size: 13px;
        }
        QLabel#dropTitle {
            color: #111827;
            font-size: 17px;
            font-weight: 500;
        }
        QLabel#filePill, QLabel#statePill {
            border-radius: 12px;
            padding: 5px 12px;
            background: #F3F4F6;
            color: #374151;
            font-weight: 500;
        }
        QLabel#badge {
            border-radius: 12px;
            padding: 5px 12px;
            background: #F3F4F6;
            color: #374151;
            font-weight: 500;
        }
        QLabel#badge[kind="cuda"], QLabel#badge[kind="ok"] {
            background: #F3F4F6;
            color: #111827;
        }
        QLabel#badge[kind="cpu"] {
            background: #F3F4F6;
            color: #374151;
        }
        QLabel#badge[kind="warn"] {
            background: #FFFBEB;
            color: #D97706;
        }
        QComboBox {
            background: #FFFFFF;
            color: #374151;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 8px 34px 8px 12px;
            min-height: 20px;
        }
        QComboBox:hover {
            border-color: #9CA3AF;
        }
        QComboBox:focus {
            border: 1px solid #111827;
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
            color: #374151;
            border: 1px solid #E5E7EB;
            border-radius: 10px;
            selection-background-color: transparent;
            selection-color: #111827;
            outline: none;
            padding: 6px;
        }
        QCheckBox {
            spacing: 10px;
            color: #374151;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 5px;
            border: 1px solid #D1D5DB;
            background: #FFFFFF;
        }
        QCheckBox::indicator:hover {
            border-color: #6B7280;
        }
        QCheckBox::indicator:checked {
            background: #111827;
            border-color: #111827;
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
            background: #111827;
        }
        QSlider::handle:horizontal:hover {
            background: #374151;
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
            background: #111827;
        }
        QPushButton {
            border: none;
            border-radius: 8px;
            padding: 9px 16px;
            font-weight: 600;
        }
        QPushButton#primaryButton {
            background: #111827;
            color: #FFFFFF;
            font-size: 14px;
        }
        QPushButton#primaryButton:hover {
            background: #374151;
        }
        QPushButton#primaryButton:pressed {
            background: #000000;
        }
        QPushButton#secondaryButton {
            background: #F3F4F6;
            color: #374151;
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
            height: 6px;
            background: #E5E7EB;
            border: none;
            border-radius: 3px;
        }
        QProgressBar::chunk {
            border-radius: 3px;
            background: #111827;
        }
        QPlainTextEdit#logBox {
            background: #FFFFFF;
            color: #374151;
            border: 1px solid #E5E7EB;
            border-radius: 10px;
            padding: 12px;
            font-family: Consolas, "Microsoft YaHei UI";
            font-size: 12px;
        }
        QFrame#resultPanel {
            background: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 10px;
        }
        QLabel#resultText {
            color: #374151;
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
        QToolTip {
            background: #FFFFFF;
            color: #374151;
            border: 1px solid #E5E7EB;
            padding: 8px 10px;
            border-radius: 8px;
        }
        QFrame#floatingTip {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 10px;
        }
        QLabel#floatingTipText {
            color: #374151;
            font-size: 12px;
            font-weight: 500;
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
        import ctypes

        msg = traceback.format_exc()
        log_path = DATA_DIR / "crash.log"
        try:
            log_path.write_text(msg, encoding="utf-8")
        except OSError:
            pass
        ctypes.windll.user32.MessageBoxW(
            0,
            f"启动失败:\n\n{msg}\n\n日志: {log_path}",
            APP_TITLE,
            0x10,
        )
        sys.exit(1)
