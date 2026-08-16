"""FFmpeg helpers — video encoding, audio extraction, and multiplexing."""

from __future__ import annotations

import os
import shutil
import subprocess

import numpy as np


def ffmpeg_available() -> bool:
    """Return True if ffmpeg is on the system PATH."""
    try:
        _get_ffmpeg_path()
        return True
    except RuntimeError:
        return False


def _get_ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if path is None:
        try:
            import imageio_ffmpeg

            bundled_path = imageio_ffmpeg.get_ffmpeg_exe()
            if os.path.isfile(bundled_path):
                path = bundled_path
        except (ImportError, RuntimeError):
            pass
    if path is None:
        raise RuntimeError(
            "系统 PATH 中未找到 ffmpeg。\n\n"
            "请先安装：\n"
            "  • macOS:  brew install ffmpeg\n"
            "  • Windows: winget install ffmpeg\n"
            "              …或前往 https://ffmpeg.org/download.html 下载\n"
            "安装后请重新启动本应用。"
        )
    return path


def has_audio_stream(video_path: str) -> bool:
    """Check whether *video_path* contains an audio track."""
    ffmpeg = _get_ffmpeg_path()
    cmd = [
        ffmpeg, "-i", video_path,
        "-af", "volumedetect",
        "-vn", "-sn", "-dn",
        "-f", "null", "-",
    ]
    # Keep stderr as bytes.  FFmpeg diagnostics can contain characters that
    # are not decodable with Windows' active console code page (often GBK).
    # The stream marker itself is ASCII, so no locale-dependent decoding is
    # needed here.
    result = subprocess.run(cmd, capture_output=True)
    return b"Audio:" in result.stderr


def extract_audio(video_path: str, output_audio_path: str) -> bool:
    """Extract the audio track from *video_path* as AAC into *output_audio_path*.

    Returns True on success.
    """
    ffmpeg = _get_ffmpeg_path()
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "aac",
        "-b:a", "192k",
        output_audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def write_video_ffmpeg(
    frames: np.ndarray,         # (N, H, W, 3) uint8 BGR
    fps: float,
    output_path: str,
    crf: int = 18,
    progress=None,
) -> None:
    """Encode a stack of BGR frames to H.264 MP4 via an ffmpeg pipe."""
    ffmpeg = _get_ffmpeg_path()
    _n, h, w, _c = frames.shape
    cmd = [
        ffmpeg, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{w}x{h}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", str(crf),
        "-preset", "medium",
        output_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert proc.stdin is not None
    try:
        total = max(int(_n), 1)
        for idx, frame in enumerate(frames):
            proc.stdin.write(frame.tobytes())
            if progress is not None:
                progress((idx + 1) / total)
        proc.stdin.close()
        returncode = proc.wait(timeout=300)
        if returncode != 0:
            raise RuntimeError(f"ffmpeg 编码失败，退出码 {returncode}")
    except Exception:
        proc.kill()
        raise


def merge_audio_video(video_path: str, audio_path: str, output_path: str) -> None:
    """Mux a video file and audio file into a single MP4 container."""
    ffmpeg = _get_ffmpeg_path()
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
