import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.api.tasks as task_api
from app.core.config import settings
from app.db import get_session
from app.main import app
from app.models import media_asset, quota, task, user


@pytest.fixture()
def client(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _ = (media_asset, quota, task, user)
    SQLModel.metadata.create_all(engine)
    original_media_root = settings.media_root
    settings.media_root = str(tmp_path / "media")
    enqueued_task_ids = []
    monkeypatch.setattr(task_api, "enqueue_task", enqueued_task_ids.append)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app), enqueued_task_ids
    app.dependency_overrides.clear()
    settings.media_root = original_media_root


def test_create_link_parse_task(client):
    client, enqueued_task_ids = client
    response = client.post("/api/tasks/link-parse", json={"url": "https://www.douyin.com/video/123"})

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "link_parse"
    assert body["status"] == "pending"
    assert body["progress"] == 0
    assert body["input_payload"]["url"] == "https://www.douyin.com/video/123"
    assert enqueued_task_ids == [body["id"]]


def test_create_file_process_task(client):
    client, enqueued_task_ids = client
    file_content = b"demo video"
    response = client.post(
        "/api/tasks/file-process",
        data={"process_type": "remove_watermark", "user_id": "user-1"},
        files={"file": ("demo.mp4", file_content, "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "remove_watermark"
    assert body["status"] == "pending"
    input_payload = body["input_payload"]
    assert input_payload["filename"] == "demo.mp4"
    assert input_payload["mime_type"] == "video/mp4"
    assert input_payload["size"] == len(file_content)

    upload_path = input_payload["file_path"]
    assert upload_path.endswith(".mp4")
    with open(upload_path, "rb") as saved_file:
        assert saved_file.read() == file_content
    assert enqueued_task_ids == [body["id"]]


def test_file_process_rejects_non_file_task_type(client):
    client, enqueued_task_ids = client
    response = client.post(
        "/api/tasks/file-process",
        data={"process_type": "link_parse"},
        files={"file": ("demo.txt", b"demo", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_process_type"
    assert enqueued_task_ids == []


def test_file_process_rejects_unknown_task_type(client):
    client, enqueued_task_ids = client
    response = client.post(
        "/api/tasks/file-process",
        data={"process_type": "unknown"},
        files={"file": ("demo.txt", b"demo", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_process_type"
    assert enqueued_task_ids == []


def test_create_video_generate_task(client):
    client, enqueued_task_ids = client
    response = client.post(
        "/api/tasks/video-generate",
        json={"image_asset_ids": ["asset-1"], "text": "hello", "template_id": "default", "user_id": "user-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "video_generate"
    assert body["status"] == "pending"
    assert body["input_payload"]["image_asset_ids"] == ["asset-1"]
    assert body["input_payload"]["text"] == "hello"
    assert "user_id" not in body["input_payload"]
    assert enqueued_task_ids == [body["id"]]


def test_create_video_watermark_task(client):
    client, enqueued_task_ids = client
    response = client.post(
        "/api/tasks/video-watermark",
        data={"mode": "auto", "method": "inpaint", "padding": "12", "user_id": "user-1"},
        files={"file": ("demo.mp4", b"demo", "video/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "video_watermark"
    assert body["status"] == "pending"
    input_payload = body["input_payload"]
    assert input_payload["filename"] == "demo.mp4"
    assert input_payload["watermark_mode"] == "auto"
    assert input_payload["watermark_method"] == "inpaint"
    assert input_payload["watermark_padding"] == 12
    assert "watermark_region" not in input_payload
    assert enqueued_task_ids == [body["id"]]


def test_create_video_watermark_task_with_manual_region(client):
    client, enqueued_task_ids = client
    response = client.post(
        "/api/tasks/video-watermark",
        data={"mode": "manual", "region": "bottom_right", "size": "medium"},
        files={"file": ("demo.mov", b"demo", "video/quicktime")},
    )

    assert response.status_code == 200
    input_payload = response.json()["input_payload"]
    assert input_payload["watermark_mode"] == "manual"
    assert input_payload["watermark_region"] == "bottom_right"
    assert input_payload["watermark_size"] == "medium"


def test_video_watermark_rejects_unknown_mode(client):
    client, enqueued_task_ids = client
    response = client.post(
        "/api/tasks/video-watermark",
        data={"mode": "magic"},
        files={"file": ("demo.mp4", b"demo", "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("invalid_options")
    assert enqueued_task_ids == []


def test_video_watermark_requires_region_in_manual_mode(client):
    client, enqueued_task_ids = client
    response = client.post(
        "/api/tasks/video-watermark",
        data={"mode": "manual"},
        files={"file": ("demo.mp4", b"demo", "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "manual_region_required"
    assert enqueued_task_ids == []


def test_video_watermark_rejects_non_video_suffix(client):
    client, enqueued_task_ids = client
    response = client.post(
        "/api/tasks/video-watermark",
        data={"mode": "auto"},
        files={"file": ("demo.gif", b"demo", "image/gif")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported_file_type"
    assert enqueued_task_ids == []


def test_video_watermark_rejects_invalid_box_json(client):
    client, enqueued_task_ids = client
    response = client.post(
        "/api/tasks/video-watermark",
        data={"mode": "manual", "region": "bottom_right", "box": "{bad json"},
        files={"file": ("demo.mp4", b"demo", "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_box"
    assert enqueued_task_ids == []


def test_get_missing_task_returns_404(client):
    client, enqueued_task_ids = client
    response = client.get("/api/tasks/missing-task")

    assert response.status_code == 404
    assert response.json()["detail"] == "task_not_found"
    assert enqueued_task_ids == []


def test_list_tasks_by_user_id(client):
    client, enqueued_task_ids = client
    client.post("/api/tasks/link-parse", json={"url": "https://www.douyin.com/video/123", "user_id": "user-1"})
    client.post("/api/tasks/link-parse", json={"url": "https://www.douyin.com/video/456", "user_id": "user-2"})

    response = client.get("/api/tasks", params={"user_id": "user-1"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["input_payload"]["url"] == "https://www.douyin.com/video/123"
    assert len(enqueued_task_ids) == 2
