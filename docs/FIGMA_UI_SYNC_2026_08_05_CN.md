# Figma UI 同步记录 2026-08-05

## 目标

将桌面版主界面尽量还原到 Figma 文件 `深度视频转化` 的界面状态，覆盖主窗口、菜单、下拉弹窗、图标、悬浮按钮、圆角和边距。

## 本次修改

- `desktop_qt_app.py`
  - 新增 `FigmaComboBox`，固定模型/分辨率下拉弹窗位置和高度。
  - 下拉项改为自绘选中态，使用 Figma 导出的深色勾选图标。
  - 顶部菜单弹出位置改为设计稿里的偏移，菜单项高度改为 25px。
  - 全屏悬浮按钮改为 24px，使用 Figma 导出的白色全屏图标。
  - 播放、暂停、音量、文件夹等按钮统一按 16px 图标绘制。
  - macOS 默认字体改为 `PingFang SC`，避免使用 Windows 字体导致渲染偏差。

- `assets/`
  - 从 Figma 导出并替换：`icon-play.png`、`icon-pause.png`、`icon-volume.png`、`icon-folder.png`、`icon-chevron-down.png`、`checkmark.png`。
  - 新增：`icon-check-dark.png`、`icon-chevron-right.png`、`icon-fullscreen.png`。
  - `icon-volume-muted.png` 使用 Figma 音量图标派生，保持同一视觉风格。

- `packaging/windows-web-installer/DepthuVideoConverterSetup.iss`
- `packaging/windows-offline-installer/DepthuVideoConverterSetup.iss`
  - 补齐新增图标资产，确保 Windows 安装包也能显示完整 UI。

## 验证

已完成：

- `desktop_qt_app.py` 语法检查。
- macOS 临时 Qt 环境启动主窗口。
- 主空状态截图验证。
- 加载视频状态截图验证。
- 模型下拉弹窗部件截图验证：403×124。
- 分辨率下拉弹窗部件截图验证：447×164。

离屏截图中系统级弹窗可能存在置顶限制，因此菜单/下拉最终以部件尺寸和单独部件截图为准。

## 重新打包

macOS WebSetup 安装包使用：

```bash
cd /Users/xmiles/Desktop/DepthuVideoConverter
zsh packaging/build_macos_web_installer.sh
```

输出目录通常在：

```text
/Users/xmiles/Documents/深度视频转化项目/
```

主要输出文件：

- `DepthuVideoConverter-macOS-WebSetup.dmg`
- `DepthuVideoConverter-macOS-WebSetup.zip`
