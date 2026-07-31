#!/bin/zsh
set -euo pipefail

APP_TITLE="视频深度控制图工具"
APP_NAME="Contour Control Tool"
PYTHON_VERSION="3.11"
UV_INSTALL_URL="${CCT_UV_INSTALL_URL:-https://astral.sh/uv/install.sh}"

SCRIPT_PATH="${0:A}"
MACOS_DIR="${SCRIPT_PATH:h}"
CONTENTS_DIR="${MACOS_DIR:h}"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
APP_DIR="${CCT_APP_DIR:-$RESOURCES_DIR/app}"
INSTALLER_DIR="${CCT_INSTALLER_DIR:-$RESOURCES_DIR/installer}"
DATA_DIR="${CCT_DATA_DIR:-$HOME/Library/Application Support/DepthVideoConverter}"
RUNTIME_ROOT="${CCT_RUNTIME_ROOT:-$HOME/Library/Application Support/CCT}"
TOOLS_DIR="$RUNTIME_ROOT/tools"
PYTHON_DIR="$RUNTIME_ROOT/python"
VENV_DIR="$RUNTIME_ROOT/rt311mac"
CACHE_DIR="$RUNTIME_ROOT/cache"
LOG_PATH="$DATA_DIR/installer.log"
MARKER_PATH="$VENV_DIR/.runtime-macos-ok"
SIGNATURE_PATH="$INSTALLER_DIR/runtime.signature"

mkdir -p "$DATA_DIR" "$TOOLS_DIR" "$PYTHON_DIR" "$CACHE_DIR"
touch "$LOG_PATH"
exec >>"$LOG_PATH" 2>&1

log() {
    print -ru2 -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

notify_user() {
    local message="$1"
    /usr/bin/osascript - "$message" <<'APPLESCRIPT' >/dev/null 2>&1 || true
on run argv
    display notification (item 1 of argv) with title "视频深度控制图工具"
end run
APPLESCRIPT
}

show_error() {
    local message="$1"
    /usr/bin/osascript - "$message" <<'APPLESCRIPT' >/dev/null 2>&1 || true
on run argv
    display alert "视频深度控制图工具无法启动" message (item 1 of argv) as critical buttons {"确定"} default button 1
end run
APPLESCRIPT
}

ensure_uv() {
    local uv_bin="$TOOLS_DIR/uv"
    if [[ -x "$uv_bin" ]]; then
        print -r -- "$uv_bin"
        return 0
    fi

    log "Installing uv runtime helper..."
    local installer="$CACHE_DIR/uv-install.sh"
    /usr/bin/curl -fsSL "$UV_INSTALL_URL" -o "$installer"
    UV_INSTALL_DIR="$TOOLS_DIR" UV_NO_MODIFY_PATH=1 /bin/sh "$installer" >&2

    if [[ -x "$uv_bin" ]]; then
        print -r -- "$uv_bin"
        return 0
    fi
    if [[ -x "$TOOLS_DIR/bin/uv" ]]; then
        print -r -- "$TOOLS_DIR/bin/uv"
        return 0
    fi

    return 1
}

install_runtime() {
    local uv_bin="$1"
    local requirements="$INSTALLER_DIR/runtime-requirements-macos.txt"
    local signature=""
    if [[ -f "$SIGNATURE_PATH" ]]; then
        signature="$(<"$SIGNATURE_PATH")"
    fi

    if [[ -x "$VENV_DIR/bin/python" && -f "$MARKER_PATH" ]]; then
        local current_signature=""
        current_signature="$(<"$MARKER_PATH")"
        if [[ "$signature" != "" && "$current_signature" == "$signature" ]]; then
            log "Runtime already installed."
            return 0
        fi
    fi

    log "Preparing runtime in: $VENV_DIR"
    rm -rf "$VENV_DIR"
    mkdir -p "$VENV_DIR"

    notify_user "首次启动正在联网准备运行环境，请保持网络连接。"

    if ! UV_PYTHON_INSTALL_DIR="$PYTHON_DIR" \
        UV_CACHE_DIR="$CACHE_DIR" \
        UV_NO_PROGRESS=1 \
        "$uv_bin" venv --python "$PYTHON_VERSION" "$VENV_DIR"; then
        return 1
    fi

    if ! UV_CACHE_DIR="$CACHE_DIR" \
        UV_NO_PROGRESS=1 \
        "$uv_bin" pip install --python "$VENV_DIR/bin/python" --no-cache --only-binary=:all: -r "$requirements"; then
        return 1
    fi

    if ! "$VENV_DIR/bin/python" "$INSTALLER_DIR/verify_runtime.py" "$APP_DIR"; then
        return 1
    fi

    if [[ "$signature" != "" ]]; then
        print -r -- "$signature" > "$MARKER_PATH"
    else
        print -r -- "installed=$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$MARKER_PATH"
    fi
    log "Runtime installation completed."
}

main() {
    log "Launching $APP_NAME"
    log "App dir: $APP_DIR"
    log "Installer dir: $INSTALLER_DIR"
    log "Data dir: $DATA_DIR"

    if [[ "${CCT_MACOS_INSTALLER_SELF_TEST:-0}" == "1" ]]; then
        [[ -d "$APP_DIR" ]] || return 2
        [[ -f "$INSTALLER_DIR/runtime-requirements-macos.txt" ]] || return 2
        [[ -f "$INSTALLER_DIR/verify_runtime.py" ]] || return 2
        log "Self-test completed."
        return 0
    fi

    if [[ ! -d "$APP_DIR" ]]; then
        show_error "找不到应用资源目录：$APP_DIR"
        return 1
    fi

    local uv_bin
    uv_bin="$(ensure_uv)" || {
        show_error "uv 安装失败，请查看日志：$LOG_PATH"
        return 1
    }
    install_runtime "$uv_bin" || {
        show_error "运行环境安装失败，请查看日志：$LOG_PATH"
        return 1
    }

    if [[ "${CCT_MACOS_INSTALL_RUNTIME_ONLY:-0}" == "1" ]]; then
        log "Runtime-only verification completed."
        return 0
    fi

    log "Starting desktop launcher..."
    exec "$VENV_DIR/bin/python" "$APP_DIR/desktop_launcher.py"
}

main "$@"
