@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\pythonw.exe" goto :missing_python

venv\Scripts\pythonw.exe desktop_launcher.py
exit /b 0

:missing_python
echo 未找到项目虚拟环境：venv\Scripts\pythonw.exe
echo 请先创建 venv 并安装 requirements.txt。
pause
exit /b 1
