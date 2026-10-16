"""视频去字幕：通过链接读取视频，框选字幕区域后去除。

与水印不同，字幕不是固定在角落的显式标识，而是随视频内容变化的人造文字条，
位置需要用户手动框选。因此本模块提供两段式流程：

1. ``extract_frame_for_selection`` —— 下载视频并抽取一帧，供前端让用户框选字幕区域；
2. ``remove_subtitle`` —— 拿到用户框选的归一化区域后，对整段视频做局部修复。

区域去除逻辑直接复用 ``watermark`` 模块（delogo 插值 / OpenCV Telea 逐帧修复），
保留音轨与原分辨率帧率，输出 H.264 + faststart。
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.workers.processors.ffmpeg_utils import run_ffmpeg
from app.workers.processors.link_video import (
    _download_video,
    _public_url,
    _resolve_video,
    _stable_id,
)
from app.workers.processors.watermark import (
    METHOD_ALGORITHMS,
    VIDEO_SUFFIXES,
    _apply_removal,
)
from app.workers.processors.watermark_detect import (
    Region,
    custom_region,
    expand_region,
    merge_overlapping,
    probe_video,
    render_region_preview,
)

DEFAULT_PADDING = 4
DEFAULT_SUBTITLE_BAND_RATIO = 0.12  # 未框选时，默认处理底部 12% 字幕带


def _video_work_dir(source_url: str) -> Path:
    work_dir = Path(settings.media_root) / "link_videos" / _stable_id(source_url)
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def _is_direct_video_url(url: str) -> bool:
    return url.lower().endswith((".mp4", ".mov", ".m4v", ".mkv", ".webm"))


def ensure_video(source_url: str) -> dict:
    """解析并下载视频（已存在则复用），返回本地路径与解析信息。"""
    local_path = Path(source_url)
    if local_path.exists() and local_path.suffix.lower() in VIDEO_SUFFIXES:
        return {"ok": True, "path": local_path, "download_url": _public_url(local_path), "source": {"method": "local"}}

    resolved = _resolve_video(source_url, source_url if _is_direct_video_url(source_url) else "")
    if not resolved.get("download_url"):
        return {
            "ok": False,
            "message": "未能解析到可下载视频地址，平台可能需要登录或签名校验",
            "source": resolved,
        }

    work_dir = _video_work_dir(source_url)
    original = work_dir / "original.mp4"
    if not original.exists():
        try:
            _download_video(resolved["download_url"], original)
        except Exception as exc:
            return {"ok": False, "message": f"视频下载失败：{exc}", "source": resolved}
    if not original.exists():
        return {"ok": False, "message": "视频下载失败", "source": resolved}
    return {"ok": True, "path": original, "download_url": _public_url(original), "source": resolved}


def extract_frame_for_selection(source_url: str) -> dict:
    """下载视频并抽取一帧，供前端用户框选字幕区域。"""
    prepared = ensure_video(source_url)
    if not prepared["ok"]:
        return {"status": "unavailable", "message": prepared["message"], "source": prepared.get("source", {})}

    original = Path(prepared["path"])
    meta = probe_video(original)
    width = int(meta.get("width") or 0)
    height = int(meta.get("height") or 0)
    if width <= 0 or height <= 0:
        return {"status": "unavailable", "message": "视频信息读取失败，文件可能已损坏", "source": meta}

    work_dir = _video_work_dir(source_url)
    frame_path = work_dir / "subtitle_frame.jpg"
    if not _extract_frame(original, frame_path, meta):
        return {"status": "unavailable", "message": "抽取预览帧失败", "source": meta}

    return {
        "status": "success",
        "frame_url": _public_url(frame_path),
        "width": width,
        "height": height,
        "duration": meta.get("duration"),
        "download_url": prepared["download_url"],
        "source": meta,
    }


def _extract_frame(source: Path, frame_path: Path, meta: dict) -> bool:
    duration = float(meta.get("duration") or 0)
    seek = max(0.1, duration / 2) if duration > 0 else 0.1
    args = ["-y", "-ss", f"{seek:.3f}", "-i", str(source), "-frames:v", "1", "-q:v", "2", str(frame_path)]
    completed = run_ffmpeg(args, timeout=120)
    return completed.returncode == 0 and frame_path.exists() and frame_path.stat().st_size > 0


def remove_subtitle(input_payload: dict) -> dict:
    """工作任务入口：按用户框选区域去除视频字幕。"""
    source_url = str(input_payload.get("url") or "").strip()
    local_path = str(input_payload.get("file_path") or "").strip()

    if not source_url and not local_path:
        return _empty_result(
            input_payload,
            message="缺少视频来源，请通过视频链接或本地文件提交",
            method="missing_source",
            status="failed",
        )

    algorithm = str(input_payload.get("subtitle_method") or "delogo").strip().lower()
    if algorithm not in METHOD_ALGORITHMS:
        algorithm = "delogo"

    prepared = _load_source(source_url, local_path)
    if not prepared["ok"]:
        return _empty_result(
            input_payload,
            message=prepared["message"],
            method="download_failed",
            status="failed",
            extra={"source": prepared.get("source", {})},
        )

    source_path = Path(prepared["path"])
    meta = probe_video(source_path)
    width = int(meta.get("width") or 0)
    height = int(meta.get("height") or 0)
    if width <= 0 or height <= 0:
        return _empty_result(
            input_payload,
            message="视频信息读取失败，文件可能已损坏或缺少视频轨",
            method="probe_failed",
            status="failed",
        )

    region = _resolve_region(input_payload, width, height)
    if region is None:
        return _empty_result(
            input_payload,
            message="未提供有效的字幕区域，请在预览帧上框选字幕位置后重试",
            method="no_region",
            status="failed",
        )

    cache_key = source_url or str(source_path)
    work_dir = Path(settings.media_root) / "processed" / _stable_id(cache_key)
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path = work_dir / "subtitle_removed.mp4"
    preview_path = work_dir / "subtitle_preview.jpg"

    regions = [expand_region(region, width, height, DEFAULT_PADDING)]
    regions = merge_overlapping(regions)

    preview_ok = render_region_preview(source_path, regions, preview_path)

    ok, detail = _apply_removal(source_path, output_path, regions, meta, algorithm)
    if not ok:
        if output_path.exists():
            output_path.unlink()
        return _empty_result(
            input_payload,
            message=f"去字幕处理失败：{detail}",
            method=METHOD_ALGORITHMS[algorithm],
            status="failed",
            extra={"video_meta": meta, "regions": [region.as_dict() for region in regions]},
        )

    return {
        "message": "已按框选区域去除字幕",
        "status": "success",
        "method": METHOD_ALGORITHMS[algorithm],
        "algorithm": algorithm,
        "regions": [region.as_dict() for region in regions],
        "video_meta": meta,
        "original_video_url": _public_url(source_path),
        "processed_video_url": _public_url(output_path),
        "download_url": _public_url(output_path),
        "preview_url": _public_url(preview_path) if preview_ok else "",
        "source": input_payload,
    }


def _load_source(source_url: str, local_path: str) -> dict:
    if source_url:
        return ensure_video(source_url)
    if local_path:
        candidate = Path(local_path)
        if candidate.exists() and candidate.suffix.lower() in VIDEO_SUFFIXES:
            return {"ok": True, "path": candidate, "download_url": _public_url(candidate), "source": {"method": "local"}}
        return {"ok": False, "message": "本地文件不存在或不是可处理的视频", "source": {}}
    return {"ok": False, "message": "缺少视频来源", "source": {}}


def _resolve_region(input_payload: dict, width: int, height: int) -> Region | None:
    """框选区域优先；缺省时兜底到画面底部字幕带。"""
    box = input_payload.get("subtitle_region")
    if isinstance(box, dict) and all(key in box for key in ("x", "y", "w", "h")):
        region = custom_region(box, width, height)
        if region is not None:
            return region

    band_h = max(8, int(round(height * DEFAULT_SUBTITLE_BAND_RATIO)))
    return Region(
        x=0,
        y=height - band_h,
        w=width,
        h=band_h,
        confidence=0.0,
        source="default",
    )


def _empty_result(input_payload: dict, message: str, method: str, status: str, extra: dict | None = None) -> dict:
    result = {
        "message": message,
        "status": status,
        "method": method,
        "algorithm": str(input_payload.get("subtitle_method") or "delogo"),
        "regions": [],
        "video_meta": {},
        "original_video_url": "",
        "processed_video_url": "",
        "download_url": "",
        "preview_url": "",
        "source": input_payload,
    }
    result.update(extra or {})
    return result
