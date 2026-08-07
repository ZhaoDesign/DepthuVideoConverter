# Windows x64 原生桌面安装器

这个目录用于构建公开 GitHub Release 的 Windows 64 位客户安装包。

安装包本身只包含应用代码、图标和安装脚本。用户双击安装后，可以选择安装位置；安装器会在后台联网准备 Python / PyTorch / PySide6 等运行环境，不会打开浏览器，也不会弹出 PowerShell 命令窗口。

## 用户安装后的效果

- 桌面快捷方式：`DepthuVideoConverter`
- 开始菜单快捷方式：`DepthuVideoConverter`
- 卸载入口：Windows“设置 > 应用”或控制面板
- 启动后是 PySide6 原生桌面窗口，不再是 Gradio 浏览器页面

## 运行时位置

应用文件安装到用户在向导里选择的位置。默认位置：

```text
%LOCALAPPDATA%\Programs\DepthuVideoConverter
```

Python 和大依赖固定安装到较短的用户目录，避免 PyTorch 在 Windows 默认长路径限制下失败：

```text
%LOCALAPPDATA%\CCT\rt311cpu
```

Depth Anything V2 模型文件不进入安装包，首次使用对应模型时下载到：

```text
%LOCALAPPDATA%\DepthuVideoConverter\models
```

## 构建

先安装 Inno Setup 6，然后在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_web_installer.ps1 -AppVersion 0.2.0
```

输出文件：

```text
dist\windows-installer\DepthuVideoConverter-Windows-x64-WebSetup.exe
```

## 验证重点

建议在干净 Windows 64 位电脑或虚拟机上测试：

1. 双击安装包，确认是正常安装向导。
2. 选择一个带空格的安装目录，例如 `E:\DepthuVideoConverter Native Test`。
3. 等待运行环境下载和安装完成。
4. 确认安装完成后不要求重启。
5. 确认桌面和开始菜单都有启动/卸载快捷方式。
6. 双击启动，确认打开的是原生窗口，不是浏览器。
7. 处理一个短视频，确认输出 MP4 正常生成。
8. 使用卸载快捷方式卸载。

如果安装失败，让客户提供：

```text
%LOCALAPPDATA%\DepthuVideoConverter\installer.log
```

## 当前方案取舍

- 安装包体积小，适合上传 GitHub Release 和发给客户。
- 首次安装必须联网，下载量主要来自 PyTorch、MKL、PySide6、OpenCV 和内置 FFmpeg。
- 默认是 CPU 运行时，兼容性优先，速度会比 GPU 版本慢。
- macOS 相关文件已按原生 UI 方向准备，但需要在 Mac 上单独构建和验证后再发布。
