"""FastAPI sidecar — REST API for the DepthuVideoConverter desktop shell.

Run:  python -m server.main
Port: DEPTH_SERVER_PORT env var (default 9876), bound to 127.0.0.1 only.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from depth_converter import (
    MODEL_DEFS,
    MODELS_DIR,
    detect_device,
    ffmpeg_available,
    normalize_resolution_choice,
    process_video,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DepthuVideoConverter API",
    version="2.0.0",
    docs_url=None,          # No public docs needed
    redoc_url=None,
)

# Only allow the Tauri dev server / built-in WebView to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",   # Tauri dev server
        "tauri://localhost",       # Tauri production WebView
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for running blocking process_video() calls
_executor = ThreadPoolExecutor(max_workers=1)

# In-memory progress store (one task at a time — single user desktop app)
_progress: Dict[str, tuple[float, str]] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file_size_mb(p: Path) -> str:
    if p.is_file():
        return f"{p.stat().st_size / 1e6:.1f} MB"
    return "not downloaded"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> Dict[str, Any]:
    """Return server status, device info, and model availability."""
    device_str, device_desc = detect_device()
    return {
        "status": "ok",
        "version": "2.0.0",
        "device": device_desc,
        "device_type": device_str,
        "ffmpeg": ffmpeg_available(),
    }


@app.get("/api/models")
async def list_models() -> Dict[str, Any]:
    """Return available models with download status."""
    models = {}
    for label, cfg in MODEL_DEFS.items():
        p = cfg["path"]
        models[label] = {
            "downloaded": p.is_file(),
            "size": _file_size_mb(p),
            "encoder": cfg["encoder"],
        }
    return {"models": models}


@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str) -> Dict[str, Any]:
    """Poll processing progress (0.0–1.0 fraction + description string)."""
    entry = _progress.get(task_id)
    if entry is None:
        return {"progress": 0.0, "description": "waiting…"}
    return {"progress": entry[0], "description": entry[1]}


@app.post("/api/process")
async def process(
    input_video: UploadFile = File(...),
    model_size_label: str = Form("Small (fastest, ~95 MB)"),
    resolution_choice: str = Form("Original"),
    invert_bw: bool = Form(False),
    smoothing_strength: float = Form(60),
    preserve_audio: bool = Form(True),
) -> FileResponse:
    """Upload a video and convert it to a depth-map MP4.

    Returns the output .mp4 file as a streaming download.
    """
    # Validate model_size_label
    if model_size_label not in MODEL_DEFS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_size_label}")

    try:
        resolution_choice = normalize_resolution_choice(resolution_choice)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown resolution: {resolution_choice}")

    # Save uploaded video to a temp file
    suffix = Path(input_video.filename or "video.mp4").suffix or ".mp4"
    tmp_input = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        shutil.copyfileobj(input_video.file, tmp_input)
        tmp_input.close()
    except Exception:
        tmp_input.close()
        os.unlink(tmp_input.name)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    task_id = str(uuid.uuid4())[:8]

    def progress_callback(fraction: float, description: str) -> None:
        _progress[task_id] = (fraction, description)

    try:
        loop = __import__("asyncio", fromlist=["asyncio"]).get_running_loop()
        output_path = await loop.run_in_executor(
            _executor,
            process_video,
            tmp_input.name,
            model_size_label,
            resolution_choice,
            invert_bw,
            smoothing_strength,
            preserve_audio,
            progress_callback,
        )

        return FileResponse(
            path=output_path,
            media_type="video/mp4",
            filename="depth_output.mp4",
        )

    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Clean up uploaded temp file
        try:
            os.unlink(tmp_input.name)
        except OSError:
            pass
        # Clean up progress entry
        _progress.pop(task_id, None)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import uvicorn

    port = int(os.environ.get("DEPTH_SERVER_PORT", "9876"))

    print("=" * 58)
    print("  DepthuVideoConverter — FastAPI Sidecar")
    print("=" * 58)
    device_str, device_desc = detect_device()
    print(f"  Detected device : {device_desc}")
    print(f"  ffmpeg          : {'✅ found' if ffmpeg_available() else '❌ NOT FOUND'}")
    print(f"  Listening on    : http://127.0.0.1:{port}")
    print("=" * 58)
    print()

    uvicorn.run(
        "server.main:app",
        host="127.0.0.1",
        port=port,
        reload=False,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
