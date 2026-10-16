import pytest

from app.workers.processors.subtitle import (
    _is_direct_video_url,
    extract_frame_for_selection,
    remove_subtitle,
)


def _write_sample_video_with_subtitle(path, width=480, height=854, frames=60):
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (width, height))
    assert writer.isOpened()

    bar_h = int(height * 0.12)
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
        frame = cv2.GaussianBlur(frame, (0, 0), 3)
        # 底部字幕条
        cv2.rectangle(frame, (0, height - bar_h), (width, height), (18, 18, 18), -1)
        cv2.putText(frame, "这是字幕文字", (20, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        writer.write(frame.astype("uint8"))
    writer.release()


def _setup(tmp_path, monkeypatch):
    from app.core.config import settings

    media_root = tmp_path / "media"
    (media_root / "uploads").mkdir(parents=True)
    monkeypatch.setattr(settings, "media_root", str(media_root))
    source = media_root / "uploads" / "sample.mp4"
    _write_sample_video_with_subtitle(source, 480, 854)
    return media_root, source


def test_is_direct_video_url():
    assert _is_direct_video_url("https://cdn.example.com/a.mp4")
    assert _is_direct_video_url("https://cdn.example.com/a.mov")
    assert not _is_direct_video_url("https://v.douyin.com/abcd/")
    assert not _is_direct_video_url("not a url")


def test_extract_frame_for_selection_local(tmp_path, monkeypatch):
    pytest.importorskip("cv2")
    pytest.importorskip("imageio_ffmpeg")

    media_root, source = _setup(tmp_path, monkeypatch)
    info = extract_frame_for_selection(str(source))

    assert info["status"] == "success", info.get("message")
    assert info["width"] == 480
    assert info["height"] == 854
    assert info["frame_url"]

    frame_path = media_root / info["frame_url"].replace("/media/", "", 1)
    assert frame_path.exists() and frame_path.stat().st_size > 0


def test_remove_subtitle_with_manual_region(tmp_path, monkeypatch):
    pytest.importorskip("cv2")
    pytest.importorskip("imageio_ffmpeg")

    media_root, source = _setup(tmp_path, monkeypatch)
    box = {"x": 0.0, "y": 0.88, "w": 1.0, "h": 0.12}
    result = remove_subtitle({"file_path": str(source), "subtitle_region": box, "task_id": "t1"})

    assert result["status"] == "success", result["message"]
    assert result["algorithm"] in ("delogo", "inpaint")
    assert result["regions"], "应至少返回一处字幕区域"

    output = media_root / result["processed_video_url"].replace("/media/", "", 1)
    assert output.exists() and output.stat().st_size > 0

    preview = media_root / result["preview_url"].replace("/media/", "", 1)
    assert preview.exists() and preview.stat().st_size > 0


def test_remove_subtitle_falls_back_to_bottom_band(tmp_path, monkeypatch):
    pytest.importorskip("cv2")
    pytest.importorskip("imageio_ffmpeg")

    media_root, source = _setup(tmp_path, monkeypatch)
    result = remove_subtitle({"file_path": str(source), "task_id": "t2"})

    assert result["status"] == "success", result["message"]
    region = result["regions"][0]
    # 兜底区域应落在画面底部（默认处理底部 12% 字幕带）
    assert region["y"] >= int(854 * 0.85)


def test_remove_subtitle_missing_source():
    result = remove_subtitle({"task_id": "x"})
    assert result["status"] == "failed"
    assert result["method"] == "missing_source"


def test_remove_subtitle_missing_local_file(tmp_path, monkeypatch):
    from app.core.config import settings

    media_root = tmp_path / "media"
    (media_root / "uploads").mkdir(parents=True)
    monkeypatch.setattr(settings, "media_root", str(media_root))

    result = remove_subtitle({"file_path": str(media_root / "uploads" / "nope.mp4"), "task_id": "x"})
    assert result["status"] == "failed"
    assert result["method"] == "download_failed"
