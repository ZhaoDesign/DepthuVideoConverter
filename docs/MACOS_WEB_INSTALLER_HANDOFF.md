# macOS Web Installer Handoff

This note records the macOS web-installer changes so another machine or agent can continue from a clean clone.

## Goal

Create a small macOS release package for Contour Control Tool. The installer should keep the app bundle light, then download the Python runtime and dependencies on first launch instead of shipping a large prebuilt `.app`.

## Why this path was chosen

The existing macOS package bundles the full runtime into the app, which makes the release large. The new path keeps the release asset small and shifts the heavy runtime work to first launch.

## Files Added

- `packaging/build_macos_web_installer.sh`
  - Builds `ContourControlTool-macOS-WebSetup.zip` and `.dmg`.
  - Assembles a small app bundle with a shell launcher.

- `packaging/macos-web-installer/launch_runtime.sh`
  - Runs when the app opens.
  - Downloads `uv` if needed.
  - Creates a Python 3.11 virtual environment in the user data directory.
  - Installs the locked runtime dependencies.
  - Verifies imports and UI creation before launching the web app.

- `packaging/macos-web-installer/runtime-requirements-macos.txt`
  - Runtime dependency list for the macOS web installer.

- `packaging/macos-web-installer/verify_runtime.py`
  - Post-install smoke test for the runtime environment.

- `packaging/macos-web-installer/README_CN.md`
  - Chinese user-facing notes for the macOS web installer.

## Runtime layout

- `~/Library/Application Support/CCT/`
  - `tools/` for the `uv` helper
  - `python/` for managed Python downloads
  - `rt311mac/` for the app virtual environment
  - `cache/` for installer downloads

- `~/Library/Application Support/DepthVideoConverter/models`
  - model checkpoints downloaded on first use

## Build Command

From the repository root:

```bash
zsh packaging/build_macos_web_installer.sh /path/to/output
```

Expected outputs:

- `ContourControlTool-macOS-WebSetup.zip`
- `ContourControlTool-macOS-WebSetup.dmg`

## Runtime Test Checklist

Use a clean macOS machine or VM:

1. Open the generated `.dmg`.
2. Drag or open the app.
3. Confirm the first launch shows a notification and prepares the runtime.
4. Confirm the local Gradio page opens.
5. Process a small video with `Small` or `Base`.
6. Confirm model downloads go to `~/Library/Application Support/DepthVideoConverter/models`.

If installation fails, collect:

```text
~/Library/Application Support/DepthVideoConverter/installer.log
```

## Known Tradeoffs

- First launch takes longer because Python and packages are downloaded.
- The installer depends on internet access.
- `uv` and its managed Python downloads are stored under the user data directory rather than inside the `.app`.
