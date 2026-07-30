#!/usr/bin/env python3
"""Build a self-contained Windows x64 portable package from macOS or Linux."""

from __future__ import annotations

import argparse
import fnmatch
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PYTHON_VERSION = "3.11.9"
PYTHON_ZIP_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/"
    f"python-{PYTHON_VERSION}-embed-amd64.zip"
)
PACKAGE_NAME = "DepthVideoConverter-Windows-x64"


def _run(command: list[str], cwd: Path | None = None) -> None:
    print(" ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def _download(url: str, destination: Path) -> None:
    if destination.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, destination)


def _copy_app(package_dir: Path) -> None:
    app_dir = package_dir / "app"
    app_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "desktop_launcher.py", app_dir)
    shutil.copy2(ROOT / "depth_video_converter.py", app_dir)
    shutil.copytree(ROOT / "depth_converter", app_dir / "depth_converter", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(
        ROOT / "depth_anything_v2",
        app_dir / "depth_anything_v2",
        ignore=shutil.ignore_patterns("__pycache__"),
    )


def _copy_windows_runtime_dlls(package_dir: Path) -> None:
    site_packages = package_dir / "Lib" / "site-packages"
    patterns = (
        "concrt*.dll",
        "msvcp*.dll",
        "vcamp*.dll",
        "vccorlib*.dll",
        "vcomp*.dll",
        "vcruntime*.dll",
    )
    copied: set[str] = set()

    for source_dir in (site_packages, site_packages / "Scripts"):
        if not source_dir.is_dir():
            continue
        for path in source_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name.lower()
            if not any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
                continue
            shutil.copy2(path, package_dir / path.name)
            copied.add(path.name)

    if "msvcp140.dll" not in {name.lower() for name in copied}:
        raise RuntimeError("Windows 运行库不完整：缺少 MSVCP140.dll")


def _build_launcher(package_dir: Path, build_dir: Path) -> None:
    gcc = shutil.which("x86_64-w64-mingw32-gcc")
    windres = shutil.which("x86_64-w64-mingw32-windres")
    if not gcc or not windres:
        raise RuntimeError("缺少 mingw-w64，请先运行：brew install mingw-w64")

    icon_path = ROOT / "assets" / "depth-video-converter.ico"
    resource_file = build_dir / "launcher.rc"
    resource_object = build_dir / "launcher-resource.o"
    resource_file.write_text(f'1 ICON "{icon_path.as_posix()}"\n', encoding="utf-8")
    _run([windres, str(resource_file), "-O", "coff", "-o", str(resource_object)])
    _run([
        gcc,
        str(ROOT / "packaging" / "windows_launcher.c"),
        str(resource_object),
        "-O2",
        "-s",
        "-municode",
        "-mwindows",
        "-o",
        str(package_dir / "Depth Video Converter.exe"),
    ])


def _write_runtime_config(package_dir: Path) -> None:
    pth_file = package_dir / "python311._pth"
    pth_file.write_text(
        "python311.zip\n.\nLib\\site-packages\napp\nimport site\n",
        encoding="utf-8",
    )
    (package_dir / "使用说明.txt").write_text(
        "深度视频转换器 Windows 便携版\n\n"
        "1. 请先完整解压此压缩包。\n"
        "2. 双击“Depth Video Converter.exe”。\n"
        "3. 稍等片刻，网页操作界面会自动打开，并保留一个小控制窗口。\n"
        "4. 首次选择模型时会自动下载模型。\n"
        "5. 退出时可点击控制窗口或网页底部的“退出应用”，也可以关闭浏览器标签页/窗口并确认离开。\n\n"
        "已内置常用 Windows 运行库。请勿单独移动 EXE；它需要同目录中的运行文件。\n"
        "模型位置：%LOCALAPPDATA%\\DepthVideoConverter\\models\n",
        encoding="utf-8-sig",
    )


def _zip_package(package_dir: Path, output_zip: Path) -> None:
    if output_zip.exists():
        output_zip.unlink()
    print(f"Creating {output_zip}")
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                archive.write(path, Path(package_dir.name) / path.relative_to(package_dir))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build" / "windows-portable")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    build_dir = args.build_dir.resolve()
    package_dir = build_dir / PACKAGE_NAME
    cache_dir = build_dir / "cache"
    python_zip = cache_dir / f"python-{PYTHON_VERSION}-embed-amd64.zip"

    output_dir.mkdir(parents=True, exist_ok=True)
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    _download(PYTHON_ZIP_URL, python_zip)
    with zipfile.ZipFile(python_zip) as archive:
        archive.extractall(package_dir)

    site_packages = package_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True)
    _run([
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(site_packages),
        "--platform",
        "win_amd64",
        "--implementation",
        "cp",
        "--python-version",
        "3.11",
        "--abi",
        "cp311",
        "--only-binary=:all:",
        "--no-compile",
        "--upgrade",
        "-r",
        str(ROOT / "packaging" / "desktop-requirements.txt"),
    ])

    _copy_windows_runtime_dlls(package_dir)
    _copy_app(package_dir)
    _write_runtime_config(package_dir)
    _build_launcher(package_dir, build_dir)
    shutil.copy2(ROOT / "README_CN.md", package_dir / "项目说明.md")

    output_zip = output_dir / f"{PACKAGE_NAME}.zip"
    _zip_package(package_dir, output_zip)
    print(output_zip)


if __name__ == "__main__":
    main()
