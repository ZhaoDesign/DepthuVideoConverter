# 视频深度控制图工具桌面版打包

桌面启动器会自动打开本地网页界面，并保留一个小控制窗口，方便重新打开网页或彻底退出。macOS 版使用原生窗口，Windows 版使用简洁控制窗。关闭浏览器标签页/窗口并确认离开后，本地后台也会一起退出。模型不会放入安装包，首次选择模型时下载到用户数据目录：

- macOS：`~/Library/Application Support/DepthVideoConverter/models`
- Windows：`%LOCALAPPDATA%\DepthVideoConverter\models`

## macOS Apple Silicon

```bash
zsh packaging/build_macos.sh /path/to/output
```

输出 `.app` 压缩包和 `.dmg`。当前脚本使用本机架构构建，因此在 Apple Silicon Mac 上生成 ARM64 应用。

## Windows x64

先安装交叉编译器：

```bash
brew install mingw-w64
```

然后运行：

```bash
venv/bin/python packaging/build_windows_portable.py --output-dir /path/to/output
```

输出 Windows x64 便携版压缩包。用户完整解压后，双击 `Depth Video Converter.exe` 即可启动。便携包会内置常用 VC++ 运行库，减少 `c10.dll` / `MSVCP140.dll` 启动报错。
