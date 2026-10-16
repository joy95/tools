import hashlib
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.core.config import settings


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://www.douyin.com/",
}


def process_link_video(source_url: str, direct_video_url: str = "") -> dict:
    try:
        resolved = _resolve_video(source_url, direct_video_url)
    except Exception as exc:
        return {
            "status": "unavailable",
            "message": f"视频解析失败：{exc}",
            "download_url": "",
            "processed_video_url": "",
            "ocr_text": "",
            "source": {"download_url": "", "method": "resolve_failed"},
        }
    if not resolved["download_url"]:
        return {
            "status": "unavailable",
            "message": "未能解析到可下载视频地址，平台可能需要登录、签名或风控校验",
            "download_url": "",
            "processed_video_url": "",
            "ocr_text": "",
            "source": resolved,
        }

    work_dir = Path(settings.media_root) / "link_videos" / _stable_id(source_url)
    work_dir.mkdir(parents=True, exist_ok=True)
    original_path = work_dir / "original.mp4"
    processed_path = work_dir / "watermark_removed.mp4"

    try:
        _download_video(resolved["download_url"], original_path)
    except Exception as exc:
        return {
            "status": "unavailable",
            "message": f"视频下载失败：{exc}",
            "download_url": "",
            "processed_video_url": "",
            "ocr_text": "",
            "source": resolved,
        }

    watermark_result = _remove_visible_watermark(original_path, processed_path)
    ocr_text = _extract_video_text(processed_path if processed_path.exists() else original_path)

    public_path = processed_path if processed_path.exists() else original_path
    return {
        "status": "success",
        "message": watermark_result,
        "download_url": _public_url(public_path),
        "processed_video_url": _public_url(public_path),
        "ocr_text": ocr_text,
        "source": resolved,
    }


def _resolve_video(source_url: str, direct_video_url: str) -> dict:
    if _is_direct_video_url(direct_video_url):
        return {"download_url": direct_video_url, "method": "public_page_direct_url"}

    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return {"download_url": direct_video_url if _is_direct_video_url(direct_video_url) else "", "method": "yt_dlp_unavailable"}

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bv*+ba/best",
    }
    if settings.ytdlp_cookies_file and Path(settings.ytdlp_cookies_file).exists():
        options["cookiefile"] = settings.ytdlp_cookies_file

    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(source_url, download=False)

    download_url = info.get("url") or ""
    if not download_url:
        formats = info.get("formats") or []
        best = sorted(
            [item for item in formats if item.get("url")],
            key=lambda item: (item.get("height") or 0, item.get("tbr") or 0),
            reverse=True,
        )
        download_url = best[0]["url"] if best else ""

    return {
        "download_url": download_url,
        "method": "yt_dlp",
        "title": info.get("title") or "",
        "description": info.get("description") or "",
        "thumbnail": info.get("thumbnail") or "",
    }


def _download_video(url: str, target_path: Path) -> None:
    with requests.get(url, headers=REQUEST_HEADERS, stream=True, timeout=60) as response:
        response.raise_for_status()
        with target_path.open("wb") as target_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    target_file.write(chunk)


def _remove_visible_watermark(input_path: Path, output_path: Path) -> str:
    filter_expr = (
        "delogo=x=10:y=10:w=180:h=80,"
        "delogo=x=main_w-210:y=10:w=200:h=80,"
        "delogo=x=main_w-230:y=main_h-150:w=220:h=90"
    )
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        filter_expr,
        "-c:a",
        "copy",
        str(output_path),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        if output_path.exists():
            output_path.unlink()
        return "视频已下载，去水印处理失败，返回原视频"
    return "视频已下载，并已对常见水印区域做模糊去除"


def _extract_video_text(video_path: Path) -> str:
    try:
        import cv2
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return ""

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return ""

    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count <= 0:
        capture.release()
        return ""

    ocr = RapidOCR()
    texts: list[str] = []
    sample_count = min(8, frame_count)
    frame_indexes = sorted({int(frame_count * (index + 1) / (sample_count + 1)) for index in range(sample_count)})

    for frame_index in frame_indexes:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            continue
        result, _ = ocr(frame)
        for item in result or []:
            text = item[1]
            score = item[2]
            if text and score >= 0.45 and text not in texts:
                texts.append(text)

    capture.release()
    return "\n".join(texts)


def _is_direct_video_url(url: str) -> bool:
    if not url:
        return False
    return urlparse(url).path.lower().endswith((".mp4", ".mov", ".m3u8"))


def _public_url(path: Path) -> str:
    relative = path.relative_to(Path(settings.media_root))
    return f"{settings.public_media_prefix}/{relative.as_posix()}"


def _stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
