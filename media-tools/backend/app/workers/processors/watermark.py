"""本地视频去水印。

针对 AI 生成视频里**固定在角落的显式标识**（平台角标、"AI生成" 文字等）：

1. **定位** —— 智能模式下自动检测（见 ``watermark_detect``），手动模式下使用用户指定的角落区域；
2. **去除** —— ``delogo`` 用区域边缘像素插值重建，速度快；``inpaint`` 逐帧做 Telea 修复，
   在复杂背景上痕迹更自然，代价是耗时数倍；
3. **保真** —— 保留原分辨率、帧率与音轨，输出 H.264 + faststart，便于小程序直接播放与保存。
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from app.core.config import settings
from app.workers.processors.ffmpeg_utils import FFmpegUnavailable, ffmpeg_error, ffmpeg_path, run_ffmpeg
from app.workers.processors.watermark_detect import (
    DEFAULT_FALLBACK_REGIONS,
    Region,
    custom_region,
    detect_watermark_regions,
    expand_region,
    merge_overlapping,
    preset_region,
    probe_video,
    render_region_preview,
    tighten_region,
)

VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}

METHOD_ALGORITHMS = {"delogo": "delogo_error_diffusion", "inpaint": "opencv_telea_inpaint"}
DEFAULT_PADDING = 2


def remove_watermark(input_payload: dict) -> dict:
    """工作任务入口：对上传的本地视频做去水印处理。"""
    source_path = Path(str(input_payload.get("file_path", "")))
    if not source_path.exists() or source_path.suffix.lower() not in VIDEO_SUFFIXES:
        return _empty_result(
            input_payload,
            message="当前文件不是可处理的视频，请上传 mp4/mov 等视频文件",
            method="unsupported_file_type",
            status="unsupported",
        )

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

    mode = str(input_payload.get("watermark_mode") or "auto").strip().lower()
    padding = _parse_padding(input_payload.get("watermark_padding"))
    algorithm = str(input_payload.get("watermark_method") or "delogo").strip().lower()
    if algorithm not in METHOD_ALGORITHMS:
        algorithm = "delogo"

    detected: list[Region] = []
    message_notes: list[str] = []

    if mode == "manual":
        requested = _manual_region(input_payload, width, height)
        if requested is None:
            mode = "auto"
            message_notes.append("未提供有效的自定义区域，已改用智能检测")
        else:
            detected = [requested]
    else:
        mode = "auto"

    if mode == "auto":
        detected = detect_watermark_regions(source_path)
        if not detected:
            detected = _fallback_regions(width, height)
            message_notes.append("未检测到明显的水印区域，已按国内 AI 平台最常见的右下角位置处理")

    working_dir = Path(settings.media_root) / "processed" / _stable_id(str(source_path))
    working_dir.mkdir(parents=True, exist_ok=True)
    output_path = working_dir / "watermark_removed.mp4"
    preview_path = working_dir / "watermark_preview.jpg"

    if mode == "auto":
        detected = [tighten_region(region, width, height) if region.source == "auto" else region for region in detected]

    regions = [expand_region(region, width, height, padding) for region in detected]
    regions = merge_overlapping(regions)

    preview_ok = render_region_preview(source_path, regions, preview_path)

    if not regions:
        return _empty_result(
            input_payload,
            message="未能确定水印区域，请改用「手动指定区域」重试",
            method="no_region",
            status="failed",
            extra={"video_meta": meta},
        )

    ok, detail = _apply_removal(source_path, output_path, regions, meta, algorithm)
    if not ok:
        if output_path.exists():
            output_path.unlink()
        return _empty_result(
            input_payload,
            message=f"去水印处理失败：{detail}",
            method=METHOD_ALGORITHMS[algorithm],
            status="failed",
            extra={"video_meta": meta, "regions": [region.as_dict() for region in regions]},
        )

    notes = [f"已去除 {len(regions)} 处水印区域"]
    if mode == "manual":
        notes.append("按手动指定区域处理")
    else:
        notes.append("由智能检测自动定位" if not message_notes else "已按兜底区域处理")
    notes.extend(message_notes)

    return {
        "message": "；".join(notes),
        "status": "success",
        "method": METHOD_ALGORITHMS[algorithm],
        "mode": mode,
        "algorithm": algorithm,
        "regions": [region.as_dict() for region in regions],
        "detected_regions": [region.as_dict() for region in detected],
        "video_meta": meta,
        "original_video_url": _public_url(source_path),
        "processed_video_url": _public_url(output_path),
        "download_url": _public_url(output_path),
        "preview_url": _public_url(preview_path) if preview_ok else "",
        "video_text": _extract_video_text(output_path) if input_payload.get("with_text") else "",
        "source": input_payload,
    }


def _manual_region(input_payload: dict, width: int, height: int) -> Region | None:
    box = input_payload.get("watermark_box")
    if isinstance(box, dict) and box:
        parsed = custom_region(box, width, height)
        if parsed is not None:
            return parsed

    name = input_payload.get("watermark_region")
    if name:
        return preset_region(str(name), str(input_payload.get("watermark_size") or "medium"), width, height)
    return None


def _fallback_regions(width: int, height: int) -> list[Region]:
    regions: list[Region] = []
    for name in DEFAULT_FALLBACK_REGIONS:
        region = preset_region(name, "medium", width, height)
        if region is not None:
            regions.append(region)
    return regions


def _parse_padding(value) -> int:
    try:
        padding = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PADDING
    return max(0, min(60, padding))


def _apply_removal(
    source_path: Path,
    output_path: Path,
    regions: list[Region],
    meta: dict,
    algorithm: str,
) -> tuple[bool, str]:
    try:
        ffmpeg_path()
    except FFmpegUnavailable as exc:
        return False, str(exc)

    if algorithm == "inpaint":
        ok, detail = _remove_with_patch(source_path, output_path, regions, meta, radius=3)
        if ok:
            return True, detail
        fallback_ok, fallback_detail = _remove_with_delogo(source_path, output_path, regions, meta)
        if fallback_ok:
            return True, "精细模式不可用，已自动改用快速模式"
        return False, f"{detail}；{fallback_detail}"

    ok, detail = _remove_with_patch(source_path, output_path, regions, meta, radius=2)
    if ok:
        return True, detail
    return _remove_with_delogo(source_path, output_path, regions, meta)


def _remove_with_delogo(source_path: Path, output_path: Path, regions: list[Region], meta: dict) -> tuple[bool, str]:
    filters = [f"delogo=x={region.x}:y={region.y}:w={region.w}:h={region.h}" for region in regions]
    if int(meta.get("width") or 0) % 2 or int(meta.get("height") or 0) % 2:
        filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

    args = [
        "-y",
        "-i",
        str(source_path),
        "-vf",
        ",".join(filters),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        str(output_path),
    ]
    completed = run_ffmpeg(args, timeout=_encode_timeout(meta))
    if completed.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        return False, ffmpeg_error(completed)
    return True, "快速模式（delogo 插值）"


def _remove_with_patch(
    source_path: Path,
    output_path: Path,
    regions: list[Region],
    meta: dict,
    radius: int,
) -> tuple[bool, str]:
    """只修复水印小块，边缘淡出，避免整块涂抹。"""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return False, "局部修复需要 opencv-python，当前环境未安装"

    width = int(meta.get("width") or 0)
    height = int(meta.get("height") or 0)
    fps = float(meta.get("fps") or 0) or 25.0
    if width <= 0 or height <= 0:
        return False, "视频尺寸异常"

    command = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps}",
        "-i",
        "pipe:0",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-shortest",
        str(output_path),
    ]

    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except OSError as exc:
        return False, f"无法启动 ffmpeg：{exc}"

    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        process.kill()
        return False, "无法读取源视频"

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            _blend_regions(frame, regions, radius, cv2, np)
            process.stdin.write(frame.tobytes())
    except (BrokenPipeError, OSError) as exc:
        capture.release()
        process.kill()
        return False, f"修复写入中断：{exc}"
    finally:
        capture.release()

    process.stdin.close()
    stderr = (process.stderr.read() or b"").decode("utf-8", "ignore").strip()
    return_code = process.wait(timeout=_encode_timeout(meta))

    if return_code != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        return False, stderr.splitlines()[-1][:200] if stderr else f"ffmpeg 退出码 {return_code}"
    return True, "局部修复"


def _blend_regions(frame, regions: list[Region], radius: int, cv2, np) -> None:
    """用旁边同样大小的画面盖住水印，内侧边缘做短渐变。"""
    for region in regions:
        donor = _neighbor_patch(frame, region)
        if donor is None:
            _inpaint_region(frame, region, radius, cv2, np)
            continue
        _paste_feather(frame, region, donor, np)


def _neighbor_patch(frame, region: Region):
    """从水印内侧相邻位置裁一块同样大小的纹理。"""
    height, width = frame.shape[:2]
    x, y, box_w, box_h = region.x, region.y, region.w, region.h
    options = []
    if y >= box_h:
        options.append((y, frame[y - box_h : y, x : x + box_w]))
    if height - (y + box_h) >= box_h:
        options.append((height - (y + box_h), frame[y + box_h : y + 2 * box_h, x : x + box_w]))
    if x >= box_w:
        options.append((x, frame[y : y + box_h, x - box_w : x]))
    if width - (x + box_w) >= box_w:
        options.append((width - (x + box_w), frame[y : y + box_h, x + box_w : x + 2 * box_w]))
    if not options:
        return None
    patch = max(options, key=lambda item: item[0])[1]
    if patch.shape[0] != box_h or patch.shape[1] != box_w:
        return None
    return patch.copy()


def _paste_feather(frame, region: Region, donor, np) -> None:
    """贴上邻接纹理，靠画面内侧的边渐变，避免出现硬边。"""
    height, width = frame.shape[:2]
    x, y, box_w, box_h = region.x, region.y, region.w, region.h
    fade = max(6, min(10, min(box_w, box_h) // 4))
    alpha = np.ones((box_h, box_w), dtype="float32")
    ramp = np.linspace(0.0, 1.0, fade, dtype="float32")
    if y > 2 and box_h > fade:
        alpha[:fade, :] *= ramp[:, None]
    if y + box_h < height - 2 and box_h > fade:
        alpha[-fade:, :] *= ramp[::-1, None]
    if x > 2 and box_w > fade:
        alpha[:, :fade] *= ramp[None, :]
    if x + box_w < width - 2 and box_w > fade:
        alpha[:, -fade:] *= ramp[::-1][None, :]
    base = frame[y : y + box_h, x : x + box_w].astype("float32")
    donor_f = donor.astype("float32")
    donor_f += base.mean(axis=(0, 1)) - donor_f.mean(axis=(0, 1))
    frame[y : y + box_h, x : x + box_w] = np.clip(
        donor_f * alpha[..., None] + base * (1.0 - alpha[..., None]), 0, 255
    ).astype("uint8")


def _inpaint_region(frame, region: Region, radius: int, cv2, np) -> None:
    """旁边没有足够画面时，只修复水印这一小块。"""
    height, width = frame.shape[:2]
    context = 8
    x0 = max(0, region.x - context)
    y0 = max(0, region.y - context)
    x1 = min(width, region.x + region.w + context)
    y1 = min(height, region.y + region.h + context)
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return
    mask = np.zeros(crop.shape[:2], dtype="uint8")
    mx0 = max(0, region.x - x0)
    my0 = max(0, region.y - y0)
    mx1 = min(crop.shape[1], region.x + region.w - x0)
    my1 = min(crop.shape[0], region.y + region.h - y0)
    if mx1 - mx0 < 2 or my1 - my0 < 2:
        return
    mask[my0:my1, mx0:mx1] = 255
    filled = cv2.inpaint(crop, mask, radius, cv2.INPAINT_TELEA)
    soft = cv2.GaussianBlur(mask, (0, 0), 1.4)
    alpha = (soft.astype("float32") / 255.0)[..., None]
    blended = filled.astype("float32") * alpha + crop.astype("float32") * (1.0 - alpha)
    frame[y0:y1, x0:x1] = np.clip(blended, 0, 255).astype("uint8")


def _encode_timeout(meta: dict) -> int:
    duration = float(meta.get("duration") or 0)
    return int(max(300, min(3600, duration * 12 + 120)))


def _extract_video_text(video_path: Path) -> str:
    """可选：识别视频画面里的文字（较慢，仅在前端明确需要时调用）。"""
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


def _empty_result(input_payload: dict, message: str, method: str, status: str, extra: dict | None = None) -> dict:
    result = {
        "message": message,
        "status": status,
        "method": method,
        "mode": str(input_payload.get("watermark_mode") or "auto"),
        "algorithm": str(input_payload.get("watermark_method") or "delogo"),
        "regions": [],
        "detected_regions": [],
        "video_meta": {},
        "original_video_url": "",
        "processed_video_url": "",
        "download_url": "",
        "preview_url": "",
        "video_text": "",
        "source": input_payload,
    }
    result.update(extra or {})
    return result


def _public_url(path: Path) -> str:
    try:
        relative = path.relative_to(Path(settings.media_root))
    except ValueError:
        return ""
    return f"{settings.public_media_prefix}/{relative.as_posix()}"


def _stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
