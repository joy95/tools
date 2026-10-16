"""AI 生成视频水印的自动定位与区域工具。

AI 生成视频（即梦、可灵、豆包、通义万相、Sora、Runway 等）的显式标识，
绝大多数是**固定在画面某个角落的文字或角标**（按《人工智能生成合成内容标识办法》，
国内平台的合成内容必须带显式标识）。这类水印有两个可判别特征：

1. **时域稳定性** —— 同一位置像素在整段视频里几乎不变，标准差远低于画面平均运动量；
2. **结构显著性** —— 水印是文字或图标，局部存在明显的高频边缘。

把两者求交，再限制在画面四周的「角标带」内，即可稳定框出水印区域；
纯静止画面（几乎没有运动）会失去第一判据，此时返回空结果，由调用方走兜底策略。
"""

from __future__ import annotations

from dataclasses import dataclass

# 降采样边长：太小会把小字水印抹平，太大会拖慢检测。480 在实测中兼顾两者。
TARGET_MAX_SIDE = 480
MIN_FRAMES = 6
MIN_AREA_RATIO = 0.0004
MAX_AREA_RATIO = 0.20
DEFAULT_ZONE_RATIO = 0.34
STRUCTURE_FLOOR = 4.5

# 预设区域：归一化宽高 + 锚定角，缩放大小时保持贴边。
REGION_PRESETS: dict[str, dict] = {
    "bottom_right": {"anchor_x": "right", "anchor_y": "bottom", "w": 0.14, "h": 0.042},
    "bottom_left": {"anchor_x": "left", "anchor_y": "bottom", "w": 0.14, "h": 0.042},
    "top_right": {"anchor_x": "right", "anchor_y": "top", "w": 0.14, "h": 0.04},
    "top_left": {"anchor_x": "left", "anchor_y": "top", "w": 0.14, "h": 0.04},
    "bottom_center": {"anchor_x": "center", "anchor_y": "bottom", "w": 0.28, "h": 0.042},
    "top_center": {"anchor_x": "center", "anchor_y": "top", "w": 0.28, "h": 0.04},
}

REGION_ALIASES = {
    "br": "bottom_right",
    "右下": "bottom_right",
    "右下角": "bottom_right",
    "bl": "bottom_left",
    "左下": "bottom_left",
    "左下角": "bottom_left",
    "tr": "top_right",
    "右上": "top_right",
    "右上角": "top_right",
    "tl": "top_left",
    "左上": "top_left",
    "左上角": "top_left",
    "bc": "bottom_center",
    "底部中间": "bottom_center",
    "tc": "top_center",
    "顶部中间": "top_center",
}

SIZE_SCALES = {"small": 0.65, "medium": 1.0, "large": 1.45}

# 自动检测失败时的兜底区域：国内 AI 平台角标以右下角为主。
DEFAULT_FALLBACK_REGIONS = ("bottom_right",)


@dataclass
class Region:
    x: int
    y: int
    w: int
    h: int
    confidence: float = 0.0
    source: str = "auto"

    @property
    def area(self) -> int:
        return self.w * self.h

    def as_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "confidence": round(float(self.confidence), 3),
            "source": self.source,
        }


def probe_video(video_path) -> dict:
    """读取视频基础信息，供前端展示与区域换算使用。"""
    try:
        import cv2
    except ImportError:
        return {}

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return {}

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    capture.release()

    if width <= 0 or height <= 0:
        return {}

    return {
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "frame_count": frame_count,
        "duration": round(frame_count / fps, 2) if fps > 0 else 0,
    }


