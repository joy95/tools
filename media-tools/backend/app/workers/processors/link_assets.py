from pathlib import Path

import requests

from app.core.config import settings
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    )
}


def download_work_assets(task_id: str, work: ExtractedWork) -> dict:
    work_dir = _work_dir_for_task(task_id)
    work_dir.mkdir(parents=True, exist_ok=True)

    assets = []
    for index, asset in enumerate(work.assets, start=1):
        staging_path = work_dir / f"{asset.type}_{index}.download"
        response_content_type = _download(asset.source_url, staging_path)
        suffix = _suffix_for_asset(asset, response_content_type)
        mime_type = _mime_from_asset(asset, response_content_type, suffix)
        target_path = work_dir / f"{asset.type}_{index}{suffix}"
        staging_path.replace(target_path)
        assets.append(
            {
                "type": asset.type,
                "source_url": asset.source_url,
                "mime_type": mime_type,
                "width": asset.width,
                "height": asset.height,
                "local_url": _public_url(target_path),
            }
        )

    return {
        "platform": work.platform,
        "source_url": work.source_url,
        "media_type": work.media_type,
        "caption": work.caption,
        "title": work.title,
        "author": work.author,
        "cover_url": work.cover_url,
        "assets": assets,
        "parse_method": work.parse_method,
        "download_status": "success" if assets else "empty",
    }


def _work_dir_for_task(task_id: str) -> Path:
    if not task_id or Path(task_id).name != task_id:
        raise ValueError("task_id must be a safe path segment")

    base_dir = (Path(settings.media_root).resolve() / "link_assets").resolve()
    work_dir = (base_dir / task_id).resolve()
    if not work_dir.is_relative_to(base_dir):
        raise ValueError("task_id must stay under link_assets")
    return work_dir


def _download(url: str, target_path: Path) -> str:
    part_path = target_path.with_name(f"{target_path.name}.part")
    try:
        with requests.get(url, headers=REQUEST_HEADERS, stream=True, timeout=60) as response:
            response.raise_for_status()
            content_type = _normalize_mime(response.headers.get("content-type", ""))
            with part_path.open("wb") as target_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        target_file.write(chunk)
            part_path.replace(target_path)
            return content_type
    except Exception:
        if part_path.exists():
            part_path.unlink()
        raise


def _suffix_for_asset(asset: ExtractedAsset, response_content_type: str = "") -> str:
    mime_type = _normalize_mime(asset.mime_type) or _normalize_mime(response_content_type)
    if mime_type == "video/mp4":
        return ".mp4"
    if mime_type == "application/vnd.apple.mpegurl":
        return ".m3u8"
    if mime_type == "image/png":
        return ".png"
    if mime_type == "image/webp":
        return ".webp"
    if mime_type == "image/gif":
        return ".gif"
    if mime_type == "image/jpeg":
        return ".jpg"

    path_suffix = Path(asset.source_url.split("?", 1)[0]).suffix.lower()
    if path_suffix in {".mp4", ".m3u8", ".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if path_suffix == ".jpeg" else path_suffix
    return ".mp4" if asset.type == "video" else ".jpg"


def _mime_from_asset(asset: ExtractedAsset, response_content_type: str, suffix: str) -> str:
    return _normalize_mime(asset.mime_type) or _normalize_mime(response_content_type) or _mime_from_suffix(suffix)


def _normalize_mime(content_type: str) -> str:
    mime_type = content_type.split(";", 1)[0].strip().lower()
    if mime_type == "application/x-mpegurl":
        return "application/vnd.apple.mpegurl"
    return mime_type


def _mime_from_suffix(suffix: str) -> str:
    return {
        ".mp4": "video/mp4",
        ".m3u8": "application/vnd.apple.mpegurl",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix.lower(), "application/octet-stream")


def _public_url(path: Path) -> str:
    relative = path.resolve().relative_to(Path(settings.media_root).resolve())
    return f"{settings.public_media_prefix}/{relative.as_posix()}"
