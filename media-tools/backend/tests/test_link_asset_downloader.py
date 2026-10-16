from pathlib import Path

import pytest

from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork
from app.workers.processors.link_assets import download_work_assets


class FakeResponse:
    def __init__(self, body: bytes, content_type: str, stream_error: Exception | None = None):
        self.body = body
        self.headers = {"content-type": content_type}
        self.stream_error = stream_error

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int):
        yield self.body
        if self.stream_error:
            raise self.stream_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_download_work_assets_video(monkeypatch, tmp_path):
    work = ExtractedWork(
        platform="douyin",
        source_url="https://www.douyin.com/video/123",
        media_type="video",
        caption="文案",
        assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/a.mp4", mime_type="video/mp4")],
        parse_method="public_page",
    )

    monkeypatch.setattr("app.workers.processors.link_assets.requests.get", lambda *args, **kwargs: FakeResponse(b"video", "video/mp4"))
    monkeypatch.setattr("app.workers.processors.link_assets.settings.media_root", str(tmp_path))

    result = download_work_assets("task-1", work)

    assert result["assets"][0]["local_url"] == "/media/link_assets/task-1/video_1.mp4"
    assert (tmp_path / "link_assets" / "task-1" / "video_1.mp4").read_bytes() == b"video"
    assert result["download_status"] == "success"


def test_download_work_assets_images(monkeypatch, tmp_path):
    work = ExtractedWork(
        platform="xiaohongshu",
        source_url="https://www.xiaohongshu.com/explore/123",
        media_type="image",
        caption="文案",
        assets=[
            ExtractedAsset(type="image", source_url="https://cdn.example.com/a.jpg", mime_type="image/jpeg"),
            ExtractedAsset(type="image", source_url="https://cdn.example.com/b.png", mime_type="image/png"),
        ],
        parse_method="public_page",
    )

    monkeypatch.setattr("app.workers.processors.link_assets.requests.get", lambda *args, **kwargs: FakeResponse(b"image", "image/jpeg"))
    monkeypatch.setattr("app.workers.processors.link_assets.settings.media_root", str(tmp_path))

    result = download_work_assets("task-2", work)

    assert [asset["type"] for asset in result["assets"]] == ["image", "image"]
    assert result["assets"][0]["local_url"] == "/media/link_assets/task-2/image_1.jpg"
    assert result["assets"][1]["local_url"] == "/media/link_assets/task-2/image_2.png"


def test_download_work_assets_rejects_unsafe_task_id(monkeypatch, tmp_path):
    work = ExtractedWork(
        platform="douyin",
        source_url="https://www.douyin.com/video/123",
        media_type="video",
        assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/a.mp4", mime_type="video/mp4")],
        parse_method="public_page",
    )

    monkeypatch.setattr("app.workers.processors.link_assets.requests.get", lambda *args, **kwargs: FakeResponse(b"video", "video/mp4"))
    monkeypatch.setattr("app.workers.processors.link_assets.settings.media_root", str(tmp_path))

    with pytest.raises(ValueError, match="task_id"):
        download_work_assets("../escape", work)

    assert not (tmp_path.parent / "escape").exists()


def test_download_work_assets_uses_response_content_type_for_signed_image(monkeypatch, tmp_path):
    work = ExtractedWork(
        platform="xiaohongshu",
        source_url="https://www.xiaohongshu.com/explore/123",
        media_type="image",
        assets=[ExtractedAsset(type="image", source_url="https://cdn.example.com/resource?token=abc")],
        parse_method="public_page",
    )

    monkeypatch.setattr("app.workers.processors.link_assets.requests.get", lambda *args, **kwargs: FakeResponse(b"image", "image/png"))
    monkeypatch.setattr("app.workers.processors.link_assets.settings.media_root", str(tmp_path))

    result = download_work_assets("task-3", work)

    assert result["assets"][0]["local_url"] == "/media/link_assets/task-3/image_1.png"
    assert result["assets"][0]["mime_type"] == "image/png"
    assert (tmp_path / "link_assets" / "task-3" / "image_1.png").read_bytes() == b"image"


def test_download_work_assets_normalizes_m3u8_content_type(monkeypatch, tmp_path):
    work = ExtractedWork(
        platform="douyin",
        source_url="https://www.douyin.com/video/123",
        media_type="video",
        assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/playlist")],
        parse_method="public_page",
    )

    monkeypatch.setattr(
        "app.workers.processors.link_assets.requests.get",
        lambda *args, **kwargs: FakeResponse(b"#EXTM3U", "application/x-mpegURL; charset=utf-8"),
    )
    monkeypatch.setattr("app.workers.processors.link_assets.settings.media_root", str(tmp_path))

    result = download_work_assets("task-4", work)

    assert result["assets"][0]["local_url"] == "/media/link_assets/task-4/video_1.m3u8"
    assert result["assets"][0]["mime_type"] == "application/vnd.apple.mpegurl"


def test_download_work_assets_cleans_partial_file_on_stream_error(monkeypatch, tmp_path):
    work = ExtractedWork(
        platform="douyin",
        source_url="https://www.douyin.com/video/123",
        media_type="video",
        assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/a.mp4", mime_type="video/mp4")],
        parse_method="public_page",
    )

    monkeypatch.setattr(
        "app.workers.processors.link_assets.requests.get",
        lambda *args, **kwargs: FakeResponse(b"partial", "video/mp4", RuntimeError("stream broken")),
    )
    monkeypatch.setattr("app.workers.processors.link_assets.settings.media_root", str(tmp_path))

    with pytest.raises(RuntimeError, match="stream broken"):
        download_work_assets("task-5", work)

    target_dir = tmp_path / "link_assets" / "task-5"
    assert not (target_dir / "video_1.mp4").exists()
    assert not list(target_dir.glob("*.part"))


def test_download_work_assets_supports_relative_media_root(monkeypatch, tmp_path):
    work = ExtractedWork(
        platform="douyin",
        source_url="https://www.douyin.com/video/123",
        media_type="video",
        assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/a.mp4", mime_type="video/mp4")],
        parse_method="public_page",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app.workers.processors.link_assets.requests.get", lambda *args, **kwargs: FakeResponse(b"video", "video/mp4"))
    monkeypatch.setattr("app.workers.processors.link_assets.settings.media_root", "./media")

    result = download_work_assets("task-6", work)

    assert result["assets"][0]["local_url"] == "/media/link_assets/task-6/video_1.mp4"
    assert (tmp_path / "media" / "link_assets" / "task-6" / "video_1.mp4").read_bytes() == b"video"
