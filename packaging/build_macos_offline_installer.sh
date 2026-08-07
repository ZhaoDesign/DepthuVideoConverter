#!/bin/zsh
# ──────────────────────────────────────────────────────────────────────
# macOS 离线安装器构建脚本
#
# 对应 Windows 的 build_windows_offline_installer.ps1：
#   - 内嵌 Python 3.11 虚拟环境 + 所有依赖
#   - 内嵌 Small PyTorch .pth 模型（首次运行无需联网）
#   - 输出 .dmg 和 .zip
#
# 用法:
#   APP_VERSION=0.1.0 zsh packaging/build_macos_offline_installer.sh [输出目录]
#
# 依赖:
#   - macOS 11+ (Apple Silicon)
#   - uv (自动安装)
#   - curl
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="${0:A:h:h}"
OUTPUT_DIR="${1:-$ROOT/build/macos-offline-installer/output}"
BUILD_DIR="$ROOT/build/macos-offline-installer"
STAGE_DIR="$BUILD_DIR/stage"
CACHE_DIR="$BUILD_DIR/cache"
APP_NAME="DepthuVideoConverter"
APP_BUNDLE="$APP_NAME.app"
APP_PATH="$STAGE_DIR/$APP_BUNDLE"
CONTENTS_DIR="$APP_PATH/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
APP_SRC_DIR="$RESOURCES_DIR/app"
RUNTIME_DIR="$RESOURCES_DIR/runtime"
MODELS_DIR="$RESOURCES_DIR/models"
VERSION="${APP_VERSION:-0.1.0}"
PYTHON_VERSION="3.11"
REQUIREMENTS="$ROOT/packaging/macos-web-installer/runtime-requirements-macos.txt"
VERIFY_SCRIPT="$ROOT/packaging/macos-web-installer/verify_runtime.py"

# 使用中国镜像
export HF_MIRROR="${HF_MIRROR:-https://hf-mirror.com}"

log() { print -r -- "[$(date '+%H:%M:%S')] $*" }

# ── 0. 确保 uv 可用 ──────────────────────────────────────────────────
UV_BIN="${UV_BIN:-$(command -v uv 2>/dev/null || true)}"
if [[ -z "$UV_BIN" || ! -x "$UV_BIN" ]]; then
    log "正在安装 uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV_BIN="${HOME}/.local/bin/uv"
    if [[ ! -x "$UV_BIN" ]]; then
        UV_BIN="${HOME}/.cargo/bin/uv"
    fi
fi
log "uv: $UV_BIN ($("$UV_BIN" --version))"

# ── 1. 初始化目录 ────────────────────────────────────────────────────
mkdir -p "$OUTPUT_DIR" "$BUILD_DIR" "$CACHE_DIR"
rm -rf "$STAGE_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$APP_SRC_DIR" "$MODELS_DIR"

# ── 2. 构建 Python 运行环境 ──────────────────────────────────────────
log "正在创建 Python $PYTHON_VERSION 虚拟环境..."
rm -rf "$RUNTIME_DIR"
UV_PYTHON_INSTALL_DIR="$CACHE_DIR/python" \
UV_CACHE_DIR="$CACHE_DIR/uv" \
"$UV_BIN" venv --python "$PYTHON_VERSION" "$RUNTIME_DIR"

log "正在安装依赖（可能需要几分钟）..."
UV_CACHE_DIR="$CACHE_DIR/uv" \
"$UV_BIN" pip install \
    --python "$RUNTIME_DIR/bin/python" \
    --no-cache \
    --only-binary=:all: \
    -r "$REQUIREMENTS"

log "正在验证运行环境..."
"$RUNTIME_DIR/bin/python" "$VERIFY_SCRIPT" "$ROOT"

# 计算运行环境大小
RUNTIME_SIZE_MB=$(du -sm "$RUNTIME_DIR" | awk '{print $1}')
log "运行环境大小: ${RUNTIME_SIZE_MB} MB"

# ── 3. 下载 Small PyTorch 模型 ───────────────────────────────────────
MODEL_FILE="$MODELS_DIR/depth_anything_v2_vits.pth"
CACHED_MODEL="$CACHE_DIR/depth_anything_v2_vits.pth"

