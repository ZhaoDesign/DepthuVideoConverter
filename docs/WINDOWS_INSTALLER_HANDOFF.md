# Windows x64 Native Installer Handoff

This note records the Windows customer installer work so another machine or agent can continue from a clean clone.

## Current Goal

Ship a customer-friendly Windows 64-bit installer for DepthuVideoConverter:

1. A normal installation wizard with install-location selection.
2. A native desktop application window, not a browser or Gradio page.
3. Small GitHub Release asset size by downloading the heavy runtime during installation.
4. Start Menu and desktop launch shortcuts.
5. No desktop or Start Menu uninstall shortcut.
6. No restart prompt after a successful install.

## Current Release: v2026.08.17.1

The Windows x64 packages for the current native PySide6 direction have been built and smoke-tested:

- `DepthuVideoConverter-Windows-x64-WebSetup.exe` — small online installer;
- `DepthuVideoConverter-Windows-x64-OfflineSetup.exe`;
- `DepthuVideoConverter-Windows-x64-OfflineSetup-1.bin`;
- `DepthuVideoConverter-Windows-x64-OfflineSetup-2.bin` — offline package split files.

The offline `.exe` and both `.bin` files must stay in the same directory. The release page is:

`https://github.com/ZhaoDesign/DepthuVideoConverter/releases/tag/v2026.08.17.1`

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
  - Default install location is per-user: `%LOCALAPPDATA%\Programs\DepthuVideoConverter`.
  - The user can still choose a custom path, including paths with spaces.
  - Runtime install runs hidden inside the installer, so customers do not see a PowerShell window.
  - Chinese installer text is added for the main wizard steps.
  - Uninstall remains available from Windows Settings / Control Panel.
  - Legacy desktop and Start Menu uninstall shortcuts are removed during upgrades.
  - Restart prompts are disabled for the runtime install step.

- Updated `packaging/windows-web-installer/install_runtime.ps1`
  - Runtime marker now includes `runtime_version=2026.08.08-cuda`.
  - Changing the runtime marker forces older browser-runtime installs to reinstall with PySide6.
  - Child Python/pip arguments are quoted so install paths with spaces work.
  - pip dependency install uses retries, longer timeouts, and resume retries.
  - Runtime installs to `%LOCALAPPDATA%\CCT\rt311cuda` to avoid Windows long-path failures in PyTorch.

- Updated `packaging/windows-web-installer/runtime-requirements-cuda.txt`
  - Removed Gradio/FastAPI/Starlette/browser-server dependencies from the Windows customer runtime.
  - Keeps only native UI and video-processing dependencies:
    PySide6, CUDA PyTorch, ONNX Runtime fallback, OpenCV headless, NumPy, imageio-ffmpeg, and pinned runtime packages.

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

The chosen release paths:

1. Publish a small online Inno Setup `.exe`.
2. Publish an offline CUDA package as one launcher `.exe` plus two `.bin` slices.
3. Include app source, assets, and installer scripts.
4. The online installer downloads Python 3.11 and locked CUDA PyTorch dependencies during setup.
5. The offline package includes the CUDA runtime and the Small + Base models.

The online installer remains a few MB. The offline package is split so each GitHub Release asset stays below the single-file upload limit; keep all three offline files in the same folder before running the `.exe`.

## Build Command

Install Inno Setup 6 on Windows, then run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_web_installer.ps1 -AppVersion 2026.08.17.1
```

Expected output:

```text
dist\windows-installer\DepthuVideoConverter-Windows-x64-WebSetup.exe
```

Offline build:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_offline_installer.ps1 -AppVersion 2026.08.17.1
```

Expected offline files:

```text
dist\windows-installer\DepthuVideoConverter-Windows-x64-OfflineSetup.exe
dist\windows-installer\DepthuVideoConverter-Windows-x64-OfflineSetup-1.bin
dist\windows-installer\DepthuVideoConverter-Windows-x64-OfflineSetup-2.bin
```
## Verification Done On 2026-08-17

Windows installer build:

