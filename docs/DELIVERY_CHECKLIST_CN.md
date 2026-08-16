# 本地桌面交付自检

当前交付对象是 PySide6 原生桌面端，不包含在线队列、Web 服务或 Tauri 外壳。

当前本地功能包含视频深度转换、单张图片深度图、模型自动下载、按比例分辨率、黑白反转、时序平滑、视频音频保留、CLI 和 CPU/CUDA/MPS 设备检测。

## 自检命令

在项目虚拟环境中执行：

```powershell
python verify_desktop_delivery.py
```

自检覆盖：

- 稳定启动入口、图标、Small 模型和目录结构；
- Python 源文件编译；
- FFmpeg 可用、模型菜单和分辨率预设；
- PySide6 无障碍离屏实例化、窗口尺寸和三个模型菜单项；
- `start_desktop.cmd` 是否指向 `venv\\Scripts\\pythonw.exe desktop_launcher.py`。

## 当前分发边界

- 已生成 Windows x64 Inno Setup 安装包版本 `2026.08.17.1`，并准备发布到 GitHub Release：
  - `DepthuVideoConverter-Windows-x64-WebSetup.exe`：小体积联网安装器，安装时联网准备运行环境；
  - `DepthuVideoConverter-Windows-x64-OfflineSetup.exe`；
  - `DepthuVideoConverter-Windows-x64-OfflineSetup-1.bin`；
  - `DepthuVideoConverter-Windows-x64-OfflineSetup-2.bin`：离线版的主程序和两个分卷，必须放在同一目录。
- 联网安装器已在隔离目录完成静默安装，运行时验证、原生桌面入口导入和 Python 编译均通过。
- 离线安装器已在分卷所在目录完成静默安装，安装日志显示成功且无需重启；Small/Base 模型文件和桌面入口均已落地。
- 运行时验证通过：PySide6 6.7.3、PyTorch 2.13.0+cu126、CUDA 12.6、OpenCV 4.10.0、ONNX Runtime 1.18.1、FFmpeg，以及本机 NVIDIA GPU 检测。
- 参考项目中的 Web/ONNX/Tauri 打包脚本不适用于当前 PyTorch/PySide6 路线，因此不复制、不恢复。
- 发布页：<https://github.com/ZhaoDesign/DepthuVideoConverter/releases/tag/v2026.08.17.1>