def detect_watermark_regions(
    video_path,
    sample_count: int = 24,
    max_regions: int = 4,
    zone_ratio: float = DEFAULT_ZONE_RATIO,
) -> list[Region]:
    """检测固定的水印/角标区域，返回原图坐标系下的区域列表。"""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return []

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if width <= 0 or height <= 0:
        capture.release()
        return []

    scale = min(1.0, TARGET_MAX_SIDE / max(width, height))
    small_w = max(48, int(width * scale))
    small_h = max(48, int(height * scale))

    grays: list = []
    for index in _sample_indexes(frame_count, sample_count):
        if frame_count > 0:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (small_w, small_h), interpolation=cv2.INTER_AREA)
        grays.append(gray.astype("float32"))
    capture.release()

    if len(grays) < MIN_FRAMES:
        return []

    stack = np.stack(grays, axis=0)
    median = np.median(stack, axis=0)
    deviation = np.std(stack, axis=0)

    motion = float(np.median(deviation))
    static_threshold = max(2.0, motion * 0.4)

    smooth = cv2.GaussianBlur(median, (0, 0), sigmaX=4)
    structure = cv2.absdiff(median, smooth)
    structure_threshold = float(np.clip(np.percentile(structure, 99) * 0.35, STRUCTURE_FLOOR, 28.0))

    candidate = ((deviation < static_threshold) & (structure > structure_threshold)).astype("uint8") * 255
    candidate = cv2.bitwise_and(candidate, _zone_mask(small_w, small_h, zone_ratio))
    candidate = cv2.morphologyEx(
        candidate, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 3)), iterations=1
    )
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))

    total_pixels = small_w * small_h
    found: list[Region] = []
    component_count, _, stats, _ = cv2.connectedComponentsWithStats(candidate, connectivity=8)

    for index in range(1, component_count):
        x, y, box_w, box_h, area = (int(value) for value in stats[index])
        if box_w < 6 or box_h < 5:
            continue
        area_ratio = area / total_pixels
        if area_ratio < MIN_AREA_RATIO or area_ratio > MAX_AREA_RATIO:
            continue
        if area / float(box_w * box_h) < 0.06:
            continue

        box_mask = candidate[y : y + box_h, x : x + box_w] > 0
        static_score = 1.0 - min(1.0, float(deviation[y : y + box_h, x : x + box_w][box_mask].mean()) / static_threshold)
        structure_score = min(
            1.0, float(structure[y : y + box_h, x : x + box_w][box_mask].mean()) / (structure_threshold * 2)
        )
        confidence = max(0.0, min(1.0, 0.55 * static_score + 0.45 * structure_score))
        if confidence < 0.25:
            continue

        found.append(Region(x=x, y=y, w=box_w, h=box_h, confidence=confidence, source="auto"))

    if not found:
        return []

    merged = _merge_regions(found)
    merged.sort(key=lambda region: (region.confidence, region.area), reverse=True)

    ratio_x = width / small_w
    ratio_y = height / small_h
    results: list[Region] = []
    for region in merged[:max_regions]:
        results.append(
            Region(
                x=int(round(region.x * ratio_x)),
                y=int(round(region.y * ratio_y)),
                w=int(round(region.w * ratio_x)),
                h=int(round(region.h * ratio_y)),
                confidence=region.confidence,
                source="auto",
            )
        )
    return results


def preset_region(name: str, size: str, width: int, height: int) -> Region | None:
    """把预设名称 + 尺寸档位换算成实际像素区域。"""
    key = REGION_ALIASES.get(str(name or "").strip().lower(), str(name or "").strip().lower())
    preset = REGION_PRESETS.get(key)
    if preset is None:
        return None

    scale = SIZE_SCALES.get(str(size or "medium").strip().lower(), 1.0)
    box_w = min(1.0, preset["w"] * scale)
    box_h = min(1.0, preset["h"] * scale)

    if preset["anchor_x"] == "right":
        x_ratio = 1.0 - box_w
    elif preset["anchor_x"] == "center":
        x_ratio = (1.0 - box_w) / 2
    else:
        x_ratio = 0.0

    y_ratio = (1.0 - box_h) if preset["anchor_y"] == "bottom" else 0.0

    return Region(
        x=int(round(x_ratio * width)),
        y=int(round(y_ratio * height)),
        w=max(2, int(round(box_w * width))),
        h=max(2, int(round(box_h * height))),
        confidence=0.5,
        source="manual",
    )


def custom_region(values: dict, width: int, height: int) -> Region | None:
    """解析用户自定义区域，宽高缺省时按归一化比例处理。"""
    try:
        x = float(values.get("x"))
        y = float(values.get("y"))
        box_w = float(values.get("w"))
        box_h = float(values.get("h"))
    except (TypeError, ValueError):
        return None

    if max(abs(x), abs(y), abs(box_w), abs(box_h)) <= 1.0:
        x, box_w = x * width, box_w * width
        y, box_h = y * height, box_h * height

    if box_w < 4 or box_h < 4:
        return None

    return Region(
        x=int(round(x)),
        y=int(round(y)),
        w=int(round(box_w)),
        h=int(round(box_h)),
        confidence=0.5,
        source="manual",
    )


def tighten_region(region: Region, width: int, height: int, max_w_ratio: float = 0.16, max_h_ratio: float = 0.05) -> Region:
    """把过大的检测框收回到贴边的小范围，避免修掉周围画面。"""
    max_w = max(8, int(round(width * max_w_ratio)))
    max_h = max(8, int(round(height * max_h_ratio)))
    box_w = min(region.w, max_w)
    box_h = min(region.h, max_h)
    if region.x <= 2:
        x = region.x
    elif region.x + region.w >= width - 2:
        x = region.x + region.w - box_w
    else:
        x = region.x + (region.w - box_w) // 2
    if region.y <= 2:
        y = region.y
    elif region.y + region.h >= height - 2:
        y = region.y + region.h - box_h
    else:
        y = region.y + (region.h - box_h) // 2
    return Region(x=x, y=y, w=box_w, h=box_h, confidence=region.confidence, source=region.source)


