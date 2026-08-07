#!/bin/zsh
set -euo pipefail

APP_TITLE="DepthuVideoConverter"
APP_NAME="DepthuVideoConverter"
PYTHON_VERSION="3.11"
UV_INSTALL_URL="${CCT_UV_INSTALL_URL:-https://astral.sh/uv/install.sh}"

SCRIPT_PATH="${0:A}"
MACOS_DIR="${SCRIPT_PATH:h}"
CONTENTS_DIR="${MACOS_DIR:h}"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
APP_DIR="${CCT_APP_DIR:-$RESOURCES_DIR/app}"
INSTALLER_DIR="${CCT_INSTALLER_DIR:-$RESOURCES_DIR/installer}"
DEFAULT_DATA_DIR="$HOME/Library/Application Support/DepthuVideoConverter"
LEGACY_DATA_DIR="$HOME/Library/Application Support/DepthVideoConverter"
if [[ -n "${CCT_DATA_DIR:-}" ]]; then
    DATA_DIR="$CCT_DATA_DIR"
elif [[ -d "$DEFAULT_DATA_DIR" || ! -d "$LEGACY_DATA_DIR" ]]; then
    DATA_DIR="$DEFAULT_DATA_DIR"
else
    DATA_DIR="$LEGACY_DATA_DIR"
fi
RUNTIME_ROOT="${CCT_RUNTIME_ROOT:-$HOME/Library/Application Support/CCT}"
TOOLS_DIR="$RUNTIME_ROOT/tools"
PYTHON_DIR="$RUNTIME_ROOT/python"
VENV_DIR="$RUNTIME_ROOT/rt311mac"
CACHE_DIR="$RUNTIME_ROOT/cache"
LOCK_DIR="$RUNTIME_ROOT/install.lock"
LOG_PATH="$DATA_DIR/installer.log"
MARKER_PATH="$VENV_DIR/.runtime-macos-ok"
SIGNATURE_PATH="$INSTALLER_DIR/runtime.signature"

export PYTHONDONTWRITEBYTECODE=1

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
    display notification (item 1 of argv) with title "DepthuVideoConverter"
end run
APPLESCRIPT
}

show_error() {
    local message="$1"
    /usr/bin/osascript - "$message" <<'APPLESCRIPT' >/dev/null 2>&1 || true
on run argv
    display alert "DepthuVideoConverter 无法启动" message (item 1 of argv) as critical buttons {"确定"} default button 1
end run
APPLESCRIPT
}

runtime_ready() {
    local signature="$1"
    if [[ ! -x "$VENV_DIR/bin/python" || ! -f "$MARKER_PATH" ]]; then
        return 1
    fi
    local current_signature=""
    current_signature="$(<"$MARKER_PATH")"
    [[ "$signature" != "" && ( "$current_signature" == "$signature" || "$current_signature" == *":$signature" ) ]]
}

acquire_install_lock() {
    local waited=0
    while ! mkdir "$LOCK_DIR" 2>/dev/null; do
        local lock_pid=""
        if [[ -f "$LOCK_DIR/pid" ]]; then
            lock_pid="$(<"$LOCK_DIR/pid")"
        fi
        if [[ "$lock_pid" != "" ]] && ! kill -0 "$lock_pid" 2>/dev/null; then
            log "Removing stale install lock: $LOCK_DIR"
            rm -rf "$LOCK_DIR"
            continue
        fi
        if (( waited == 0 )); then
            notify_user "运行环境正在准备中，请不要重复打开。"
            log "Waiting for existing runtime installation..."
        fi
        sleep 2
        waited=$((waited + 2))
        if (( waited >= 900 )); then
            show_error "运行环境准备超时，请稍后重试。日志：$LOG_PATH"
            return 1
        fi
    done
    print -r -- "$$" > "$LOCK_DIR/pid"
}

release_install_lock() {
    rm -rf "$LOCK_DIR"
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

    if runtime_ready "$signature"; then
        log "Runtime already installed."
        return 0
    fi

    acquire_install_lock || return 1
    trap 'release_install_lock' EXIT INT TERM

    if runtime_ready "$signature"; then
        log "Runtime was installed by another launch."
        release_install_lock
        trap - EXIT INT TERM
        return 0
    fi

    log "Preparing runtime in: $VENV_DIR"
    rm -rf "$VENV_DIR"
    mkdir -p "$VENV_DIR"

    notify_user "首次启动正在联网准备运行环境，可能需要几分钟。"

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

    if ! PYTHONDONTWRITEBYTECODE=1 "$VENV_DIR/bin/python" "$INSTALLER_DIR/verify_runtime.py" "$APP_DIR"; then
        return 1
    fi

    if [[ "$signature" != "" ]]; then
        print -r -- "$signature" > "$MARKER_PATH"
    else
        print -r -- "installed=$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$MARKER_PATH"
    fi
    log "Runtime installation completed."
    release_install_lock
    trap - EXIT INT TERM
}

main() {
    log "Launching $APP_NAME"
    log "App dir: $APP_DIR"
    log "Installer dir: $INSTALLER_DIR"
    log "Data dir: $DATA_DIR"
    export DEPTH_APP_DATA_DIR="$DATA_DIR"

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

    log "Starting native desktop app..."
    exec "$VENV_DIR/bin/python" "$APP_DIR/desktop_qt_app.py"
}

main "$@"
