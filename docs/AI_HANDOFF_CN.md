# DepthuVideoConverter — 跨电脑 AI 交接说明

> 用途：把本地迁移的目标、当前实现、验证结果和边界交给另一台电脑上的 AI。先读本文，再读 `MIGRATION_TO_LOCAL_CN.md`、`README_CN.md` 和 `docs/ARCHITECTURE.md`。

## 1. 项目身份与当前目标

- 项目名称：`DepthuVideoConverter`。
- 当前主目录：`F:\Documents\深度视频控制\DepthVideoConverter`。
- 参考 UI 项目：`F:\Desktop\contour-control-tool`。
- 目标仓库：`https://github.com/ZhaoDesign/DepthuVideoConverter`。
- 当前方向：Windows 本地 PySide6 原生桌面端，直接调用本地 Python/PyTorch 转换核心。

必须保持：

1. 保留参考项目主窗口的两栏结构、尺寸层级、颜色、间距和交互风格，采用小步修复。
2. 不恢复 GitHub 在线队列。
3. 不恢复 Web、FastAPI 在线服务或 Tauri 外壳作为当前入口。
4. 先检查 `git status` 和现有修改；不要用 reset、checkout 或覆盖方式抹掉用户文件。
5. `depth_video_converter.py` 和 `downloads/` 是迁移前已有用户内容，除非用户明确要求，否则只读保留。

## 2. 当前支持的启动路径

日常开发或诊断：

```powershell
venv\Scripts\python.exe desktop_launcher.py
```

Windows 双击入口：

```text
start_desktop.cmd
```

交付前自检：

```powershell
venv\Scripts\python.exe verify_desktop_delivery.py
```

稳定链路是：

```text
desktop_launcher.py -> desktop_qt_app.py -> depth_converter/
```

旧的 `depth_video_converter.py`、`server/`、Docker/Web 相关文件只作为历史兼容路径，不要把它们重新接回桌面入口。

## 3. 当前 UI 行为约定

- 主窗口：无边框、默认约 `1110 × 852`，最小 `900 × 680`；左输入/参数栏，右深度视频/状态栏。两列面板和播放器使用弹性布局，最大化时随窗口扩展，不再固定缩在中间。
- 输入支持拖放和“选择视频”；输出目录默认跟随输入目录，也可以手动选择。
- 模型菜单只显示 Small、Base、Large 三个受支持模型定义；模型文件优先使用项目 `models/` 目录，原生桌面默认使用本地 PyTorch 后端。
- 分辨率支持 Original、480p、720p、1080p，并按输入宽高比计算输出尺寸。
- 输入支持 MP4/MOV 等视频和 PNG/JPG/JPEG/WEBP/BMP/TIFF 图片；图片生成 PNG 深度图，视频生成 H.264 MP4 深度视频。
- 支持黑白反转、时序平滑和保留原声。
- 输出重名时生成带时间戳的 `*_depth_YYYYMMDD-HHMMSS.mp4`，不覆盖旧文件。
- 下拉弹窗优先向下展开；屏幕底部空间不足时才向上展开。模型三项菜单不显示滚动条。
- 鼠标点击“选择视频”后不应留下 Windows 原生焦点虚线框。
- 视频预览最大化必须在原窗口内显示黑色半透明遮罩，不创建新的系统窗口；遮罩内提供播放/暂停、进度、时间、静音和音量控件，并可用关闭按钮或 Esc 退出。
- “打开文件夹”在 Windows 使用 Explorer `/select` 定位并选中生成的输出文件，不启动视频播放器。
- 视频圆角不使用 1-bit `QBitmap` 裁剪；使用抗锯齿角落覆盖层，避免圆角边缘出现颗粒和锯齿。
- 转换期间输入区域、源视频控件和参数控件锁定；成功后恢复并启用“打开视频/打开文件夹”。

## 3.1 与 SwiftSteed/DepthVideoConverter 的功能对齐

上游项目 README 定义的本地转换能力需要保留：

- Small / Base / Large 模型选择与首次使用时下载；当前 PyTorch 模型标签约为 99/392/1300 MB；
- Original / 480p / 720p / 1080p 输出分辨率；
- 黑白反转；
- 0–100 时序平滑；
- 保留或关闭原始音频；
- CLI `depth_video_cli.py` 的输入、输出、模型、分辨率、平滑、反转和无音频参数；
- 本地 FFmpeg 编码、模型缓存和 CPU/CUDA/MPS 设备检测。
- 单张图片深度推理和 PNG 输出。

