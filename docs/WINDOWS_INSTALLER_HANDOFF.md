# Windows x64 Web Installer Handoff

This note records the Windows installer changes so another machine or agent can continue from a clean clone.

## Goal

Create a small GitHub Release installer for Windows 64-bit customers. The installer should let users choose the install location, install app files locally, then download the heavy runtime dependencies during installation instead of shipping a very large portable zip.

## Why this path was chosen

The previous portable package included a full Python runtime and all Python packages. On the inspected local build, the package `Lib` folder was about 1.76 GB after extraction, with `torch` alone about 1.2 GB. The app source itself is tiny, so bundling PyTorch directly is the main package-size problem.

The new release path is:

1. Ship a small Inno Setup installer.
2. Include only app source, assets, and installer scripts.
3. During install, download Python 3.11 embeddable runtime and locked CPU runtime dependencies into a short per-user runtime path.
4. Keep Depth Anything V2 model files out of the installer. Models are still downloaded on first use into `%LOCALAPPDATA%\DepthVideoConverter\models`.

This favors customer compatibility and small release assets. It requires internet during installation and first model use.

## Files Added

- `packaging/windows-web-installer/ContourControlToolSetup.iss`
  - Inno Setup script for `ContourControlTool-Windows-x64-WebSetup.exe`.
  - Creates Start Menu and optional desktop shortcuts.
  - Adds a Start Menu uninstall shortcut by default.
  - Adds an optional desktop quick uninstall shortcut.
  - Launch shortcuts point at `%LOCALAPPDATA%\CCT\rt311cpu\pythonw.exe`.

- `packaging/windows-web-installer/install_runtime.ps1`
  - Runs after app files are copied.
  - Downloads Python 3.11.9 embeddable runtime.
  - Installs pip.
  - Installs locked CPU runtime dependencies.
  - Writes logs to `%LOCALAPPDATA%\DepthVideoConverter\installer.log`.
  - Verifies imports and UI creation before marking the runtime as installed.
  - Installs the heavy runtime into `%LOCALAPPDATA%\CCT\rt311cpu` instead of the chosen app directory. This avoids PyTorch install failures on Windows systems without long path support.
  - Quotes child-process arguments before calling Python / pip. This is required when customers choose an install directory with spaces, such as `E:\Contour Control Tool`.
  - Uses extended pip retry and timeout settings for dependency installation, including incomplete download resume retries.
  - Wraps dependency installation in a three-attempt retry loop so a transient PyPI / PyTorch download failure does not fail the whole installer immediately.

- `packaging/windows-web-installer/runtime-requirements-cpu.txt`
  - Installer runtime dependency list.
  - Uses CPU PyTorch wheels from `https://download.pytorch.org/whl/cpu`.
  - Locks Gradio / FastAPI / Starlette to avoid the localhost startup failure caused by incompatible Starlette template APIs.
  - Fully pins the transitive package set that passed the local installer smoke test.

- `packaging/windows-web-installer/verify_runtime.py`
  - Post-install smoke test.
  - Imports the required libraries and calls `create_ui()`.

- `packaging/build_windows_web_installer.ps1`
  - Builds the Inno Setup installer.
  - Searches for `ISCC.exe` in Program Files and the current user's local Programs folder.

- `packaging/windows-web-installer/README_CN.md`
  - Chinese usage notes for the small Windows web installer.

## Files Changed

- `packaging/desktop-requirements.txt`
  - Locked `fastapi==0.112.4` and `starlette==0.38.6`.
  - Locked `opencv-python==4.10.0.84`, `numpy==1.26.4`, and `imageio-ffmpeg==0.6.0`.
  - This prevents future dependency resolution from pulling `starlette 1.x`, which caused Gradio 4.44.1 to fail when opening the local page.

## Build Command

Install Inno Setup 6 on Windows, then run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_web_installer.ps1 -AppVersion 0.1.0
```

Expected output:

```text
dist\windows-installer\ContourControlTool-Windows-x64-WebSetup.exe
```

The generated installer is small because it does not include Python packages or models.

## Runtime Test Checklist

Use a clean Windows 64-bit test machine or VM:

1. Run `ContourControlTool-Windows-x64-WebSetup.exe`.
2. Choose a custom install path.
3. Let the installer download the runtime dependencies.
4. Confirm Start Menu contains:
   - `视频深度控制图工具`
   - `Uninstall 视频深度控制图工具`
5. Launch the app and confirm the local Gradio page opens.
6. Process a small video with `Small (fastest, ~95 MB)`.
7. Confirm first-use model download goes to `%LOCALAPPDATA%\DepthVideoConverter\models`.
8. Use the uninstall shortcut and confirm the install directory is removed.
   - The installer explicitly removes generated `__pycache__` leftovers under `{app}\app`.
   - The shared short runtime path `%LOCALAPPDATA%\CCT\rt311cpu` is removed on uninstall.

If installation fails, collect:

```text
%LOCALAPPDATA%\DepthVideoConverter\installer.log
```

The installer was adjusted after a local failure in a deep test path. The original design installed PyTorch under the selected app directory; that failed with a Windows long-path error. The runtime now uses `%LOCALAPPDATA%\CCT\rt311cpu`, which keeps PyTorch's internal include paths short enough for default Windows settings.

The installer was also adjusted after a customer-path test failed at:

```text
ERROR: Invalid requirement: 'Tool\installer\runtime-requirements-cpu.txt'
```

Root cause: PowerShell `Start-Process -ArgumentList` joined array arguments without preserving the full `-r` requirements path when the selected app directory contained spaces. `install_runtime.ps1` now quotes each child-process argument before calling Python / pip. A later validation reached the correct full path:

```text
E:\Contour Control Tool Space Test\installer\runtime-requirements-cpu.txt
```

That same validation exposed a separate transient network failure while downloading package metadata. The dependency install command now uses longer socket timeouts plus connection and incomplete-download retry settings, and the script retries the whole dependency install step up to three times.

## GitHub Release Notes Draft

Release asset:

```text
ContourControlTool-Windows-x64-WebSetup.exe
```

Suggested description:

```markdown
Windows x64 web installer for Contour Control Tool.

- Small installer package; runtime dependencies download during installation.
- Lets users choose the installation path.
- Models are downloaded on first use into `%LOCALAPPDATA%\DepthVideoConverter\models`.
- Default runtime uses CPU PyTorch for compatibility. Processing is slower than GPU builds.
- Includes Start Menu launch and uninstall shortcuts. Optional desktop uninstall shortcut is available during setup.

Requirements:

- Windows 64-bit
- Internet access during installation
- Internet access on first model use

Troubleshooting:

If installation fails, send `%LOCALAPPDATA%\DepthVideoConverter\installer.log`.
```

## Known Tradeoffs

- First install can take several minutes because PyTorch and related packages are downloaded.
- CPU runtime is more compatible and smaller than CUDA runtime, but slower.
- Customers behind strict network filtering may fail to download Python, PyPI packages, PyTorch CPU wheels, or Hugging Face model files.
- A future GPU installer can be added as a separate larger release asset.
