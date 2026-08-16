# Git 变更审计（2026-08-17）

## 用户已有内容

以下内容在本次本地迁移工作开始前已存在，必须保留：

- `depth_video_converter.py`
- `downloads/`

本次工作没有执行 `git reset`、`git checkout`、强制覆盖或自动提交。

## 本次迁移与修复内容

- `desktop_qt_app.py`：参考项目主窗口迁移、PySide6 原生交互、模型/输出/转换状态修复、下拉弹窗定位、焦点框修复、播放器圆角/关闭/窗口内放大。
- `desktop_launcher.py`：稳定原生桌面入口。
- `start_desktop.cmd`：Windows 双击启动入口，使用 CRLF 换行。
- `assets/`：参考项目 UI 所需图标资源。
- `verify_desktop_delivery.py`：交付自检脚本。
- `docs/AI_HANDOFF_CN.md`：跨电脑 AI 交接说明。
- `docs/DELIVERY_CHECKLIST_CN.md`：交付边界与自检说明。
- `depth_converter/ffmpeg.py`：音频 FFmpeg 输出解码修复。
- `depth_converter/models.py`：模型目录和缓存修复。
- `depth_converter/__init__.py`、`README.md`、`README_CN.md`、`requirements.txt`、`docs/ARCHITECTURE.md`、`docs/DEV_PLAN.md`：明确当前原生桌面方向，保留历史 Web/Tauri 记录但不恢复。

## 推送前检查

```powershell
venv\Scripts\python.exe verify_desktop_delivery.py
git diff --check
git status --short
git diff --stat
```

临时验证目录 `ui-regression-artifacts/` 和 `ui-check-player.png` 不属于交付内容，推送前必须删除并再次检查状态。

## 远程仓库

目标地址：`https://github.com/ZhaoDesign/DepthuVideoConverter.git`。

推送需要用户/环境已配置 GitHub 认证；认证失败时只报告失败原因，不保存令牌。
