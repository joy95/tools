"""统一解析 ffmpeg 可执行文件位置，并封装调用。

查找顺序：
1. 环境变量 ``FFMPEG_BINARY``（显式指定，优先级最高）。
2. 系统 ``PATH`` 中的 ``ffmpeg``（Dockerfile 里通过 apt 安装的走这条）。
3. ``imageio-ffmpeg`` 自带的静态二进制（moviepy 的依赖，本地开发环境通常只有这个）。
"""

import os
import shutil
import subprocess
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 900


class FFmpegUnavailable(RuntimeError):
    """找不到可用的 ffmpeg 时抛出。"""


def ffmpeg_path() -> str:
    configured = os.environ.get("FFMPEG_BINARY", "").strip()
    if configured and Path(configured).exists():
        return configured

    found = shutil.which("ffmpeg")
    if found:
        return found

    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - 依赖缺失分支
        raise FFmpegUnavailable("未找到 ffmpeg，请安装 ffmpeg 或 imageio-ffmpeg") from exc

    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - 二进制下载失败分支
        raise FFmpegUnavailable("未找到可用的 ffmpeg 可执行文件") from exc


def run_ffmpeg(args: list[str], timeout: int = DEFAULT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """执行一次 ffmpeg，返回完成信息；调用方通过 ``returncode`` 判断成败。"""
    command = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", *args]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def ffmpeg_error(completed: subprocess.CompletedProcess) -> str:
    """从失败结果里取一段可读的错误信息。"""
    text = (completed.stderr or "").strip() or (completed.stdout or "").strip()
    if not text:
        return f"ffmpeg 执行失败（退出码 {completed.returncode}）"
    return text.splitlines()[-1][:300]
