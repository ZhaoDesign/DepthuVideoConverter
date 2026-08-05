# Contour Control Tool｜视频深度控制图工具

一个本地运行的视频深度控制图生成工具。它使用 [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2) 把普通 MP4 / MOV 视频转换成灰度深度视频，可用于 AI 视频生成、ComfyUI 工作流、Seedance / 即梦等视频工具的运动参考、空间结构参考或轮廓控制素材。

近处通常更亮，远处更暗；也可以一键黑白反转。所有处理都在本机完成，视频不会上传到外部服务器。

## 主要功能

- 支持 MP4 / MOV 上传，生成 H.264 MP4 深度视频。
- 支持 Small / Base / Large 三档 Depth Anything V2 模型。
- 自动识别 NVIDIA CUDA、Apple Silicon MPS 或 CPU。
- 支持原始分辨率、480p、720p、1080p 输出。
- 480p / 720p / 1080p 只表示目标高度，宽度会按原视频比例自动计算，不会压扁画面。
- 支持时序平滑，减少深度视频闪烁。
- 支持保留原视频音频。
- Windows x64 安装器提供原生桌面应用窗口，不需要从浏览器打开。
- 安装器会创建桌面和开始菜单的启动/卸载快捷方式。

## 下载安装

请到 GitHub Releases 下载对应系统的安装包：

- macOS Apple Silicon：`DepthVideoConverter-macOS-AppleSilicon.dmg`
- macOS ZIP：`DepthVideoConverter-macOS-AppleSilicon.zip`
- macOS 通用联网安装器：`ContourControlTool-macOS-WebSetup.dmg`
- Windows x64 原生桌面安装器：`ContourControlTool-Windows-x64-WebSetup.exe`

Windows 用户双击 `.exe` 安装器，按向导选择安装位置即可。首次安装需要联网下载 Python / PyTorch / PySide6 等运行环境；首次使用模型时还会下载对应的 Depth Anything V2 权重。

macOS 联网安装器首次启动会自动下载运行环境，更适合想要小体积发布包的场景。macOS 原生 UI 版本需要在 Mac 上单独构建和验证后发布。

## 推荐模型

| 模型 | 适合场景 | 说明 |
|---|---|---|
| Small | 快速预览、批量测试 | 速度最快，质量一般 |
| Base | 日常推荐 | 质量和速度最均衡 |
| Large | 最终输出、复杂画面 | 深度细节更好，但更慢、模型更大 |

如果是 15 秒左右的视频，建议优先用 **Base**。如果只是想快速看效果，用 **Small**。画面空间关系复杂、人物遮挡多、需要更稳定的控制素材时，再用 **Large**。

## 桌面版使用

1. 打开应用。
2. 拖入视频，或点击选择视频。
3. 选择模型、输出分辨率和平滑参数。
4. 选择输出文件夹。
5. 点击开始转换。
6. 完成后点击打开视频或打开文件夹。

Windows 安装器会创建桌面和开始菜单启动快捷方式；卸载请使用 Windows“设置 > 应用”或控制面板。

## 本地源码运行

```bash
git clone https://github.com/ZhaoDesign/contour-control-tool.git
cd contour-control-tool
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python desktop_qt_app.py
```

如果只想运行旧的本地网页界面，也可以运行：

```bash
python depth_video_converter.py
```

## 命令行使用

```bash
python depth_video_cli.py your-video.mp4 -m "Base (balanced, ~372 MB)"
```

常用参数：

```bash
python depth_video_cli.py input.mp4 \
  -o output-depth.mp4 \
  -m "Base (balanced, ~372 MB)" \
  -r 720p \
  -s 60
```

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| 模型大小 | Small | Small / Base / Large，越大质量越高、速度越慢 |
| 输出分辨率 | Original | Original 保持原尺寸；480p / 720p / 1080p 按原比例缩放到目标高度 |
| 黑白反转 | 关闭 | 交换远近区域明暗 |
| 时序平滑 | 60 | 数值越高闪烁越少，但可能有拖影 |
| 保留原始音频 | 开启 | 将原视频音轨合并到输出视频 |

## 打包

macOS Apple Silicon：

```bash
zsh packaging/build_macos.sh /Users/xmiles/Documents/深度视频转化项目
```

macOS 通用联网安装器：

```bash
zsh packaging/build_macos_web_installer.sh /Users/xmiles/Documents/深度视频转化项目
```

macOS 联网安装器的修改说明和验证步骤见 `docs/MACOS_WEB_INSTALLER_HANDOFF_CN.md`。macOS 原生 UI 文件已经准备，但需要在 Mac 上验证后再发布。

Windows x64 原生桌面安装器：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_web_installer.ps1 -AppVersion 0.2.0
```

Windows 安装器的修改说明和验证步骤见 `docs/WINDOWS_INSTALLER_HANDOFF.md`。

## 说明

本项目是本地工具，不包含模型权重。首次选择模型时会自动从 Hugging Face 下载 Depth Anything V2 权重。

模型来自 Hugging Face [depth-anything](https://huggingface.co/depth-anything)。  
Depth Anything V2 使用 Apache 2.0 License，本工具代码使用 MIT License。
