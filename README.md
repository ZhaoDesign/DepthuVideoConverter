<p align="right">
  <sub>EN</sub> | <a href="README_CN.md">中文</a>
</p>

<h1 align="center">Depth Video Converter</h1>

<p align="center">
  Turn any video into a <strong>grayscale depth-map video</strong> using
  <a href="https://github.com/DepthAnything/Depth-Anything-V2">Depth Anything V2</a>.
  Everything runs locally.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## Demo

[🎬 Side-by-side comparison](examples/comparison.mp4) — Original (left) vs Depth Map (right)

> Near = bright, far = dark. Generated with the **Large** model.

---

## Quick Start

### CLI (simplest)

```bash
git clone https://github.com/SwiftSteed/DepthVideoConverter.git
cd DepthVideoConverter
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python depth_video_cli.py your-video.mp4 -m "Base (balanced, ~372 MB)"
# Options: -m (model), -r (resolution), -s (smoothing), --invert, --no-audio
```

Models auto-download on first use.

> **Claude Code user?** Install the skill and just say what you want:
> `/depth-video` — "convert this video to depth, use Large model"

### Web UI (Gradio)

```bash
python depth_video_converter.py
# → http://127.0.0.1:7860
```

In the desktop package, a small control window stays open so you can reopen the page or quit cleanly. Closing the browser tab/window asks for browser confirmation first. If you confirm leaving, the local background process exits too.

### Docker

```bash
git clone https://github.com/SwiftSteed/DepthVideoConverter.git
cd DepthVideoConverter
docker compose up
```

Open **http://localhost:7860**.  No Python, no ffmpeg — everything inside the container.

> **NVIDIA GPU?** The compose file enables GPU automatically.
> Requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
> Apple Silicon / CPU-only works too, just slower.

---

## Controls

| Control | Default | What it does |
|---|---|---|
| **Model Size** | Small | Small (~95 MB) / Base (~372 MB) / Large (~1.2 GB). Larger = better quality, slower. |
| **Output Resolution** | Original | Downscale to speed up processing. 480p / 720p / 1080p set target height only; width follows the uploaded video's aspect ratio. |
| **Invert Black & White** | Off | Swap near ↔ far. |
| **Temporal Smoothing** | 60 | 0 = off. 100 = max (less flicker, possible ghosting). |
| **Preserve Original Audio** | On | Copy the original audio track into output. |

### Model performance (Apple M4 MPS, 720×1280, 15s clip)

| Model | Speed | 15s clip | 60s clip |
|---|---|---|---|
| **Small** | 5.0 fps | 1.5 min | 6 min |
| **Base** | 2.1 fps | 3.6 min | 14 min |
| **Large** | 0.7 fps | 10.8 min | 43 min |

Base is the sweet spot. CUDA is ~2–4× faster depending on GPU.

---

## License

MIT. [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2) is Apache 2.0.

Models from [depth-anything](https://huggingface.co/depth-anything) on Hugging Face.
Built with [Gradio](https://www.gradio.app/), [OpenCV](https://opencv.org/), [ffmpeg](https://ffmpeg.org/).
