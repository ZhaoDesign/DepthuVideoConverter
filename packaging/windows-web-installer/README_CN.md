# Windows x64 小体积联网安装器

这个方案用于公开 GitHub Release 的第一版 Windows 客户测试包。

安装器本身只包含应用代码和安装脚本。用户双击安装器后可以选择应用安装位置，安装器会联网下载：

- Python 3.11 embeddable runtime
- 已锁版本的 Gradio / FastAPI / Starlette
- CPU 版 PyTorch / TorchVision
- OpenCV headless、NumPy、imageio-ffmpeg 等运行依赖

模型文件不进入安装包，首次在界面选择模型时再下载到：

`%LOCALAPPDATA%\DepthVideoConverter\models`

为避免 Windows 默认未开启长路径时 PyTorch 安装失败，Python 运行时和大依赖固定安装到较短的用户目录：

`%LOCALAPPDATA%\CCT\rt311cpu`

## 为什么这样做

原便携包把完整 PyTorch 运行库打进压缩包，解压后 `Lib` 目录约 1.76GB，其中 `torch` 约 1.2GB。小体积安装器避免内置这些大文件，同时锁定依赖版本，减少客户电脑上出现 Gradio / Starlette 不兼容导致无法打开本地页面的问题。

## 构建

在 Windows 64 位电脑上安装 Inno Setup 6，然后运行：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_web_installer.ps1 -AppVersion 0.1.0
```

输出文件：

`dist\windows-installer\ContourControlTool-Windows-x64-WebSetup.exe`

## 客户使用要求

- Windows 64 位
- 安装时需要联网
- 首次处理视频时需要联网下载所选 Depth Anything V2 模型
- 开始菜单默认包含卸载快捷方式，安装时也可以勾选桌面卸载快捷方式

## 发布建议

GitHub Release 第一版建议上传这个小体积安装器，并在说明里明确：

- 这是 Windows x64 联网安装器
- 默认 CPU 运行，兼容性优先，速度会比 GPU 版慢
- 如果安装失败，请提供 `%LOCALAPPDATA%\DepthVideoConverter\installer.log`