```text
DepthuVideoConverter-Windows-x64-WebSetup.exe
Size: 2,334,007 bytes
SHA256: 3A24463E6EAED0332A0C16BF7930EBF12EA626FCA4CDFCE6F4DBFDBC422EAD1F

DepthuVideoConverter-Windows-x64-OfflineSetup.exe
Size: 3,156,891 bytes
SHA256: C0C4BDEE7436F461F7870C2174F5E304CF243410F7967686B6D67634849E0CEA

DepthuVideoConverter-Windows-x64-OfflineSetup-1.bin
Size: 1,896,843,008 bytes
SHA256: 2089EAA2C0F3F3D3E5683F528EDE147641ABE802D9CAD4CD4EBCB02AC320B7EC

DepthuVideoConverter-Windows-x64-OfflineSetup-2.bin
Size: 1,263,255,126 bytes
SHA256: 48FAC8C9C9619B0D88FE1F764D92EEB56D8D507B3BECDA6BEE174AEAEFFC7E94
```

Install test:

```text
Online smoke install path: repository `build\smoke-online-install-20260817`
Offline smoke install path: repository `build\smoke-offline-install-20260817-c`
Runtime path: %LOCALAPPDATA%\CCT\rt311cuda
Runtime marker: runtime_version=2026.08.08-cuda
Online installer result: Installation process succeeded
Offline installer result: Installation process succeeded
Runtime install exit code: 0
Need to restart Windows? No
```

Runtime smoke test:

```text
torch: 2.13.0+cu126
torch.cuda: available on supported NVIDIA systems
cv2: 4.10.0
numpy: 1.26.4
imageio_ffmpeg: 0.6.0
PySide6: 6.7.3
desktop_qt_app.ContourControlWindow: OK
```

Native window creation test:

```text
Window title: DepthuVideoConverter
Window class: ContourControlWindow
Model choices loaded: 3
```

Shortcut test:

```text
Desktop launch: %LOCALAPPDATA%\CCT\rt311cuda\pythonw.exe "{install}\app\desktop_qt_app.py"
Start Menu launch: %LOCALAPPDATA%\CCT\rt311cuda\pythonw.exe "{install}\app\desktop_qt_app.py"
Desktop / Start Menu uninstall shortcuts: not created
```

## Customer Requirements

- Windows 64-bit.
- Online installer: internet access during installation.
- Online installer: internet access on first Base/Large model use.
- Offline installer: no internet required during installation or Small + Base model use.
- CUDA PyTorch is preferred when an NVIDIA GPU is available; ONNX Runtime remains the CPU fallback.

## Troubleshooting

If installation fails, collect:

```text
%LOCALAPPDATA%\DepthuVideoConverter\installer.log
```

The installer log from Inno Setup is available only when run with `/LOG=...`.

Common failure points:

- Python download blocked by network policy.
- PyPI or PyTorch wheel download interrupted.
- Hugging Face model download blocked on first use.
- Antivirus blocks unsigned installer/runtime scripts.

## Release Notes Draft

```markdown
Windows x64 native desktop installer for DepthuVideoConverter.

- Native desktop app: no browser, no Gradio page.
- Normal installer wizard with install-location selection.
- Small installer asset; Python/PyTorch/PySide6 runtime downloads during installation.
- Uses CUDA PyTorch on supported NVIDIA systems, with ONNX Runtime CPU fallback.
- Creates desktop and Start Menu launch shortcuts.
- Does not create desktop or Start Menu uninstall shortcuts.
- Fixed install paths with spaces.
- Fixed restart prompt after successful installation.
- Runtime packages are pinned and verified for Windows x64 Python 3.11.
- Offline CUDA package is split into one `.exe` and two `.bin` files; keep them together.

Requirements:

- Windows 64-bit
- Online installer: internet access during installation
- Offline installer: no internet required during installation or Small + Base model use

Troubleshooting:

If installation fails, send `%LOCALAPPDATA%\DepthuVideoConverter\installer.log`.
```

## Next Mac Step

Do not publish a macOS asset from Windows. On a Mac:

1. Pull the latest repo.
2. Build the macOS package with `packaging/build_macos_web_installer.sh`.
3. Verify the native Qt window opens.
4. Verify model download and a small video conversion.
5. Then publish a separate macOS release asset.
