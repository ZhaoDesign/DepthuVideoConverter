# 桌面版打包

桌面启动器会自动打开本地网页界面。模型不会放入安装包，首次选择模型时下载到用户数据目录：

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

输出 Windows x64 便携版压缩包。用户完整解压后，双击 `Depth Video Converter.exe` 即可启动。
