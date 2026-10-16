import pytest

from app.workers.processors.watermark import remove_watermark
from app.workers.processors.watermark_detect import (
    Region,
    custom_region,
    expand_region,
    merge_overlapping,
    preset_region,
)


def test_preset_region_bottom_right_medium():
    region = preset_region("bottom_right", "medium", 720, 1280)

    assert region is not None
    assert region.source == "manual"
    # 右下角锚定：右边缘和下边缘贴住画面边界
    assert region.x + region.w == 720
    assert region.y + region.h == 1280
    assert region.w == int(round(0.14 * 720))
    assert region.h == int(round(0.042 * 1280))


def test_preset_region_supports_alias_and_scale():
    small = preset_region("右下角", "small", 720, 1280)
    large = preset_region("br", "large", 720, 1280)

    assert small is not None and large is not None
    assert small.w < preset_region("bottom_right", "medium", 720, 1280).w
    assert large.w > preset_region("bottom_right", "medium", 720, 1280).w
    assert large.x + large.w == 720


def test_preset_region_unknown_name_returns_none():
    assert preset_region("nowhere", "medium", 720, 1280) is None
    assert preset_region("", "medium", 720, 1280) is None


def test_custom_region_accepts_normalized_values():
    region = custom_region({"x": 0.5, "y": 0.9, "w": 0.25, "h": 0.08}, 720, 1280)

    assert region is not None
    assert (region.x, region.y, region.w, region.h) == (360, 1152, 180, 102)


def test_custom_region_accepts_pixel_values():
    region = custom_region({"x": 10, "y": 20, "w": 100, "h": 40}, 720, 1280)

    assert region is not None
    assert (region.x, region.y, region.w, region.h) == (10, 20, 100, 40)


def test_custom_region_rejects_invalid_values():
    assert custom_region({"x": "a", "y": 0.1, "w": 0.2, "h": 0.2}, 720, 1280) is None
    assert custom_region({"x": 0.1, "y": 0.1, "w": 0.0, "h": 0.0}, 720, 1280) is None
    assert custom_region({}, 720, 1280) is None


def test_expand_region_keeps_full_coverage_and_clamps():
    region = Region(x=0, y=0, w=50, h=30)
    expanded = expand_region(region, 200, 100, padding=10)

    # 贴边水印无法向外扩张，改为向内扩张，但最多让出 1px（delogo 需要 1px 有效边框）
    assert expanded.x <= region.x + 1
    assert expanded.y <= region.y + 1
    assert expanded.x + expanded.w >= region.x + region.w
    assert expanded.y + expanded.h >= region.y + region.h
    assert expanded.x >= 1
    assert expanded.y >= 1
    assert expanded.x + expanded.w <= 200 - 1
    assert expanded.y + expanded.h <= 100 - 1


def test_merge_overlapping_unifies_boxes():
    first = Region(x=0, y=0, w=50, h=40, confidence=0.6)
    second = Region(x=40, y=10, w=50, h=40, confidence=0.8)
    far = Region(x=500, y=500, w=30, h=30, confidence=0.7)

    merged = merge_overlapping([first, second, far])

    assert len(merged) == 2
    top = max(merged, key=lambda region: region.area)
    assert top.x == 0
    assert top.y == 0
    assert top.x + top.w == 90
    assert top.y + top.h == 50
    assert top.confidence == 0.8


def test_remove_watermark_rejects_non_video_file(tmp_path):
    missing = tmp_path / "demo.png"
    result = remove_watermark({"file_path": str(missing)})

    assert result["status"] == "unsupported"
    assert result["method"] == "unsupported_file_type"
    assert result["download_url"] == ""


def test_remove_watermark_reports_probe_failure_for_fake_video(tmp_path):
    fake = tmp_path / "demo.mp4"
    fake.write_bytes(b"not a real video")

    result = remove_watermark({"file_path": str(fake)})

    assert result["status"] == "failed"
    assert result["method"] == "probe_failed"


