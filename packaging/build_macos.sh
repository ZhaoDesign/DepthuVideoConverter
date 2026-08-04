#!/bin/zsh
# ──────────────────────────────────────────────────────────────────────
# macOS PyInstaller 构建脚本
#
# 使用 PyInstaller 把 PySide6 Qt 桌面应用打包成独立 .app
# 输出 .dmg 和 .zip
#
# 前提：需要先创建并激活包含所有依赖的 venv:
#   python3.11 -m venv venv
#   source venv/bin/activate
#   pip install -r packaging/macos-web-installer/runtime-requirements-macos.txt
#   pip install pyinstaller
#
# 用法:
#   APP_VERSION=0.1.0 zsh packaging/build_macos.sh [输出目录]
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="${0:A:h:h}"
OUTPUT_DIR="${1:-$ROOT/build/macos-pyinstaller/output}"
BUILD_DIR="$ROOT/build/macos-pyinstaller"
APP_NAME="ContourControlTool"
APP_PATH="$BUILD_DIR/dist/$APP_NAME.app"
VERSION="${APP_VERSION:-0.1.0}"

# 查找 Python — 优先使用 venv
PYTHON="${ROOT}/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3.11 2>/dev/null || command -v python3 2>/dev/null || true)"
fi
if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
    print -ru2 "错误: 找不到 Python。请先创建 venv 或确保 python3.11 在 PATH 中。"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
export GRADIO_ANALYTICS_ENABLED=False
export HF_HUB_DISABLE_TELEMETRY=1

"$PYTHON" -m pip install --upgrade pyinstaller imageio-ffmpeg

rm -rf "$BUILD_DIR/work" "$BUILD_DIR/dist" "$BUILD_DIR/spec"
mkdir -p "$BUILD_DIR/work" "$BUILD_DIR/dist" "$BUILD_DIR/spec"

"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name "$APP_NAME" \
  --osx-bundle-identifier "com.zhaodesign.contour-control-tool.pyinstaller" \
  --icon "$ROOT/assets/depth-video-converter.icns" \
  --distpath "$BUILD_DIR/dist" \
  --workpath "$BUILD_DIR/work" \
  --specpath "$BUILD_DIR/spec" \
  --collect-all imageio_ffmpeg \
  --collect-submodules depth_converter \
  --collect-submodules PySide6 \
  --hidden-import PySide6.QtCore \
  --hidden-import PySide6.QtGui \
  --hidden-import PySide6.QtWidgets \
  --hidden-import PySide6.QtMultimedia \
  --hidden-import PySide6.QtMultimediaWidgets \
  --hidden-import onnxruntime \
  --hidden-import cv2 \
  --hidden-import numpy \
  "$ROOT/desktop_qt_app.py"

/usr/bin/codesign --force --deep --sign - "$APP_PATH"

# 修改 Info.plist 添加中文显示名
/usr/bin/plutil -replace CFBundleDisplayName -string "视频深度控制图工具" "$APP_PATH/Contents/Info.plist"
/usr/bin/plutil -replace CFBundleName -string "视频深度控制图工具" "$APP_PATH/Contents/Info.plist"
/usr/bin/plutil -replace CFBundleShortVersionString -string "$VERSION" "$APP_PATH/Contents/Info.plist"
/usr/bin/plutil -replace NSHighResolutionCapable -bool true "$APP_PATH/Contents/Info.plist"

ZIP_PATH="$OUTPUT_DIR/ContourControlTool-macOS-PyInstaller.zip"
DMG_PATH="$OUTPUT_DIR/ContourControlTool-macOS-PyInstaller.dmg"
STAGE_DIR="$BUILD_DIR/dmg-stage"
rm -rf "$ZIP_PATH" "$DMG_PATH" "$STAGE_DIR"
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
mkdir -p "$STAGE_DIR"
/usr/bin/ditto "$APP_PATH" "$STAGE_DIR/$APP_NAME.app"
ln -s /Applications "$STAGE_DIR/Applications"
/usr/bin/hdiutil create -volname "视频深度控制图工具" -srcfolder "$STAGE_DIR" -format UDZO -ov "$DMG_PATH"
rm -rf "$STAGE_DIR"

print -r -- ""
print -r -- "============================================"
print -r -- " PyInstaller 构建成功!"
print -r -- " ZIP: $ZIP_PATH"
print -r -- " DMG: $DMG_PATH"
print -r -- "============================================"
