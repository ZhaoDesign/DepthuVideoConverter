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

[<video src="examples/comparison.mp4" controls width="100%"></video>](https://github.com/user-attachments/assets/aa83ef7f-7435-4c6f-a8fb-eb3f1509b9f7
)

左：原始视频 | 右：深度图

> 近处偏亮，远处偏暗。使用 **Large** 模型生成。

---

## 快速开始

### 原生桌面端（当前主入口）

```bash
python desktop_launcher.py
```

Windows 虚拟环境：

```powershell
.\venv\Scripts\python.exe desktop_launcher.py
```

也可以直接双击项目目录中的 `start_desktop.cmd`。

这是当前迁移后的主界面：使用 PySide6 原生窗口，直接调用本地转换核心，不启动在线队列、Web 服务或 Tauri。支持拖入视频或图片、预览、选择模型/分辨率、时序平滑、保留音频，并将结果保存到本地文件夹。图片会生成 PNG 深度图，视频会生成 H.264 MP4 深度视频。

### CLI（最简单）

```bash
git clone https://github.com/ZhaoDesign/DepthuVideoConverter.git
cd DepthVideoConverter
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python depth_video_cli.py your-video.mp4 -m "Base (balanced, ~392 MB)"
# 也支持单张 PNG/JPG/WEBP 图片；选项：-m, -r, -s, --invert, --no-audio
```

模型首次使用自动下载。

> **Claude Code 用户？** 安装 Skill 后直接说需求：
> `/depth-video` — "把这段视频转成深度视频，用 Large 模型"

### 历史 Web UI（不作为当前桌面入口）

```bash
python depth_video_converter.py
# → http://127.0.0.1:7860
```

`desktop_qt_app.py` 是桌面窗口实现文件；日常启动请使用上面的 `desktop_launcher.py`。

### 历史 Docker/Web 运行方式

```bash
git clone https://github.com/ZhaoDesign/DepthuVideoConverter.git
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
| **Output Resolution** | Original | 降分辨率可加速（480p / 720p / 1080p）。 |
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
当前原生桌面端基于 [PySide6](https://doc.qt.io/qtforpython/)、[OpenCV](https://opencv.org/)、[FFmpeg](https://ffmpeg.org/) 和 PyTorch 构建。Gradio/FastAPI 依赖仅为历史兼容路径保留，不属于当前桌面入口。