if [[ -f "$CACHED_MODEL" ]] && (( $(stat -f%z "$CACHED_MODEL" 2>/dev/null || stat -c%s "$CACHED_MODEL" 2>/dev/null) > 1000000 )); then
    log "使用缓存的 Small 模型"
    cp "$CACHED_MODEL" "$MODEL_FILE"
else
    log "正在下载 Small PyTorch 模型 (~95 MB)..."
    MODEL_REPO="depth-anything/Depth-Anything-V2-Small"
    MODEL_URLS=(
        "${HF_MIRROR}/${MODEL_REPO}/resolve/main/depth_anything_v2_vits.pth"
        "https://huggingface.co/${MODEL_REPO}/resolve/main/depth_anything_v2_vits.pth"
    )
    DOWNLOADED=0
    for url in "${MODEL_URLS[@]}"; do
        if curl -fSL --retry 3 "$url" -o "$MODEL_FILE"; then
            DOWNLOADED=1
            cp "$MODEL_FILE" "$CACHED_MODEL"
            break
        fi
        log "镜像下载失败，尝试下一个..."
    done
    if (( ! DOWNLOADED )); then
        log "⚠ 模型下载失败，离线包将不含预装模型（首次使用时需下载）"
        rm -f "$MODEL_FILE"
    fi
fi

# ── 4. 复制应用源码 ──────────────────────────────────────────────────
log "正在复制应用文件..."
cp "$ROOT/desktop_qt_app.py"          "$APP_SRC_DIR/"
cp "$ROOT/desktop_launcher.py"        "$APP_SRC_DIR/"
cp "$ROOT/depth_video_converter.py"   "$APP_SRC_DIR/"
cp "$ROOT/depth_video_cli.py"         "$APP_SRC_DIR/"
cp "$ROOT/README.md"                  "$APP_SRC_DIR/"
cp "$ROOT/README_CN.md"               "$APP_SRC_DIR/"
/usr/bin/rsync -a --exclude '__pycache__/' --exclude '*.pyc' --exclude '.DS_Store' \
  "$ROOT/depth_converter/" "$APP_SRC_DIR/depth_converter/"
/usr/bin/rsync -a --exclude '__pycache__/' --exclude '*.pyc' --exclude '.DS_Store' \
  "$ROOT/depth_anything_v2/" "$APP_SRC_DIR/depth_anything_v2/"
mkdir -p "$APP_SRC_DIR/assets"
cp "$ROOT/assets/"*.png "$APP_SRC_DIR/assets/" 2>/dev/null || true
cp "$ROOT/assets/"*.ico "$APP_SRC_DIR/assets/" 2>/dev/null || true
cp "$ROOT/assets/"*.icns "$APP_SRC_DIR/assets/" 2>/dev/null || true

# ── 5. 创建启动脚本 ──────────────────────────────────────────────────
cat > "$MACOS_DIR/$APP_NAME" <<'LAUNCHER_EOF'
#!/bin/zsh
set -euo pipefail

SCRIPT_PATH="${0:A}"
MACOS_DIR="${SCRIPT_PATH:h}"
CONTENTS_DIR="${MACOS_DIR:h}"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
APP_DIR="$RESOURCES_DIR/app"
RUNTIME_DIR="$RESOURCES_DIR/runtime"
BUNDLED_MODELS_DIR="$RESOURCES_DIR/models"

DATA_DIR="$HOME/Library/Application Support/DepthuVideoConverter"
USER_MODELS_DIR="$DATA_DIR/models"
LOG_PATH="$DATA_DIR/launcher.log"

export PYTHONDONTWRITEBYTECODE=1

mkdir -p "$USER_MODELS_DIR"
touch "$LOG_PATH"

