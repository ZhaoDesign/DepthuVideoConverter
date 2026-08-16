# Depth Video Converter — Architecture

> **Current local direction (2026-08-14):** The supported application path is `desktop_launcher.py` → `desktop_qt_app.py` → `depth_converter/`. The UI is a native PySide6 window modeled on the reference project, and conversion runs directly in the local Python process. The Tauri/FastAPI/Web sections below are historical reference only and are not part of the current local restoration scope.

> **Version:** 2.0  
> **Last updated:** 2026-07-23  
> **Status:** Draft

---

## Table of Contents

- [Overview](#overview)
- [Design principles](#design-principles)
- [System architecture](#system-architecture)
- [Layer breakdown](#layer-breakdown)
  - [1. Shared Core (`depth_converter/`)](#1-shared-core-depth_converter)
  - [2. Gradio Web UI (`depth_video_converter.py`)](#2-gradio-web-ui-depth_video_converterpy)
  - [3. FastAPI Sidecar (`server/`)](#3-fastapi-sidecar-server)
  - [4. Tauri Desktop Shell (`desktop/`)](#4-tauri-desktop-shell-desktop)
- [Component interaction](#component-interaction)
- [Data flow](#data-flow)
- [Project structure](#project-structure)
- [Technology decisions](#technology-decisions)
- [Constraints & trade-offs](#constraints--trade-offs)

---

## Overview

Depth Video Converter is currently maintained as a native local desktop video depth-estimation tool:

| Interface | Entrypoint | Target user |
|---|---|---|
| **Native desktop app** | `python desktop_launcher.py` | End users |
| **CLI / library** | `from depth_converter import process_video` | Developers and scripts |

The supported desktop path uses one **pure-Python core** (`depth_converter/`) directly. The old Gradio, FastAPI, and Tauri paths remain in this document only as migration history; they are not restored by the current local work.

---

## Design principles

1. **Native-first local workflow** — The PySide6 entrypoint is the primary user workflow and does not start an online queue, Web service, or Tauri shell.

2. **Single source of truth** — The inference pipeline, model loading, FFmpeg helpers, and smoothing exist in exactly one place: `depth_converter/`.

3. **Python stays Python** — The Depth Anything V2 model is PyTorch; there is no Rust rewrite of the core logic. The native window calls the local Python core directly.

4. **Thin native UI layer** — The PySide6 window owns presentation and user interaction; all heavy lifting stays in Python core modules.

5. **Independent deployability** — Each interface can be run in isolation. The desktop app bundles its own Python environment.

---

## System architecture

```
                           ┌──────────────────────────────────────┐
                           │          depth_converter/            │
                           │         (Pure Python, no UI)         │
                           │                                      │
                           │  core.py     inference pipeline      │
                           │  models.py   load_model(), devices   │
                           │  ffmpeg.py   encoding + audio mux    │
                           │  smoothing.py  TemporalSmoother      │
                           └────┬─────┬──────┬───────────────────┘
                                │     │      │
                    ┌───────────┘     │      └──────────────┐
                    ▼                 ▼                      ▼
          ┌──────────────┐  ┌──────────────┐      ┌──────────────────┐
          │ Gradio UI    │  │ FastAPI      │      │ CLI / scripts    │
          │ (existing)   │  │ Sidecar      │      │                  │
          │              │  │              │      │ >>> from          │
          │ depth_video_ │  │ server/      │      │ depth_converter  │
          │ converter.py │  │ main.py      │      │ import ...       │
          │              │  │              │      │                  │
          │ localhost:   │  │ localhost:   │      │ process_video()  │
          │ 7860         │  │ 9876         │      │                  │
          └──────────────┘  └──────┬───────┘      └──────────────────┘
                                   │ HTTP (127.0.0.1 only)
                                   ▼
                         ┌──────────────────┐
                         │  Tauri Desktop   │
                         │  Shell           │
                         │                  │
                         │  desktop/        │
                         │  ├── src-tauri/   │  Rust: spawn + manage
                         │  │               │  Python process
                         │  └── src/         │  React 19 + Tailwind
                         │                  │
                         │  Native window,   │
                         │  .dmg / .exe      │
                         └──────────────────┘
```

### Why not call `process_video()` directly from Rust?

PyTorch models cannot be loaded from Rust. Options:

| Approach | Pros | Cons |
|---|---|---|
| Rust ML (candle / burn) | Single binary | Depth Anything V2 not supported; huge effort |
| Python embedded in Rust | Fast IPC | CPython embedding is fragile, GIL issues |
| **Python sidecar + local HTTP** ✅ | Clean separation, debuggable, same as Shuttle pattern | ~2ms HTTP overhead (negligible vs. minutes of inference) |

Shuttle uses the same pattern: a Rust/axum backend manages its own HTTP server. Here the "backend" is Python/FastAPI. The architectural principle is identical.

---

## Layer breakdown

### 1. Shared Core (`depth_converter/`)

The pure-Python library. **No UI code, no Gradio, no FastAPI.** Only the domain logic.

```
depth_converter/
├── __init__.py           # Public API exports
├── core.py               # process_video() — the main pipeline
├── models.py             # MODEL_DEFS, load_model(), detect_device()
├── ffmpeg.py             # _ffmpeg_available(), extract_audio(), write_video_ffmpeg(), merge_audio_video()
└── smoothing.py          # TemporalSmoother, depth_to_grayscale()
```

#### Public API (`depth_converter/__init__.py`)

```python
from depth_converter.core import process_video
from depth_converter.models import MODEL_DEFS, load_model, detect_device
from depth_converter.smoothing import TemporalSmoother, depth_to_grayscale

__all__ = [
    "process_video",
    "MODEL_DEFS",
    "load_model",
    "detect_device",
    "TemporalSmoother",
    "depth_to_grayscale",
]
```

#### `core.py` — `process_video()`

The signature changes slightly: the `progress` parameter becomes a generic callback protocol instead of being tied to `gr.Progress`.

```python
from typing import Protocol

class ProgressCallback(Protocol):
    def __call__(self, fraction: float, description: str) -> None: ...

def process_video(
    input_video_path: str,
    model_size_label: str,
    resolution_choice: str,
    invert_bw: bool,
    smoothing_strength: float,
    preserve_audio: bool,
    progress: ProgressCallback | None = None,
) -> str: ...
```

Gradio's `gr.Progress` already satisfies this protocol (it's `callable(fraction, desc)`), so no Gradio changes are needed. The FastAPI server passes a callback that updates an in-memory progress dict.

#### Extraction strategy

The function is already well-factored — the helpers are module-level functions. The extraction is mechanical:

1. Move `detect_device()` → `depth_converter/models.py`
2. Move all FFmpeg helpers → `depth_converter/ffmpeg.py`
3. Move `TemporalSmoother` + `depth_to_grayscale()` → `depth_converter/smoothing.py`
4. Move `MODEL_DEFS`, `RESOLUTION_PRESETS`, `load_model()`, `_ensure_checkpoint()`, `_download_with_progress()` → `depth_converter/models.py`
5. Move `process_video()` → `depth_converter/core.py` (add `ProgressCallback` protocol, decouple from `gr`)
6. `depth_video_converter.py` imports from `depth_converter` instead of its own module-level definitions. The Gradio UI code (`create_ui()`, `main()`) stays in place.

### 2. Gradio Web UI (`depth_video_converter.py`)

**Changes are minimal:**

```python
# Before
from depth_anything_v2 import DepthAnythingV2
# ... all helpers and globals defined here ...
def process_video(...): ...
def create_ui(): ...
def main(): ...

# After
from depth_converter import (
    process_video,
    MODEL_DEFS,
    RESOLUTION_PRESETS,
    detect_device,
)
from depth_converter.ffmpeg import _ffmpeg_available

# create_ui() and main() — unchanged
```

- `create_ui()` and `main()` remain byte-for-byte identical.
- Gradio's `gr.Progress` is passed directly as the `progress` callback — it already matches `(float, str) -> None`.
- `PROJECT_DIR`, `MODELS_DIR` now live in `depth_converter/models.py`.

### 3. FastAPI Sidecar (`server/`)

A lightweight REST API that wraps `process_video()`. Bound to `127.0.0.1` only (never exposed to the network).

```
server/
├── __init__.py
├── main.py                # FastAPI app
└── __init__.py
```

#### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Returns `{"status": "ok", "device": "...", "ffmpeg": true/false}` |
| `POST` | `/api/process` | Upload video + params → returns depth video |
| `GET` | `/api/progress/{task_id}` | Poll progress (0.0–1.0 + description) |
| `GET` | `/api/models` | List available models and their status (cached/downloaded) |

#### `POST /api/process` request (multipart/form-data)

```
input_video:        file          (required)
model_size_label:   string        (default: "Small (fastest, ~95 MB)")
resolution_choice:  string        (default: "Original")
invert_bw:          bool          (default: false)
smoothing_strength: int           (default: 60, range 0–100)
preserve_audio:     bool          (default: true)
```

Response: `application/octet-stream` — the output `.mp4` file.

#### Progress mechanism

Since inference runs in the same process (blocking the async loop), we run it in a thread pool:

```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

_progress_store: dict[str, tuple[float, str]] = {}

def _progress_callback(task_id: str, fraction: float, desc: str):
    _progress_store[task_id] = (fraction, desc)

async def process_endpoint(...):
    task_id = str(uuid4())
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = await loop.run_in_executor(
            pool,
            process_video,
            input_path, model, res, invert, smoothing, audio,
            lambda f, d: _progress_callback(task_id, f, d),
        )
    return FileResponse(result)
```

#### Startup

```bash
python -m server.main
# → Uvicorn running on http://127.0.0.1:9876
```

The port is configurable via `DEPTH_SERVER_PORT` env var (default: 9876).

### 4. Tauri Desktop Shell (`desktop/`)

Directly mirrors Shuttle's structure and dependency versions.

```
desktop/
├── package.json              # React 19, Vite 7, Tailwind v4, TanStack Query, Zustand, Lucide
├── vite.config.ts            # Same pattern as Shuttle (port 1420, strictPort)
├── tsconfig.json
├── tsconfig.node.json
├── index.html
├── src/
│   ├── main.tsx              # React entry
│   ├── App.tsx               # Root layout
│   ├── styles/
│   │   └── globals.css       # Tailwind directives + custom theme
│   ├── components/
│   │   ├── layout/
│   │   │   └── AppLayout.tsx       # Window chrome: title bar, status
│   │   ├── upload/
│   │   │   └── VideoUpload.tsx     # Drag-and-drop upload zone
│   │   ├── settings/
│   │   │   └── SettingsPanel.tsx   # Model, resolution, invert, smoothing
│   │   ├── progress/
│   │   │   └── ProgressPanel.tsx   # Progress bar + ETA
│   │   └── preview/
│   │       └── VideoPreview.tsx    # Before/after video player
│   ├── hooks/
│   │   ├── useProcessVideo.ts      # TanStack Query mutation
│   │   └── useServerHealth.ts      # Health check + auto-start
│   ├── stores/
│   │   └── settingsStore.ts        # Zustand — persisted settings
│   └── lib/
│       ├── api.ts                  # Base URL + fetch wrapper
│       └── utils.ts               # Misc helpers
├── src-tauri/
│   ├── Cargo.toml           # tauri 2, tokio, reqwest, serde
│   ├── tauri.conf.json      # Window config, bundle targets
│   ├── capabilities/
│   │   └── default.json     # Permissions
│   ├── icons/               # App icons (all sizes)
│   └── src/
│       ├── main.rs           # Entry: setup tracing, spawn sidecar, run app
│       └── lib.rs            # Tauri commands + sidecar lifecycle
```

#### Rust side (`src-tauri/src/lib.rs`)

Core responsibilities:

1. **Sidecar lifecycle management**
   ```rust
   struct PythonSidecar {
       child: Mutex<Option<Child>>,
       port: u16,
   }
   
   impl PythonSidecar {
       async fn start(&self) -> Result<()>;
       async fn health_check(&self) -> Result<bool>;
       async fn stop(&self);
   }
   ```

2. **Tauri commands** (exposed to React via `@tauri-apps/api`)
   ```rust
   #[tauri::command]
   async fn get_server_status(state: State<'_>) -> Result<ServerStatus>;
   
   #[tauri::command]
   async fn restart_sidecar(state: State<'_>) -> Result<()>;
   ```

3. **Startup sequence:**
   - App launches → spawn `python -m server.main`
   - Poll `/api/health` until ready (max 30s timeout)
   - Show health status in UI
   - On window close → send SIGTERM to Python, wait 5s, SIGKILL

#### React side — component tree

```
<App>
  <AppLayout>
    <StatusBar />            ← device detected, model loaded, ffmpeg status
    <div class="grid-2col">
      <VideoUpload />        ← drag .mp4/.mov, show original preview
      <VideoPreview />       ← show output video after processing
    </div>
    <SettingsPanel />        ← all controls (model/size/res/invert/smoothing/audio)
    <ProgressPanel />        ← visible only during processing
  </AppLayout>
</App>
```

#### Window spec

| Property | Value |
|---|---|
| Default size | 960 × 680 px |
| Min size | 720 × 500 px |
| Title | Depth Video Converter |
| Identifier | `com.depthvideo.converter` |
| Bundle targets | `.dmg` (macOS), `.msi` (Windows), `.deb` + `.AppImage` (Linux) |

---

## Component interaction

```
React (UI)                     Rust (Tauri)                Python (Sidecar)
    │                               │                            │
    │  @tauri invoke               │                            │
    │  "get_server_status" ────────▶                            │
    │                               │  GET /api/health ────────▶│
    │                               │  ◀────── {"ok":true} ──── │
    │  ◀─────── {status:"ok"} ──────│                            │
    │                               │                            │
    │  fetch /api/process           │                            │
    │  (multipart) ────────────────────────────────────────────▶│
    │                               │                            │
    │  poll /api/progress/{id} ─────────────────────────────────▶│
    │  ◀─────── {progress:0.45} ─────────────────────────────── │
    │                               │                            │
    │  ◀─────── output.mp4 ──────────────────────────────────── │
    │                               │                            │
    │  [user closes app]           │                            │
    │                               │  SIGTERM ─────────────────▶│
    │                               │  ◀── shutdown ──────────── │
```

**Note:** The React frontend calls the Python sidecar directly (via `fetch`) for video processing — the Rust layer only mediates sidecar lifecycle + status. This avoids funneling large video files through Rust IPC, which would add unnecessary overhead.

---

## Data flow

```
User drops video file
        │
        ▼
┌─────────────────┐
│  React: validate │  Check format, size, duration
│  .mp4 / .mov    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Write to temp   │  Tauri path API → system temp dir
│  file on disk    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  POST /api/      │  multipart/form-data
│  process         │  + params as form fields
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI saves   │  tempfile on Python side
│  uploaded file   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  depth_converter │  Load model → read frames →
│  .process_video()│  depth inference → smoothing →
│                   │  ffmpeg encode → mux audio
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Return .mp4     │  FileResponse
│  to React        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  React: save or  │  Show in <video> player
│  open in finder  │  + "Save As" button
└─────────────────┘
```

---

## Project structure (final)

```
DepthVideoCoverter/
│
├── depth_converter/                   # ★ NEW — Shared Python core
│   ├── __init__.py                    #     Public API
│   ├── core.py                        #     process_video() pipeline
│   ├── models.py                      #     Model loading, device detection
│   ├── ffmpeg.py                      #     FFmpeg helpers
│   └── smoothing.py                   #     TemporalSmoother, grayscale
│
├── depth_anything_v2/                 # (unchanged) Vendored DA V2 model
│   ├── __init__.py
│   ├── dpt.py
│   ├── dinov2.py
│   ├── dinov2_layers/
│   └── util/
│
├── server/                            # ★ NEW — FastAPI sidecar
│   ├── __init__.py
│   └── main.py                        #     REST API for desktop shell
│
├── desktop/                           # ★ NEW — Tauri desktop app
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── index.html
│   ├── src/                           #     React frontend
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── styles/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── stores/
│   │   └── lib/
│   └── src-tauri/                     #     Rust shell
│       ├── Cargo.toml
│       ├── tauri.conf.json
│       ├── capabilities/
│       ├── icons/
│       └── src/
│           ├── main.rs
│           └── lib.rs
│
├── depth_video_converter.py           # (minimal changes) Gradio UI + main()
├── models/                            # (unchanged) Checkpoint cache
├── examples/                          # (unchanged) Demo videos
├── docs/                              # ★ NEW — Architecture & plans
│   ├── ARCHITECTURE.md
│   └── DEV_PLAN.md
├── requirements.txt                   # (unchanged) Py dependencies
├── README.md                          # (append desktop section)
├── README_CN.md                       # (append desktop section)
└── .gitignore                         # (append desktop ignores)
```

---

## Technology decisions

| Decision | Rationale |
|---|---|
| **FastAPI over Flask** | Async support for progress polling; native `FileResponse` streaming; Pydantic validation |
| **Tauri over Electron** | 15 MB vs 150 MB bundle; native performance; Shuttle already uses it |
| **React + Tailwind over Gradio for desktop** | Full design control; Shuttle exact dependency match; Zustand for persistence |
| **Local HTTP over Unix sockets** | Cross-platform (Windows no sockets); simpler debugging with curl |
| **Python sidecar over embedded Python** | No CPython ABI fragility; independent venv; easy to update Python independently |
| **127.0.0.1 only binding** | Security — no network exposure; firewall not needed |
| **Uvicorn over Gunicorn** | Single-worker is enough (one user, one GPU); simpler |

---

## Constraints & trade-offs

### What this architecture does NOT support

- **Multiple concurrent users** — The Python sidecar runs one model in memory. Parallel requests would OOM. This is a single-user desktop tool.
- **GPU sharing** — The sidecar takes the GPU exclusively while processing.
- **Headless server deployment** — The desktop shell expects a local Python environment. Cloud deployment would need a separate Docker-based approach (out of scope for v2.0).

### Risks

| Risk | Mitigation |
|---|---|
| Python not found on user's PATH | Bundled Python via `python-build-standalone` or prompt to install |
| Large models (1.2 GB) download on first use | Show download progress in desktop UI; pre-bundle Small model |
| FFmpeg not installed | Bundle `ffmpeg` binary in the desktop app (Tauri `externalBin`) |
| Sidecar crashes mid-processing | Rust monitors child process; auto-restart + show error in UI |
| Mac code signing for `.dmg` | Notarization CI with `gon` or `notarytool` (separate setup) |
