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

- 本项目目前验证的是“项目目录 + venv”本地交付，尚未生成 PyInstaller/Inno Setup 安装包。
- 参考项目中的 Web/ONNX/Tauri 打包脚本不适用于当前 PyTorch/PySide6 路线，因此不复制、不恢复。
- 正式安装器需要在后续明确 Python、PyTorch、模型和 FFmpeg 的打包方式后单独设计。