log() { print -ru2 -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*" }

show_error() {
    local message="$1"
    /usr/bin/osascript - "$message" <<'APPLESCRIPT' >/dev/null 2>&1 || true
on run argv
    display alert "DepthuVideoConverter 无法启动" message (item 1 of argv) as critical buttons {"确定"} default button 1
end run
APPLESCRIPT
}

{
    log "Launching DepthuVideoConverter (offline)"
    log "App dir: $APP_DIR"
    log "Runtime dir: $RUNTIME_DIR"

    if [[ ! -x "$RUNTIME_DIR/bin/python" ]]; then
        show_error "找不到运行环境，应用可能未正确安装。请重新安装。"
        exit 1
    fi

    # 将内嵌模型复制到用户目录（如果用户还没有的话）
    if [[ -d "$BUNDLED_MODELS_DIR" ]]; then
        for model in "$BUNDLED_MODELS_DIR"/*.pth(N); do
            target="$USER_MODELS_DIR/${model:t}"
            if [[ ! -f "$target" ]]; then
                log "Copying bundled model: ${model:t}"
                cp "$model" "$target"
            fi
        done
    fi

    exec "$RUNTIME_DIR/bin/python" "$APP_DIR/desktop_qt_app.py"
} >> "$LOG_PATH" 2>&1
LAUNCHER_EOF
chmod 755 "$MACOS_DIR/$APP_NAME"

# ── 6. 复制图标 ──────────────────────────────────────────────────────
cp "$ROOT/assets/depth-video-converter.icns" "$RESOURCES_DIR/depth-video-converter.icns"

# ── 7. 创建 Info.plist ───────────────────────────────────────────────
cat > "$CONTENTS_DIR/Info.plist" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>zh_CN</string>
  <key>CFBundleDisplayName</key>
  <string>DepthuVideoConverter</string>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIconFile</key>
  <string>depth-video-converter.icns</string>
  <key>CFBundleIdentifier</key>
  <string>com.zhaodesign.depthuvideoconverter.offline</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>DepthuVideoConverter</string>
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
PLIST_EOF

plutil -lint "$CONTENTS_DIR/Info.plist"

# ── 8. 代码签名 ──────────────────────────────────────────────────────
log "正在签名..."
/usr/bin/codesign --force --deep --sign - "$APP_PATH"

# ── 9. 统计总大小 ────────────────────────────────────────────────────
TOTAL_SIZE_MB=$(du -sm "$APP_PATH" | awk '{print $1}')
log "App 总大小: ${TOTAL_SIZE_MB} MB（未压缩）"

# ── 10. 创建 ZIP 和 DMG ─────────────────────────────────────────────
ZIP_PATH="$OUTPUT_DIR/DepthuVideoConverter-macOS-OfflineSetup.zip"
DMG_PATH="$OUTPUT_DIR/DepthuVideoConverter-macOS-OfflineSetup.dmg"
STAGE_DMG_DIR="$BUILD_DIR/dmg-stage"

rm -rf "$ZIP_PATH" "$DMG_PATH" "$STAGE_DMG_DIR"

log "正在创建 ZIP..."
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

log "正在创建 DMG..."
mkdir -p "$STAGE_DMG_DIR"
/usr/bin/ditto "$APP_PATH" "$STAGE_DMG_DIR/$APP_BUNDLE"
ln -s /Applications "$STAGE_DMG_DIR/Applications"
/usr/bin/hdiutil create \
    -volname "DepthuVideoConverter" \
    -srcfolder "$STAGE_DMG_DIR" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -ov "$DMG_PATH"
rm -rf "$STAGE_DMG_DIR"

# ── 11. 输出结果 ─────────────────────────────────────────────────────
ZIP_SIZE_MB=$(printf '%.1f' "$(echo "$(stat -f%z "$ZIP_PATH" 2>/dev/null || stat -c%s "$ZIP_PATH") / 1048576" | bc)")
DMG_SIZE_MB=$(printf '%.1f' "$(echo "$(stat -f%z "$DMG_PATH" 2>/dev/null || stat -c%s "$DMG_PATH") / 1048576" | bc)")

print -r -- ""
print -r -- "============================================"
print -r -- " 构建成功!"
print -r -- " ZIP: $ZIP_PATH (${ZIP_SIZE_MB} MB)"
print -r -- " DMG: $DMG_PATH (${DMG_SIZE_MB} MB)"
print -r -- "============================================"