def _write_sample_video(path, width=480, height=854, frames=60):
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (width, height))
    assert writer.isOpened()

    for index in range(frames):
        t = index / frames
        yy, xx = np.mgrid[0:height, 0:width].astype("float32")
        frame = np.stack(
            [
                (np.sin(xx / 90 + t * 6) * 0.5 + 0.5) * 200,
                (np.cos(yy / 70 - t * 5) * 0.5 + 0.5) * 180,
                (np.sin((xx + yy) / 110 + t * 4) * 0.5 + 0.5) * 160,
            ],
            axis=-1,
        ).astype("float32")
        for k in range(3):
            cx = int((np.sin(t * 5 + k) * 0.4 + 0.5) * width)
            cy = int((np.cos(t * 4 + k * 1.7) * 0.4 + 0.5) * height)
            cv2.circle(frame, (cx, cy), 40 + k * 14, (30 + k * 40, 200 - k * 25, 120 + k * 20), -1)
        frame = cv2.GaussianBlur(frame, (0, 0), 3)

        badge = frame.copy()
        cv2.putText(badge, "AI", (width - 150, height - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 3, cv2.LINE_AA)
        frame = cv2.addWeighted(badge, 0.85, frame, 0.15, 0)

        writer.write(frame.astype("uint8"))
    writer.release()


def test_remove_watermark_detects_and_removes_corner_badge(tmp_path, monkeypatch):
    pytest.importorskip("cv2")
    pytest.importorskip("imageio_ffmpeg")

    from app.core.config import settings

    media_root = tmp_path / "media"
    (media_root / "uploads").mkdir(parents=True)
    monkeypatch.setattr(settings, "media_root", str(media_root))

    source = media_root / "uploads" / "sample.mp4"
    _write_sample_video(source)

    result = remove_watermark({"file_path": str(source), "task_id": "test-task"})

    assert result["status"] == "success", result["message"]
    assert result["mode"] == "auto"
    assert result["regions"], "应至少定位到一处水印区域"

    region = result["regions"][0]
    width, height = 480, 854
    assert region["x"] + region["w"] >= width * 0.6
    assert region["y"] + region["h"] >= height * 0.9

    output = media_root / result["processed_video_url"].replace("/media/", "", 1)
    assert output.exists() and output.stat().st_size > 0

    preview = media_root / result["preview_url"].replace("/media/", "", 1)
    assert preview.exists() and preview.stat().st_size > 0

    assert result["video_meta"]["width"] == width
    assert result["video_meta"]["height"] == height
    assert result["download_url"] == result["processed_video_url"]


def test_remove_watermark_uses_manual_region(tmp_path, monkeypatch):
    pytest.importorskip("cv2")
    pytest.importorskip("imageio_ffmpeg")

    from app.core.config import settings

    media_root = tmp_path / "media"
    (media_root / "uploads").mkdir(parents=True)
    monkeypatch.setattr(settings, "media_root", str(media_root))

    source = media_root / "uploads" / "sample.mp4"
    _write_sample_video(source)

    result = remove_watermark(
        {
            "file_path": str(source),
            "watermark_mode": "manual",
            "watermark_region": "bottom_right",
            "watermark_size": "medium",
        }
    )

    assert result["status"] == "success", result["message"]
    assert result["mode"] == "manual"
    assert result["regions"][0]["source"] == "manual"


def test_remove_watermark_falls_back_when_nothing_detected(tmp_path, monkeypatch):
    pytest.importorskip("cv2")
    pytest.importorskip("imageio_ffmpeg")

    from app.core.config import settings
    from app.workers.processors import watermark as watermark_module

    media_root = tmp_path / "media"
    (media_root / "uploads").mkdir(parents=True)
    monkeypatch.setattr(settings, "media_root", str(media_root))
    monkeypatch.setattr(watermark_module, "detect_watermark_regions", lambda *args, **kwargs: [])

    source = media_root / "uploads" / "sample.mp4"
    _write_sample_video(source)

    result = remove_watermark({"file_path": str(source)})

    assert result["status"] == "success"
    assert "兜底" in result["message"]
    assert result["regions"][0]["source"] == "manual"
