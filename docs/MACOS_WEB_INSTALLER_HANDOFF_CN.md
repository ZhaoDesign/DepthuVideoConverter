# macOS 联网安装器交接文档

这份文档记录本次参考 Windows 联网安装器后，对 macOS 发布方式做的优化。另一台电脑拉取项目后，可以按这里继续构建、验证和排查。

## 这次解决的问题

原来的 macOS 包通过 PyInstaller 把运行环境直接打进 `.app`，发布包大约 200MB 以上。Windows 端已经改成“小安装器 + 安装时下载运行环境”的方式，所以 macOS 也新增了同类方案：

- 发布包只包含 App 启动器、项目代码和安装脚本。
- 首次打开 App 时自动下载 `uv`、Python 3.11 和运行依赖。
- 模型文件仍然不放进安装包，首次选择模型时再下载。
- 安装失败时把日志写到用户目录，方便同事发回排查。

## 新增文件

- `packaging/build_macos_web_installer.sh`
  - 构建 macOS 小体积联网安装包。
  - 输出 `DepthuVideoConverter-macOS-WebSetup.zip` 和 `DepthuVideoConverter-macOS-WebSetup.dmg`。

- `packaging/macos-web-installer/launch_runtime.sh`
  - App 双击后的真正入口。
  - 检查并下载 `uv`。
  - 创建 Python 3.11 虚拟环境。
  - 安装锁定版本的运行依赖。
  - 跑安装后自检，通过后启动 `desktop_launcher.py`。

- `packaging/macos-web-installer/runtime-requirements-macos.txt`
  - macOS 联网安装器专用依赖锁定文件。
  - 固定了 `gradio`、`fastapi`、`starlette`、`torch`、`torchvision`、`opencv-python`、`numpy`、`pyobjc` 等版本，减少依赖漂移导致本地页面打不开的风险。

- `packaging/macos-web-installer/verify_runtime.py`
  - 安装后自检脚本。
  - 会导入关键依赖，并调用 `create_ui()` 确认网页界面可以创建。

- `packaging/macos-web-installer/README_CN.md`
  - 面向发布/使用的中文说明。

- `docs/MACOS_WEB_INSTALLER_HANDOFF.md`
  - 英文版交接说明。

## 修改文件

- `README.md`
- `README_CN.md`
- `packaging/README_CN.md`

这些文件新增了 macOS 联网安装器的下载名称、构建命令和使用说明。

## 运行环境位置

macOS 联网安装器会把运行环境安装到用户目录：

```text
~/Library/Application Support/CCT/
```

主要结构：

```text
tools/      uv 启动工具
python/     uv 管理的 Python
rt311mac/   本工具的 Python 虚拟环境
cache/      下载缓存
```

模型文件仍然放在：

```text
~/Library/Application Support/DepthuVideoConverter/models
```

安装日志在：

```text
~/Library/Application Support/DepthuVideoConverter/installer.log
```

## 构建方式

在 macOS 上，从项目根目录运行：

```bash
APP_VERSION=2026.07.31.2 zsh packaging/build_macos_web_installer.sh /Users/xmiles/Documents/深度视频转化项目
```

输出文件：

```text
/Users/xmiles/Documents/深度视频转化项目/DepthuVideoConverter-macOS-WebSetup.zip
/Users/xmiles/Documents/深度视频转化项目/DepthuVideoConverter-macOS-WebSetup.dmg
```

## 验证方式

1. 检查 ZIP：

```bash
unzip -tq /Users/xmiles/Documents/深度视频转化项目/DepthuVideoConverter-macOS-WebSetup.zip
```

2. 检查 DMG：

```bash
hdiutil verify /Users/xmiles/Documents/深度视频转化项目/DepthuVideoConverter-macOS-WebSetup.dmg
```

3. 检查 DMG 里的 App 结构：

```bash
hdiutil attach /Users/xmiles/Documents/深度视频转化项目/DepthuVideoConverter-macOS-WebSetup.dmg -nobrowse
CCT_MACOS_INSTALLER_SELF_TEST=1 "/Volumes/DepthuVideoConverter/DepthuVideoConverter.app/Contents/MacOS/DepthuVideoConverter"
hdiutil detach "/Volumes/DepthuVideoConverter"
```

4. 检查首次启动安装流程，但不真正打开网页：

```bash
CCT_RUNTIME_ROOT=/tmp/cct-mac-web-runtime-test \
CCT_DATA_DIR=/tmp/cct-mac-web-data-test \
CCT_MACOS_INSTALL_RUNTIME_ONLY=1 \
build/macos-web-installer/stage/DepthuVideoConverter.app/Contents/MacOS/DepthuVideoConverter
```

成功时日志里会出现：

```text
"ok": true
Runtime installation completed.
Runtime-only verification completed.
```

## 本次已验证结果

- ZIP 完整性检查通过。
- DMG 校验通过。
- 从 DMG 挂载后的 App 自检通过。
- 干净临时目录首次启动安装流程通过。
- 安装后依赖导入和 `create_ui()` 自检通过。
- 最终包大小约 300KB。

## 注意事项

- 首次启动需要联网。
- 首次选择模型时还需要联网下载 Depth Anything V2 模型。
- 这个包没有做 Apple Developer ID 公证，公开给陌生用户下载时，macOS 可能仍会提示安全确认。
- 这是新增的轻量发布方式，不替代原来的离线 PyInstaller `.dmg`；原离线构建脚本 `packaging/build_macos.sh` 仍保留。
