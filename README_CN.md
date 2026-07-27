<p align="right">
  <a href="README.md">EN</a> | <sub>中文</sub>
</p>

<h1 align="center">Depth Video Converter</h1>

<p align="center">
  使用 <a href="https://github.com/DepthAnything/Depth-Anything-V2">Depth Anything V2</a>
  将任意视频转换为<strong>灰度深度图视频</strong>。
  全程本地运行。
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## 效果演示

[🎬 并排对比](examples/comparison.mp4) — 左：原始视频 | 右：深度图

> 近处偏亮，远处偏暗。使用 **Large** 模型生成。

---

## 快速开始

### CLI（最简单）

```bash
git clone https://github.com/SwiftSteed/DepthVideoConverter.git
cd DepthVideoConverter
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python depth_video_cli.py your-video.mp4 -m "Base (balanced, ~372 MB)"
# 选项：-m (模型), -r (分辨率), -s (平滑), --invert, --no-audio
```

模型首次使用自动下载。

> **Claude Code 用户？** 安装 Skill 后直接说需求：
> `/depth-video` — "把这段视频转成深度视频，用 Large 模型"

### Web UI（Gradio）

```bash
python depth_video_converter.py
# → http://127.0.0.1:7860
```

### Docker

```bash
git clone https://github.com/SwiftSteed/DepthVideoConverter.git
cd DepthVideoConverter
docker compose up
```

浏览器打开 **http://localhost:7860**。无需 Python、ffmpeg，全部在容器内。

> **NVIDIA GPU？** compose 文件自动启用 GPU。
> 需 [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)。
> Apple Silicon / 纯 CPU 也可以，只是慢一些。

---

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| **Model Size** | Small | Small (~95 MB) / Base (~372 MB) / Large (~1.2 GB)。越大质量越好，越慢。 |
| **Output Resolution** | Original | 降分辨率可加速。480p / 720p / 1080p 只表示目标高度，宽度会按上传视频比例自动计算。 |
| **Invert Black & White** | 关闭 | 翻转近远关系。 |
| **Temporal Smoothing** | 60 | 0 = 关闭。100 = 最大（减少闪烁，可能拖影）。 |
| **Preserve Original Audio** | 开启 | 将原始音轨复制到输出。 |

### 模型性能（Apple M4 MPS, 720×1280, 15 秒视频）

| 模型 | 速度 | 15s 视频 | 60s 视频 |
|---|---|---|---|
| **Small** | 5.0 fps | 1.5 分钟 | 6 分钟 |
| **Base** | 2.1 fps | 3.6 分钟 | 14 分钟 |
| **Large** | 0.7 fps | 10.8 分钟 | 43 分钟 |

Base 是推荐之选。CUDA 会比 MPS 快约 2–4 倍。

---

## 许可证

MIT。[Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2) 使用 Apache 2.0。

模型来自 Hugging Face [depth-anything](https://huggingface.co/depth-anything)。
基于 [Gradio](https://www.gradio.app/)、[OpenCV](https://opencv.org/)、[ffmpeg](https://ffmpeg.org/) 构建。
