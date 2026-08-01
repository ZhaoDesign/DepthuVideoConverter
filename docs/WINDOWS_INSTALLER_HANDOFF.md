# Windows x64 Native Installer Handoff

This note records the Windows customer installer work so another machine or agent can continue from a clean clone.

## Current Goal

Ship a customer-friendly Windows 64-bit installer for Contour Control Tool:

1. A normal installation wizard with install-location selection.
2. A native desktop application window, not a browser or Gradio page.
3. Small GitHub Release asset size by downloading the heavy runtime during installation.
4. Start Menu and desktop launch shortcuts.
5. Start Menu and desktop quick uninstall shortcuts.
6. No restart prompt after a successful install.

macOS parity is prepared at the packaging-file level, but macOS packaging has not been verified from this Windows machine.

## Main Changes

- Added `desktop_qt_app.py`
  - PySide6 native desktop UI.
  - Drag/drop video input.
  - Model and output-resolution selectors.
  - Smoothing slider.
  - Invert and preserve-audio checkboxes.
  - Output-folder picker.
  - Progress bar, log panel, open-output buttons.
  - Runs conversion in a background Qt worker thread.

- Updated `packaging/windows-web-installer/ContourControlToolSetup.iss`
  - Launch shortcuts now run `desktop_qt_app.py` with `pythonw.exe`.
  - Default install location is per-user: `%LOCALAPPDATA%\Programs\Contour Control Tool`.
  - The user can still choose a custom path, including paths with spaces.
  - Runtime install runs hidden inside the installer, so customers do not see a PowerShell window.
  - Chinese installer text is added for the main wizard steps.
  - Start Menu and desktop uninstall shortcuts are created.
  - Old English uninstall shortcuts are removed during upgrades.
  - Restart prompts are disabled for the runtime install step.

- Updated `packaging/windows-web-installer/install_runtime.ps1`
  - Runtime marker now includes `runtime_version=2026.08.01-native-ui.2`.
  - Changing the runtime marker forces older browser-runtime installs to reinstall with PySide6.
  - Child Python/pip arguments are quoted so install paths with spaces work.
  - pip dependency install uses retries, longer timeouts, and resume retries.
  - Runtime installs to `%LOCALAPPDATA%\CCT\rt311cpu` to avoid Windows long-path failures in PyTorch.

- Updated `packaging/windows-web-installer/runtime-requirements-cpu.txt`
  - Removed Gradio/FastAPI/Starlette/browser-server dependencies from the Windows customer runtime.
  - Keeps only native UI and video-processing dependencies:
    PySide6, PyTorch CPU, TorchVision CPU, OpenCV headless, NumPy, imageio-ffmpeg, and pinned transitive runtime packages.

- Updated `packaging/windows-web-installer/verify_runtime.py`
  - Verifies native runtime imports.
  - Checks `desktop_qt_app.ContourControlWindow` exists.

- Updated macOS packaging preparation
  - macOS launcher now points to `desktop_qt_app.py`.
  - macOS runtime verifier checks PySide6/native entry point.
  - macOS dependency list is trimmed toward the native UI path.
  - This is preparation only; build and release macOS on an actual Mac before publishing.

## Why This Design

The old portable package was too large because it bundled Python, PyTorch, and all packages directly. The app source is small; the heavy parts are the runtime and model files.

The chosen release path:

1. Publish a small Inno Setup `.exe`.
2. Include app source, assets, and installer scripts.
3. During installation, download Python 3.11 embeddable runtime and locked CPU dependencies.
4. Download Depth Anything V2 model files only on first use into `%LOCALAPPDATA%\DepthVideoConverter\models`.

This keeps the GitHub Release installer around a few MB. First install still needs internet and downloads roughly hundreds of MB of runtime packages, mainly PyTorch, MKL, PySide6, OpenCV, and bundled FFmpeg.

## Build Command

Install Inno Setup 6 on Windows, then run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_web_installer.ps1 -AppVersion 0.2.0
```

Expected output:

```text
dist\windows-installer\ContourControlTool-Windows-x64-WebSetup.exe
```

## Verification Done On 2026-08-01

Windows installer build:

```text
ContourControlTool-Windows-x64-WebSetup.exe
Size: 2,213,342 bytes
SHA256: E6E350EB86A59C3336107C6DE86A2B54CDAB4A0C6E024A1310386F56E83F1318
```

Dependency wheel check:

- Windows x64, Python 3.11 wheel download succeeded.
- 21 wheels resolved.
- Total wheel download size was about 692 MB.
- No Gradio/FastAPI/Starlette packages are required by the native runtime.

Install test:

```text
Install path: E:\Contour Control Tool Native Test
Runtime path: %LOCALAPPDATA%\CCT\rt311cpu
Runtime marker: runtime_version=2026.08.01-native-ui.2
Installer result: Installation process succeeded
Runtime install exit code: 0
Need to restart Windows? No
```

Runtime smoke test:

```text
torch: 2.3.1+cpu
torchvision: 0.18.1+cpu
cv2: 4.10.0
numpy: 1.26.4
imageio_ffmpeg: 0.6.0
PySide6: 6.7.3
desktop_qt_app.ContourControlWindow: OK
```

Native window creation test:

```text
Window title: 视频深度控制图工具
Window class: ContourControlWindow
Model choices loaded: 3
```

Shortcut test:

```text
Desktop launch: %LOCALAPPDATA%\CCT\rt311cpu\pythonw.exe "E:\Contour Control Tool Native Test\app\desktop_qt_app.py"
Desktop uninstall: E:\Contour Control Tool Native Test\unins000.exe
Start Menu launch: %LOCALAPPDATA%\CCT\rt311cpu\pythonw.exe "E:\Contour Control Tool Native Test\app\desktop_qt_app.py"
Start Menu uninstall: E:\Contour Control Tool Native Test\unins000.exe
```

## Customer Requirements

- Windows 64-bit.
- Internet access during installation.
- Internet access on first model use.
- CPU runtime is the default for compatibility; processing is slower than a GPU build.

## Troubleshooting

If installation fails, collect:

```text
%LOCALAPPDATA%\DepthVideoConverter\installer.log
```

The installer log from Inno Setup is available only when run with `/LOG=...`.

Common failure points:

- Python download blocked by network policy.
- PyPI or PyTorch wheel download interrupted.
- Hugging Face model download blocked on first use.
- Antivirus blocks unsigned installer/runtime scripts.

## Release Notes Draft

```markdown
Windows x64 native desktop installer for Contour Control Tool.

- Native desktop app: no browser, no Gradio page.
- Normal installer wizard with install-location selection.
- Small installer asset; Python/PyTorch/PySide6 runtime downloads during installation.
- Uses CPU PyTorch runtime for broad Windows compatibility.
- Creates desktop and Start Menu launch shortcuts.
- Creates desktop and Start Menu uninstall shortcuts.
- Fixed install paths with spaces.
- Fixed restart prompt after successful installation.
- Runtime packages are pinned and verified for Windows x64 Python 3.11.

Requirements:

- Windows 64-bit
- Internet access during installation
- Internet access on first model use

Troubleshooting:

If installation fails, send `%LOCALAPPDATA%\DepthVideoConverter\installer.log`.
```

## Next Mac Step

Do not publish a macOS asset from Windows. On a Mac:

1. Pull the latest repo.
2. Build the macOS package with `packaging/build_macos_web_installer.sh`.
3. Verify the native Qt window opens.
4. Verify model download and a small video conversion.
5. Then publish a separate macOS release asset.