当前这些功能通过原生界面或 CLI 保留。由于本项目已经明确选择 PySide6 本地路线，上游的 Gradio Web、Docker Web、FastAPI 在线服务、Tauri 和在线队列不作为当前桌面功能恢复；这不是遗漏，而是迁移边界。

## 4. 关键实现和已修复问题

- `depth_converter/ffmpeg.py`：FFmpeg 输出按 bytes 解码，修复音频抽取/合成时的文本解码错误。
- `depth_converter/models.py`：支持 `DEPTH_MODELS_DIR`，并提供模型缓存清理；避免切换模型目录后仍使用旧缓存。
- `desktop_qt_app.py`：从参考项目迁移原生窗口结构；增加稳定启动、字体回退、模型目录同步、输入/输出状态和转换线程修复。
- `desktop_qt_app.py`：主窗口、输入区域、播放器和状态面板改为弹性布局；预览放大改为同窗遮罩层并保留播放状态、进度和音量。
- `desktop_qt_app.py`：输出文件夹使用 Explorer 选中文件；视频圆角改为抗锯齿覆盖层，移除易产生锯齿的位图 mask。
- `desktop_qt_app.py`：支持视频/图片导入，图片自动隐藏音频与播放控件，并按输入类型选择 MP4/PNG 输出。
- `FigmaComboBox`：按屏幕可用区域定位弹窗，关闭不必要的水平/垂直滚动条。
- `MouseFocusClearingButton`：保留键盘焦点能力，同时清除鼠标点击后的虚线焦点框。
- `start_desktop.cmd`：必须使用 Windows CRLF 换行，直接运行 `venv\Scripts\pythonw.exe desktop_launcher.py`。

## 5. 模型、运行时和交付边界

- 当前项目已验证的 Small 模型：`models/depth_anything_v2_vits.pth`。
- Base/Large 的定义保留，但没有为了本次迁移强行下载大模型。
- FFmpeg 必须能在 PATH 中执行；当前环境已验证可用。
- 当前交付形式已包含 Windows x64 Inno Setup 安装器版本 `2026.08.17.1`：联网版为一个 `.exe`，离线 CUDA 版为一个 `.exe` 加两个 `.bin` 分卷；离线三件套必须放在同一目录。
- 当前安装包发布页：`https://github.com/ZhaoDesign/DepthuVideoConverter/releases/tag/v2026.08.17.1`。
- 参考项目的 ONNX/Web/Tauri 打包脚本不适用于当前 PyTorch/PySide6 路线，不要直接复制。

## 6. 已完成验证

执行过并通过：

- `verify_desktop_delivery.py`：必需文件、8 个 Python 文件编译、FFmpeg、Small 模型、PySide6 窗口尺寸和三个模型项。
- 离屏 UI 弹窗检查：模型弹窗位于组合框下方，`ScrollBarAlwaysOff`，滚动条不可见。
- 离屏焦点检查：点击“选择视频”后 `hasFocus()` 为 false。
- 真实 UI 转换：带 AAC 音轨输入，输出 `854 × 480`，H.264 + AAC，进度 100%，重复输出按时间戳命名。
- Windows 批处理启动烟测：CRLF 修复后，`start_desktop.cmd` 可启动 `desktop_launcher.py`。
- Windows 联网安装器和离线分卷安装器均已在隔离目录完成安装烟测；运行时验证通过，安装不要求重启。
- 安装包 SHA256、大小和分卷文件名记录在 `docs/WINDOWS_INSTALLER_HANDOFF.md`，不要只凭文件名判断离线包是否完整。
- 当前 UI 回归：`verify_desktop_delivery.py` 已覆盖默认窗口、最大化/缩小弹性尺寸、同窗预览遮罩及播放控件存在性。

## 7. Git 协作规则

开始任何新工作前：

```powershell
git status --short
git remote -v
```

本次迁移未执行提交前的破坏性回退。推送前必须再次检查：

```powershell
git diff --check
git diff --stat
git status --short
```

目标远程应为：

```text
https://github.com/ZhaoDesign/DepthuVideoConverter.git
```

如果远程认证失败，停止并把错误交给用户，不要把令牌写入文件或命令历史。

## 8. 下一位 AI 的安全工作顺序

1. 阅读本文件、`MIGRATION_TO_LOCAL_CN.md`、`README_CN.md`。
2. 查看 `git status --short`，区分用户已有修改和本次迁移修改。
3. 运行 `venv\Scripts\python.exe verify_desktop_delivery.py`。
4. 若改 UI，先保留参考窗口结构，只修复一个交互问题并做离屏/真实回归。
5. 不启动或恢复 Web/Tauri/在线队列。
6. 推送前执行 `git diff --check`，确认没有临时媒体、缓存、日志和模型大文件被误加入。
