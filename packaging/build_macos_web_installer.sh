#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
OUTPUT_DIR="${1:-$ROOT/build/macos-web-installer/output}"
BUILD_DIR="$ROOT/build/macos-web-installer"
STAGE_DIR="$BUILD_DIR/stage"
APP_NAME="ContourControlTool"
APP_BUNDLE="$APP_NAME.app"
APP_PATH="$STAGE_DIR/$APP_BUNDLE"
CONTENTS_DIR="$APP_PATH/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
INSTALLER_DIR="$RESOURCES_DIR/installer"
APP_SRC_DIR="$RESOURCES_DIR/app"
VERSION="${APP_VERSION:-0.1.0}"

mkdir -p "$OUTPUT_DIR" "$BUILD_DIR"
export GRADIO_ANALYTICS_ENABLED=False
export HF_HUB_DISABLE_TELEMETRY=1

rm -rf "$STAGE_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$INSTALLER_DIR" "$APP_SRC_DIR"

cp "$ROOT/packaging/macos-web-installer/launch_runtime.sh" "$MACOS_DIR/$APP_NAME"
chmod 755 "$MACOS_DIR/$APP_NAME"
cp "$ROOT/assets/depth-video-converter.icns" "$RESOURCES_DIR/depth-video-converter.icns"
cp "$ROOT/README.md" "$APP_SRC_DIR/README.md"
cp "$ROOT/README_CN.md" "$APP_SRC_DIR/README_CN.md"
cp "$ROOT/desktop_launcher.py" "$APP_SRC_DIR/desktop_launcher.py"
cp "$ROOT/depth_video_converter.py" "$APP_SRC_DIR/depth_video_converter.py"
cp "$ROOT/depth_video_cli.py" "$APP_SRC_DIR/depth_video_cli.py"
cp "$ROOT/packaging/macos-web-installer/README_CN.md" "$APP_SRC_DIR/README_WEB_INSTALLER_CN.md"
cp "$ROOT/packaging/macos-web-installer/runtime-requirements-macos.txt" "$INSTALLER_DIR/runtime-requirements-macos.txt"
cp "$ROOT/packaging/macos-web-installer/verify_runtime.py" "$INSTALLER_DIR/verify_runtime.py"

cp -R "$ROOT/depth_converter" "$APP_SRC_DIR/depth_converter"
cp -R "$ROOT/depth_anything_v2" "$APP_SRC_DIR/depth_anything_v2"
mkdir -p "$APP_SRC_DIR/assets"
cp "$ROOT/assets/depth-video-converter.ico" "$APP_SRC_DIR/assets/depth-video-converter.ico"
cp "$ROOT/assets/depth-video-converter.png" "$APP_SRC_DIR/assets/depth-video-converter.png"

SIGNATURE_FILE="$INSTALLER_DIR/runtime.signature"
REQ_HASH="$(shasum -a 256 "$INSTALLER_DIR/runtime-requirements-macos.txt" | awk '{print $1}')"
printf '%s:%s\n' "$VERSION" "$REQ_HASH" > "$SIGNATURE_FILE"

cat > "$CONTENTS_DIR/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>zh_CN</string>
  <key>CFBundleDisplayName</key>
  <string>视频深度控制图工具</string>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIconFile</key>
  <string>depth-video-converter.icns</string>
  <key>CFBundleIdentifier</key>
  <string>com.zhaodesign.contour-control-tool.web</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>视频深度控制图工具</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>$VERSION</string>
  <key>CFBundleVersion</key>
  <string>$VERSION</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF

plutil -lint "$CONTENTS_DIR/Info.plist"
CCT_MACOS_INSTALLER_SELF_TEST=1 "$MACOS_DIR/$APP_NAME"

/usr/bin/codesign --force --deep --sign - "$APP_PATH"

ZIP_PATH="$OUTPUT_DIR/ContourControlTool-macOS-WebSetup.zip"
DMG_PATH="$OUTPUT_DIR/ContourControlTool-macOS-WebSetup.dmg"
STAGE_DMG_DIR="$BUILD_DIR/dmg-stage"
rm -rf "$ZIP_PATH" "$DMG_PATH" "$STAGE_DMG_DIR"
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
mkdir -p "$STAGE_DMG_DIR"
/usr/bin/ditto "$APP_PATH" "$STAGE_DMG_DIR/$APP_BUNDLE"
ln -s /Applications "$STAGE_DMG_DIR/Applications"
/usr/bin/hdiutil create -volname "Contour Control Tool" -srcfolder "$STAGE_DMG_DIR" -format UDZO -ov "$DMG_PATH"
rm -rf "$STAGE_DMG_DIR"

print -r -- "$ZIP_PATH"
print -r -- "$DMG_PATH"
