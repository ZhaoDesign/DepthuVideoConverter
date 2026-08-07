# Development Plan — Desktop App (Tauri + FastAPI Sidecar)

> **Plan version:** 1.0  
> **Created:** 2026-07-23  
> **Status:** Ready for review  
> **Reference:** [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Overview

This plan covers the phased implementation of a Tauri desktop application for DepthuVideoConverter, built on top of an extracted shared Python core library.

**Total phases:** 5  
**Estimated effort:** ~2–3 days (all-in)

---

## Phase 0: Project Setup & Prep

**Goal:** Create directory scaffolding, update `.gitignore`, verify nothing is broken before we start.

### Tasks

| # | Task | Verification |
|---|---|---|
| 0.1 | Create directory structure: `depth_converter/`, `server/`, `desktop/`, `docs/` (already done) | `ls` shows expected dirs |
| 0.2 | Update `.gitignore` with desktop ignores (`node_modules/`, `dist/`, `src-tauri/target/`, `*.tsbuildinfo`) | `git status` clean after adding |
| 0.3 | Run existing Gradio app to establish baseline | `python depth_video_converter.py` works from CLI |
| 0.4 | Commit baseline: `chore: scaffold project directories for v2 desktop refactor` | Clean commit on `main` |

### Files touched

- `.gitignore` — append desktop entries

---

## Phase 1: Extract Shared Core (`depth_converter/`)

**Goal:** Move all domain logic out of `depth_video_converter.py` into a shared `depth_converter/` package. The Gradio file becomes a thin UI wrapper that imports from the package. This is the critical phase — if this breaks, everything else breaks.

### Tasks

| # | Task | Details | Verification |
|---|---|---|---|
| 1.1 | Create `depth_converter/ffmpeg.py` | Move `_ffmpeg_available()`, `_get_ffmpeg_path()`, `_has_audio_stream()`, `extract_audio()`, `write_video_ffmpeg()`, `merge_audio_video()` | Import works in REPL |
| 1.2 | Create `depth_converter/smoothing.py` | Move `TemporalSmoother` class, `depth_to_grayscale()` | Import works in REPL |
| 1.3 | Create `depth_converter/models.py` | Move `MODEL_DEFS`, `RESOLUTION_PRESETS`, `detect_device()`, `load_model()`, `_cached_model`, `_download_with_progress()`, `_ensure_checkpoint()`. Add `PROJECT_DIR`, `MODELS_DIR`. | Import works in REPL |
| 1.4 | Create `depth_converter/core.py` | Move `process_video()`. Add `ProgressCallback` protocol. Decouple from `gr.Error` → use `RuntimeError` (Gradio layer catches and wraps). Decouple from `gr.Progress` → use the protocol. | Import works in REPL |
| 1.5 | Create `depth_converter/__init__.py` | Export public API: `process_video`, `MODEL_DEFS`, `RESOLUTION_PRESETS`, `detect_device`, `load_model`, `TemporalSmoother`, `depth_to_grayscale` | `from depth_converter import process_video` works |
| 1.6 | Refactor `depth_video_converter.py` | Replace all moved function/class bodies with imports from `depth_converter`. Add a thin `RuntimeError` → `gr.Error` adapter in `process_video` wrapper. `create_ui()` and `main()` stay verbatim. | Run Gradio app, upload video, process end-to-end |
| 1.7 | Run full processing test | Process `examples/original.mp4` with Small model, verify output identical to baseline | `cmp` or `ffmpeg -i` comparison |

### Files changed
- `depth_video_converter.py` — ~200 lines removed, ~30 lines of imports added
- `depth_converter/` — 5 new files, ~400 lines total (moved, not new code)

### Rollback plan
If Phase 1 breaks Gradio, revert: `git checkout depth_video_converter.py && rm -rf depth_converter/`. Zero risk to the model code or Gradio UI.

---

## Phase 2: FastAPI Sidecar (`server/`)

**Goal:** A standalone FastAPI server that wraps `process_video()` behind a REST API. Callable via `curl`, HTTP client, or the desktop shell.

### Tasks

| # | Task | Details | Verification |
|---|---|---|---|
| 2.1 | Create `server/main.py` | FastAPI app with CORS restricted to `http://localhost:1420` (Tauri dev port). Endpoints: `GET /api/health`, `POST /api/process`, `GET /api/progress/{task_id}`, `GET /api/models` | `python -m server.main` starts on 9876 |
| 2.2 | Implement `/api/health` | Returns device info, ffmpeg status, available models, server version | `curl http://127.0.0.1:9876/api/health` |
| 2.3 | Implement `/api/process` | Accepts multipart upload + form params. Runs `process_video()` in thread pool. Returns output `.mp4`. | `curl -F "input_video=@examples/original.mp4" -F "model_size_label=Small (fastest, ~95 MB)" http://127.0.0.1:9876/api/process -o out.mp4` |
| 2.4 | Implement `/api/progress/{task_id}` | Polled by desktop UI; returns `{"progress": 0.45, "description": "Depth inference 120/450"}` | `curl` during processing shows incrementing progress |
| 2.5 | Implement `/api/models` | Returns list of models with download status, file size | `curl http://127.0.0.1:9876/api/models` |
| 2.6 | Add `uvicorn` and `fastapi` to `requirements.txt` | Add `fastapi>=0.110` and `uvicorn[standard]>=0.29` | `pip install -r requirements.txt` includes them |
| 2.7 | Full end-to-end test | Start server, process a video via curl, verify output | Output video plays correctly |

### Files changed
- `server/main.py` — ~200 lines new
- `requirements.txt` — 2 lines added

---

## Phase 3: Tauri Desktop Shell (`desktop/`)

**Goal:** A native desktop app that looks and feels like Shuttle, talks to the Python sidecar, and lets users drag-drop videos to convert them.

### Tasks

| # | Task | Details | Verification |
|---|---|---|---|
| 3.1 | Scaffold Tauri + React project | `npm create vite@latest desktop -- --template react-ts`, then `cd desktop && npm install @tauri-apps/cli@^2 @tauri-apps/api@^2 && npx tauri init`. Mirror Shuttle's `package.json` dependencies. | `npm run dev` starts Vite on :1420 |
| 3.2 | Configure `tauri.conf.json` | Window size 960×680, min 720×500. Bundle targets: dmg, msi, deb, appimage. CSP: allow localhost fetch. | `npx tauri dev` opens a native window |
| 3.3 | Implement Rust sidecar manager (`src-tauri/src/lib.rs`) | `PythonSidecar` struct: spawn `python -m server.main`, health-check polling loop, graceful shutdown on app close. Tauri commands: `get_server_status`, `restart_sidecar`. | App starts → Python process visible in `ps aux`; close app → process gone |
| 3.4 | Build React layout (`App.tsx`, `AppLayout.tsx`) | Two-column layout: left = upload + settings, right = preview. Status bar at top showing device/model/ffmpeg. Same Tailwind v4 + Lucide icons as Shuttle. | UI renders in browser during dev |
| 3.5 | Implement `VideoUpload.tsx` | Drag-and-drop zone, file picker fallback, `.mp4`/`.mov` filter. Show thumbnail + metadata (duration, resolution, size). | Drag a video → shows preview |
| 3.6 | Implement `SettingsPanel.tsx` | Dropdowns for model/resolution, checkbox for invert, slider for smoothing, checkbox for preserve audio. Values stored in Zustand `settingsStore` (persisted to localStorage). | Settings persist across reloads |
| 3.7 | Implement `useServerHealth.ts` | Polls `/api/health` on mount. Shows green/red indicator in status bar. Auto-retry with backoff if sidecar not yet ready. | Status indicator shows correct state |
| 3.8 | Implement `useProcessVideo.ts` | TanStack Query mutation. POSTs to `/api/process`. Polls `/api/progress/{task_id}` every 500ms. Returns output video blob. | Click process → progress bar fills → output video appears |
| 3.9 | Implement `ProgressPanel.tsx` | Progress bar + percentage + "Depth inference 120/450 — 45s remaining". Shown during active processing, hidden otherwise. | Matches design during processing |
| 3.10 | Implement `VideoPreview.tsx` | `<video>` player for the output depth video. "Save As…" button (writes to user-chosen path via Tauri dialog API). | Output plays in-app |
| 3.11 | Polish and styling | Apply Tailwind v4 theme, responsive layout, dark mode support. Match Shuttle's design language (clean, minimal, professional). | Visual review side-by-side with Shuttle |
| 3.12 | Bundle test (macOS) | `npx tauri build --target aarch64-apple-darwin` → produces `.dmg`. Install and run end-to-end. | Double-click `.dmg` → app opens → process video → output plays |

### Files changed
All under `desktop/` — 25+ files. No existing files outside this directory are touched.

---

## Phase 4: Documentation & Polish

**Goal:** Update READMEs, add desktop-specific usage guide, final review.

### Tasks

| # | Task | Details | Verification |
|---|---|---|---|
| 4.1 | Update `README.md` | Add "Desktop App" section after "Features". Screenshot of the app. Quick install instructions for `.dmg`/`.exe`. Link to architecture doc. | Read through final README |
| 4.2 | Update `README_CN.md` | Same as above, in Chinese | Read through final README_CN |
| 4.3 | Final review | Run all three interfaces (Gradio, FastAPI, Desktop) and verify: same input → same output | All three produce identical depth videos |
| 4.4 | Commit & tag | `feat: add desktop app with Tauri + FastAPI sidecar` + `v2.0.0` tag | Clean git log |

### Files changed
- `README.md`, `README_CN.md`

---

## Dependency graph

```
Phase 0 ──▶ Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4
  (setup)    (core)    (server)    (desktop)    (docs)
```

Phases are strictly sequential — each depends on the previous. Within a phase, tasks with no dependency can be parallelized.

---

## Testing strategy

| Phase | Test type | What |
|---|---|---|
| 1 | Regression | Run Gradio app, process `examples/original.mp4`, compare with pre-refactor output |
| 2 | Integration | `curl` POST to `/api/process`, verify output video plays and matches |
| 3 | E2E | Manual walkthrough: open app → drag video → configure → process → preview → save |
| 4 | Smoke | All three interfaces produce identical output from same input |

### Known test gap

No automated unit tests exist for the current codebase. Adding a pytest suite for `depth_converter/` is a recommended follow-up but out of scope for this plan (we're adding a desktop shell, not introducing the test regime). The regression test in Phase 1 serves as the safety net.

---

## Risk register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Gradio breaks after Phase 1 refactor | Low | High | Phase 1.7 regression test; trivial rollback |
| PyTorch OOM in sidecar (user picks Large on 8GB machine) | Medium | Medium | Frontend warns if model > available RAM; Small is default |
| Python not on user PATH (Windows especially) | High | High | Document in README; Phase 3.1+: bundle `python-build-standalone` in Tauri `externalBin` |
| FFmpeg not installed | Medium | Medium | Detect in `/api/health`; bundle `ffmpeg` binary in Tauri `externalBin` (cross-platform static builds available) |
| Tauri v2 unstable API changes | Low | Medium | Pin exact versions in `Cargo.toml` and `package.json` |
| Model download on first use takes minutes | High | Medium | Show download progress in desktop UI; pre-bundle Small model (95 MB) in the app |
