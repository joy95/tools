from pathlib import Path
from typing import Any

from app.core.config import settings
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork, LinkExtractionError


def video_mime_type(url: str, format_info: dict[str, Any] | None = None) -> str:
    normalized_url = url.split("?", 1)[0].lower()
    if normalized_url.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"
    if normalized_url.endswith(".mp4"):
        return "video/mp4"

    if format_info:
        ext = str(format_info.get("ext") or "").lower()
        protocol = str(format_info.get("protocol") or "").lower()
        if ext == "m3u8" or "m3u8" in protocol:
            return "application/vnd.apple.mpegurl"
        if ext == "mp4":
            return "video/mp4"

    return ""


def _is_hls_format(url: str, format_info: dict[str, Any] | None = None) -> bool:
    normalized_url = url.split("?", 1)[0].lower()
    if normalized_url.endswith(".m3u8"):
        return True
    if not format_info:
        return False

    ext = str(format_info.get("ext") or "").lower()
    protocol = str(format_info.get("protocol") or "").lower()
    return ext == "m3u8" or "m3u8" in protocol


def _is_progressive_format(format_info: dict[str, Any]) -> bool:
    vcodec = format_info.get("vcodec")
    acodec = format_info.get("acodec")
    if vcodec is None and acodec is None:
        return True
    return vcodec not in (None, "none") and acodec not in (None, "none")


def _is_saveable_video_format(format_info: dict[str, Any]) -> bool:
    url = str(format_info.get("url") or "")
    return bool(url) and not _is_hls_format(url, format_info) and _is_progressive_format(format_info)


def _format_rank(format_info: dict[str, Any]) -> tuple[int, int, int]:
    url = str(format_info.get("url") or "")
    mime_type = str(format_info.get("mime_type") or "") or video_mime_type(url, format_info)
    is_mp4 = 1 if mime_type == "video/mp4" or video_mime_type(url, format_info) == "video/mp4" else 0
    return (is_mp4, format_info.get("height") or 0, format_info.get("tbr") or 0)


def _get_youtube_dl():
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise LinkExtractionError("ytdlp_unavailable", "yt-dlp 未安装或不可用") from exc

    return YoutubeDL


def extract_with_ytdlp(url: str) -> ExtractedWork:
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bv*+ba/best",
    }
    if settings.ytdlp_cookies_file and Path(settings.ytdlp_cookies_file).exists():
        options["cookiefile"] = settings.ytdlp_cookies_file

    YoutubeDL = _get_youtube_dl()
    try:
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
    except LinkExtractionError:
        raise
    except Exception as exc:
        raise LinkExtractionError("ytdlp_extract_failed", "yt-dlp 解析失败") from exc

    if not isinstance(info, dict):
        raise LinkExtractionError("ytdlp_extract_failed", "yt-dlp 未返回有效解析结果")

    media_format = info
    media_url = str(info.get("url") or "")
    if media_url and not _is_saveable_video_format(info):
        media_url = ""
        media_format = {}
    if not media_url:
        formats = sorted(
            [item for item in info.get("formats", []) if isinstance(item, dict) and _is_saveable_video_format(item)],
            key=_format_rank,
            reverse=True,
        )
        media_format = formats[0] if formats else {}
        media_url = str(media_format.get("url") or "") if media_format else ""

    if not media_url:
        raise LinkExtractionError("ytdlp_extract_failed", "yt-dlp 未返回可保存视频资源")

    assets = [ExtractedAsset(type="video", source_url=media_url, mime_type=video_mime_type(media_url, media_format))]
    return ExtractedWork(
        platform="unknown",
        source_url=info.get("webpage_url") or url,
        media_type="video" if assets else "unknown",
        caption=info.get("description") or info.get("title") or "",
        title=info.get("title") or "",
        cover_url=info.get("thumbnail") or None,
        assets=assets,
        parse_method="yt_dlp",
    )