def expand_region(region: Region, width: int, height: int, padding: int) -> Region:
    """向外扩张 padding，同时保证仍然完整覆盖原区域且不越界。

    ffmpeg 的 delogo 会用区域外一圈像素做插值，因此需要留出干净边框；
    贴边水印无法向外扩张时，改为向画面内侧扩张。
    """
    left = max(1, min(region.x - padding, region.x))
    top = max(1, min(region.y - padding, region.y))
    right = min(width - 1, max(region.x + region.w + padding, region.x + region.w))
    bottom = min(height - 1, max(region.y + region.h + padding, region.y + region.h))
    return Region(x=left, y=top, w=max(2, right - left), h=max(2, bottom - top), confidence=region.confidence, source=region.source)


def merge_overlapping(regions: list[Region], padding: int = 4) -> list[Region]:
    """合并互相重叠的区域，避免 delogo 在重叠区域上互相干扰。"""
    return _merge_regions(regions, padding)


def render_region_preview(video_path, regions: list[Region], output_path, max_width: int = 720) -> bool:
    """抽一帧并把区域画上去，生成预览图，方便用户确认水印位置。"""
    try:
        import cv2
    except ImportError:
        return False

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return False

    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count > 0:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_count * 0.2))
    ok, frame = capture.read()
    if not ok:
        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, frame = capture.read()
    capture.release()
    if not ok:
        return False

    original_width = int(frame.shape[1])
    frame = _fit_width(frame, max_width)
    scale = frame.shape[1] / max(1, original_width)

    overlay = frame.copy()
    for region in regions:
        top_left = (int(region.x * scale), int(region.y * scale))
        bottom_right = (int((region.x + region.w) * scale), int((region.y + region.h) * scale))
        cv2.rectangle(overlay, top_left, bottom_right, (75, 180, 60), thickness=-1)
    cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

    for region in regions:
        top_left = (int(region.x * scale), int(region.y * scale))
        bottom_right = (int((region.x + region.w) * scale), int((region.y + region.h) * scale))
        cv2.rectangle(frame, top_left, bottom_right, (75, 180, 60), thickness=3)

    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    if not ok:
        return False

    from pathlib import Path

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(buffer.tobytes())
    return True


def _fit_width(frame, max_width: int):
    import cv2

    if frame.shape[1] <= max_width:
        return frame
    ratio = max_width / frame.shape[1]
    return cv2.resize(frame, (max_width, max(1, int(frame.shape[0] * ratio))), interpolation=cv2.INTER_AREA)


def _sample_indexes(frame_count: int, sample_count: int) -> list[int]:
    if frame_count <= 0:
        return list(range(sample_count))

    lower = int(frame_count * 0.03)
    upper = max(lower + 1, int(frame_count * 0.97))
    count = max(MIN_FRAMES, min(sample_count, upper - lower))
    step = max(1, (upper - lower) // count)
    return list(range(lower, upper, step))[:sample_count]


def _zone_mask(width: int, height: int, ratio: float):
    import numpy as np

    mask = np.zeros((height, width), dtype="uint8")
    band_w = max(8, int(width * ratio))
    band_h = max(8, int(height * ratio))
    mask[:band_h, :] = 255
    mask[height - band_h :, :] = 255
    mask[:, :band_w] = 255
    mask[:, width - band_w :] = 255
    return mask


def _merge_regions(regions: list[Region], padding: int = 4) -> list[Region]:
    merged: list[Region] = []
    for region in sorted(regions, key=lambda item: item.area, reverse=True):
        merged.append(region)

    changed = True
    while changed:
        changed = False
        result: list[Region] = []
        for region in merged:
            for index, kept in enumerate(result):
                if _touches(kept, region, padding):
                    result[index] = Region(
                        x=min(kept.x, region.x),
                        y=min(kept.y, region.y),
                        w=max(kept.x + kept.w, region.x + region.w) - min(kept.x, region.x),
                        h=max(kept.y + kept.h, region.y + region.h) - min(kept.y, region.y),
                        confidence=max(kept.confidence, region.confidence),
                        source=kept.source if kept.source == region.source else "mixed",
                    )
                    changed = True
                    break
            else:
                result.append(region)
        merged = result
    return merged


def _touches(first: Region, second: Region, padding: int) -> bool:
    return not (
        first.x - padding > second.x + second.w
        or second.x - padding > first.x + first.w
        or first.y - padding > second.y + second.h
        or second.y - padding > first.y + first.h
    )
