#!/usr/bin/env python3
"""Generate deterministic PNG, ICNS, and ICO desktop app icons."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def _make_master() -> Image.Image:
    size = 1024
    image = Image.new("RGBA", (size, size), "#16191d")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((44, 44, 980, 980), radius=210, fill="#20252b", outline="#4d5660", width=10)
    draw.rounded_rectangle((126, 126, 898, 898), radius=164, fill="#101316")

    contours = [
        ((194, 204, 830, 842), "#343b43"),
        ((256, 262, 768, 782), "#58616b"),
        ((320, 324, 704, 718), "#89919a"),
        ((382, 388, 642, 654), "#c8cdd2"),
    ]
    for bounds, color in contours:
        draw.ellipse(bounds, fill=color)

    draw.polygon([(438, 364), (438, 660), (688, 512)], fill="#ffffff")
    draw.rounded_rectangle((180, 790, 844, 836), radius=23, fill="#353c44")
    draw.rounded_rectangle((180, 790, 618, 836), radius=23, fill="#10B981")
    draw.ellipse((600, 770, 662, 856), fill="#ffffff")
    return image


def _make_installer_banner(master: Image.Image) -> None:
    banner = Image.new("RGB", (164, 314), "#FFFFFF")
    draw = ImageDraw.Draw(banner)
    draw.rectangle((0, 210, 164, 314), fill="#F3F4F6")
    icon = master.resize((80, 80), Image.Resampling.LANCZOS)
    icon_rgb = Image.new("RGB", icon.size, "#FFFFFF")
    icon_rgb.paste(icon, mask=icon.split()[3])
    banner.paste(icon_rgb, (42, 80))
    draw.rectangle((32, 172, 132, 174), fill="#10B981")
    banner.save(ASSETS / "installer-banner.bmp")


def _make_installer_small(master: Image.Image) -> None:
    small = master.resize((55, 55), Image.Resampling.LANCZOS)
    small_rgb = Image.new("RGB", small.size, "#FFFFFF")
    small_rgb.paste(small, mask=small.split()[3])
    small_rgb.save(ASSETS / "installer-small.bmp")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = _make_master()
    png_path = ASSETS / "depth-video-converter.png"
    ico_path = ASSETS / "depth-video-converter.ico"
    icns_path = ASSETS / "depth-video-converter.icns"
    master.save(png_path)
    master.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    _make_installer_banner(master)
    _make_installer_small(master)

    if shutil.which("iconutil"):
        iconset = ASSETS / "DepthuVideoConverter.iconset"
        if iconset.exists():
            shutil.rmtree(iconset)
        iconset.mkdir()
        for points in (16, 32, 128, 256, 512):
            master.resize((points, points), Image.Resampling.LANCZOS).save(iconset / f"icon_{points}x{points}.png")
            pixels = points * 2
            master.resize((pixels, pixels), Image.Resampling.LANCZOS).save(
                iconset / f"icon_{points}x{points}@2x.png"
            )
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)], check=True)
        shutil.rmtree(iconset)


if __name__ == "__main__":
    main()
