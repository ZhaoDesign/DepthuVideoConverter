# macOS 通用联网安装器

这是给 GitHub Release 用的 macOS 小体积安装方案。

安装包里只放应用代码和安装脚本，不把 Python、PyTorch 和其他大依赖打进 `.app`。
用户双击后，安装器会自动把运行环境下载到本机用户目录，再启动原生桌面界面。

注意：当前仓库里的 macOS 原生 UI 文件只是跟随 Windows 方案做了准备，必须在真实 Mac 上完成构建、启动和短视频转换验证后再发布。

## 适合什么场景

- 想要比原始 `.dmg` / `.zip` 更小的首发包
- 不想让用户先手动装 Python
- 希望安装后直接双击打开，体验更接近普通 macOS 应用

## 运行时会下载什么

- uv 运行时引导工具
- Python 3.11
- PySide6 原生桌面界面
- PyTorch / TorchVision
- OpenCV、NumPy、imageio-ffmpeg

模型文件不进入安装包，首次在界面选择模型时再下载到：

`~/Library/Application Support/DepthVideoConverter/models`

## 运行环境位置

安装器会把运行环境放到：

`~/Library/Application Support/CCT/`

其中包括 Python、uv、缓存和虚拟环境。

## 构建

在 macOS 上运行：

```bash
zsh packaging/build_macos_web_installer.sh /path/to/output
```

输出文件：

- `ContourControlTool-macOS-WebSetup.zip`
- `ContourControlTool-macOS-WebSetup.dmg`

## 客户要求

- macOS
- 首次启动需要联网
- 首次处理视频时需要联网下载所选模型

## 建议发布说明

- 这是 macOS 通用联网安装器
- 首次启动会自动准备 Python 和依赖
- 当前原生 UI 版本需在 Mac 上验证后再发布
- 如果安装失败，请把 `~/Library/Application Support/DepthVideoConverter/installer.log` 发回来
