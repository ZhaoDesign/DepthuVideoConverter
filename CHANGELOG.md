# Changelog

## Unreleased

### UI 播放器与控件优化
- 输入视频和输出视频播放器改为 Qt Multimedia，支持原视频声音播放。
- 两个播放器都新增独立静音按钮和音量滑块。
- 运行依赖恢复 `PySide6-Addons`，用于提供 `QtMultimedia` / `QtMultimediaWidgets`。
- 统一播放、暂停、音量、静音、模型目录和下拉箭头图标规格。
- 模型和分辨率下拉框改为自绘圆角选中态，优化弹层间距和悬停效果。
- 模型目录按钮改为自定义圆角提示浮层，统一边框和阴影。
- 安装器自检新增 `QtMultimedia` / `QtMultimediaWidgets` 导入检查，避免打包后缺少音视频模块。

## v0.2.0 (2026-08-03)

### 架构优化
- **PyTorch → ONNX Runtime**：推理后端替换，运行时依赖从 ~422MB 降至 ~155MB（减少 63%）
- **去掉 PySide6-Addons**：只保留 PySide6-Essentials，减少 ~118MB
- **去掉 torchvision**：内联 Compose 类，减少 ~80MB
- **依赖数量**：从 21 个减至 6 个

### 离线安装包
- 安装包内置完整 Python 运行环境 + 所有依赖 + Small ONNX 模型
- 安装时完全不需要联网
- 安装包大小：231 MB（LZMA2 fast 压缩，安装速度快）

### UI 改版
- 白色 Codex 风格主题（纯白底 + 浅灰面板）
- 按钮/进度条/滑块强调色改为黑色（#111827）
- 顶部菜单栏（文件/设置/帮助）
- 右侧面板集成视频播放器（播放/暂停/进度条拖动）
- 源视频/深度视频切换预览
- 模型下拉框旁增加📂按钮，快速打开模型目录
- 下拉列表样式优化

### 模型下载改进
- 默认使用 hf-mirror.com 国内镜像
- 增加 ghproxy 备用镜像
- 下载超时设置（默认 60s）
- 更好的错误提示

### 修复
- 修复 PytorchStreamReader 报错（模型文件损坏检测 + 自动重下载）
- 修复下载进度条卡在 0% 的问题

## 文件改动清单

| 文件 | 改动说明 |
|------|----------|
| `desktop_qt_app.py` | 白色主题 QSS、视频播放器组件（OpenCV+QLabel+QTimer）、菜单栏、模型目录按钮、黑色强调色 |
| `depth_converter/models.py` | 完全重写：PyTorch→ONNX Runtime 推理、preprocess_image()、infer_depth()、镜像下载、超时处理 |
| `depth_converter/core.py` | 移除 torch 引用，改用 infer_depth() |
| `depth_converter/__init__.py` | 导出 infer_depth、MODELS_DIR |
| `requirements.txt` | torch→onnxruntime, PySide6→PySide6-Essentials |
| `packaging/windows-offline-installer/ContourControlToolSetup.iss` | 新增离线安装包 Inno Setup 脚本 |
| `packaging/build_windows_offline_installer.ps1` | 新增离线构建脚本（下载Python+pip install+ISCC编译） |
| `packaging/windows-web-installer/runtime-requirements-cpu.txt` | 精简到 6 个依赖（原 21 个） |
| `packaging/generate_icon.py` | 图标强调色 + 安装向导品牌图片生成 |
| `export_onnx.py` | 新增 ONNX 导出工具（开发用，运行时不需要） |
| `depth_anything_v2/dpt.py` | 内联 Compose 类替代 torchvision 导入 |

## 安装说明
1. 下载 `ContourControlTool-Windows-x64-OfflineSetup.exe`
2. 双击运行，按提示安装（无需联网，无需管理员权限）
3. 安装完成后从桌面快捷方式启动
4. 首次使用直接拖入视频即可转换（Small 模型已内置）
5. 如需更大模型（Base/Large），点击模型下拉框旁📂按钮打开模型目录，手动放入 .onnx 文件

## 技术细节

### ONNX 模型来源
- Small: `onnx-community/depth-anything-v2-small` (58 MB)
- Base: `onnx-community/depth-anything-v2-base` (392 MB)
- Large: `onnx-community/depth-anything-v2-large` (1.3 GB)

### 视频播放器实现
使用 OpenCV VideoCapture + QLabel + QTimer，无需额外多媒体依赖：
- `cv2.VideoCapture` 打开视频
- `QTimer` 按视频 FPS 触发帧渲染
- BGR→RGB→QImage→QPixmap→QLabel.setPixmap()
- QSlider 绑定帧位置跳转
