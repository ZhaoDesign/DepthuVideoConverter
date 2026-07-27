#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
OUTPUT_DIR="${1:-${ROOT:h}/outputs}"
BUILD_DIR="$ROOT/build/macos"
APP_PATH="$BUILD_DIR/dist/DepthVideoConverter.app"

mkdir -p "$OUTPUT_DIR"
export GRADIO_ANALYTICS_ENABLED=False
export HF_HUB_DISABLE_TELEMETRY=1
"$ROOT/venv/bin/python" -m pip install --upgrade pyinstaller imageio-ffmpeg
"$ROOT/venv/bin/python" "$ROOT/packaging/generate_icon.py"

rm -rf "$BUILD_DIR/work" "$BUILD_DIR/dist" "$BUILD_DIR/spec"
mkdir -p "$BUILD_DIR/work" "$BUILD_DIR/dist" "$BUILD_DIR/spec"

"$ROOT/venv/bin/pyinstaller" \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name "DepthVideoConverter" \
  --osx-bundle-identifier "com.depthvideoconverter.desktop" \
  --icon "$ROOT/assets/depth-video-converter.icns" \
  --distpath "$BUILD_DIR/dist" \
  --workpath "$BUILD_DIR/work" \
  --specpath "$BUILD_DIR/spec" \
  --collect-all gradio \
  --collect-all gradio_client \
  --collect-all imageio_ffmpeg \
  --collect-submodules depth_anything_v2 \
  --copy-metadata gradio \
  --copy-metadata gradio_client \
  --copy-metadata huggingface_hub \
  "$ROOT/desktop_launcher.py"

/usr/bin/codesign --force --deep --sign - "$APP_PATH"

ZIP_PATH="$OUTPUT_DIR/DepthVideoConverter-macOS-AppleSilicon.zip"
DMG_PATH="$OUTPUT_DIR/DepthVideoConverter-macOS-AppleSilicon.dmg"
STAGE_DIR="$BUILD_DIR/dmg-stage"
rm -rf "$ZIP_PATH" "$DMG_PATH" "$STAGE_DIR"
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
mkdir -p "$STAGE_DIR"
/usr/bin/ditto "$APP_PATH" "$STAGE_DIR/DepthVideoConverter.app"
ln -s /Applications "$STAGE_DIR/Applications"
/usr/bin/hdiutil create -volname "Depth Video Converter" -srcfolder "$STAGE_DIR" -format UDZO -ov "$DMG_PATH"
rm -rf "$STAGE_DIR"

print -r -- "$ZIP_PATH"
print -r -- "$DMG_PATH"
