# DepthuVideoConverter打包说明

当前推荐给客户发布的是 Windows x64 原生桌面安装器：

```text
DepthuVideoConverter-Windows-x64-WebSetup.exe
```

当前构建版本：`2026.08.17.1`。已完成联网版和 CUDA 离线版构建，并发布到 [GitHub Release](https://github.com/ZhaoDesign/DepthuVideoConverter/releases/tag/v2026.08.17.1)。

联网版是小体积安装器：安装包只放应用代码、图标和安装脚本，首次安装时下载 Python、CUDA PyTorch、PySide6、OpenCV 和 FFmpeg 运行环境。模型文件也不进入联网包，首次选择 Base/Large 模型时下载到用户数据目录。

同时提供 CUDA 离线版：

```text
DepthuVideoConverter-Windows-x64-OfflineSetup.exe
DepthuVideoConverter-Windows-x64-OfflineSetup-1.bin
DepthuVideoConverter-Windows-x64-OfflineSetup-2.bin
```

离线版包含 CUDA 运行时、Small 模型和 Base 模型。三个文件必须放在同一目录，再运行主 `.exe`。

模型缓存位置：

- Windows：`%LOCALAPPDATA%\DepthuVideoConverter\models`
- macOS：`~/Library/Application Support/DepthuVideoConverter/models`

## Windows x64 原生桌面安装器

先在 Windows 上安装 Inno Setup 6，然后运行：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_web_installer.ps1 -AppVersion 2026.08.17.1
```

输出：

```text
dist\windows-installer\DepthuVideoConverter-Windows-x64-WebSetup.exe
```

离线版构建命令：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_offline_installer.ps1 -AppVersion 2026.08.17.1
```

安装后的客户体验：

- 正常安装向导，可选择安装位置。
- 后台安装运行环境，不显示 PowerShell 窗口。
- 启动后是 PySide6 原生桌面窗口，不需要浏览器。
- 桌面和开始菜单都有启动快捷方式。
- 不创建桌面或开始菜单卸载快捷方式；卸载使用 Windows“设置 > 应用”或控制面板。
- 安装完成后不要求重启。

详细交接和验证记录见：

```text
docs/WINDOWS_INSTALLER_HANDOFF.md
```

## macOS

macOS 相关脚本已按原生 UI 方向做准备，但必须在 Mac 上构建、启动、转换短视频验证后再发布。

macOS 联网安装器构建命令：

```bash
zsh packaging/build_macos_web_installer.sh /path/to/output
```

旧的 macOS Apple Silicon PyInstaller 包仍可构建：

```bash
zsh packaging/build_macos.sh /path/to/output
```

## 旧 Windows 便携包

旧便携包脚本还保留在仓库中，但当前不再作为客户首选发布方式：

```bash
venv/bin/python packaging/build_windows_portable.py --output-dir /path/to/output
```

便携包会把运行环境直接打进压缩包，体积明显更大。
