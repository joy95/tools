import json

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import media_asset, quota, task, user
from app.models.task import TaskStatus, TaskType
from app.services.task_service import TaskService, to_task_response
from app.workers.celery_app import celery_app
from app.workers.tasks import _run_task, dispatch_task


def test_celery_app_includes_worker_tasks():
    assert "app.workers.tasks" in celery_app.conf.include


def test_run_link_parse_task(monkeypatch):
    from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork

    def fake_extract(url: str, raw_text: str = ""):
        return ExtractedWork(
            platform="douyin",
            source_url=url,
            media_type="video",
            caption="平台文案",
            assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/a.mp4", mime_type="video/mp4")],
            parse_method="public_page",
        )

    def fake_download(task_id: str, work):
        return {
            "platform": work.platform,
            "source_url": work.source_url,
            "media_type": work.media_type,
            "caption": work.caption,
            "assets": [
                {
                    "type": "video",
                    "source_url": "https://cdn.example.com/a.mp4",
                    "local_url": "/media/link_assets/test-task/video_1.mp4",
                    "mime_type": "video/mp4",
                }
            ],
            "parse_method": work.parse_method,
            "download_status": "success",
        }

    def fake_speech(result):
        return {**result, "speech_status": "success", "speech_text": "这是口播文案"}

    monkeypatch.setattr("app.workers.tasks.extract_link_work", fake_extract)
    monkeypatch.setattr("app.workers.tasks.download_work_assets", fake_download)
    monkeypatch.setattr("app.workers.tasks.enrich_result_with_speech", fake_speech)

    result = _run_task(TaskType.link_parse, {"url": "https://www.douyin.com/video/123", "raw_text": "分享文案", "task_id": "test-task"})

    assert result["platform"] == "douyin"
    assert result["media_type"] == "video"
    assert result["caption"] == "平台文案"
    assert result["assets"][0]["local_url"] == "/media/link_assets/test-task/video_1.mp4"
    assert result["download_status"] == "success"
    assert result["speech_status"] == "success"
    assert result["speech_text"] == "这是口播文案"


def test_run_basic_processor_tasks():
    payload = {"file_path": "/tmp/demo.mp4", "template_id": "default"}

    assert _run_task(TaskType.remove_watermark, payload)["method"] == "unsupported_file_type"
    assert _run_task(TaskType.video_watermark, payload)["method"] == "unsupported_file_type"
    subtitle_result = _run_task(TaskType.remove_subtitle, payload)
    assert subtitle_result["status"] == "failed"
    assert subtitle_result["method"] == "download_failed"
    assert _run_task(TaskType.ocr_extract, payload)["text"] == ""
    assert _run_task(TaskType.video_generate, payload)["template_id"] == "default"


def test_dispatch_task_updates_task_success(monkeypatch):
    from app.parsers.link_extractors.base import ExtractedWork

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _ = (media_asset, quota, task, user)
    SQLModel.metadata.create_all(engine)

    import app.workers.tasks as worker_tasks

    monkeypatch.setattr(worker_tasks, "engine", engine)
    monkeypatch.setattr(
        worker_tasks,
        "extract_link_work",
        lambda url, raw_text="": ExtractedWork(platform="douyin", source_url=url, media_type="video", parse_method="public_page"),
    )
    monkeypatch.setattr(
        worker_tasks,
        "download_work_assets",
        lambda task_id, work: {
            "platform": work.platform,
            "source_url": work.source_url,
            "media_type": work.media_type,
            "assets": [],
            "parse_method": work.parse_method,
            "download_status": "empty",
            "task_id": task_id,
        },
    )
    monkeypatch.setattr(
        worker_tasks,
        "enrich_result_with_speech",
        lambda result: {**result, "speech_status": "skipped", "speech_text": "", "speech_message": "当前作品无需提取口播文案"},
    )

    with Session(engine) as session:
        service = TaskService(session)
        created_task = service.create_task(
            user_id="anonymous",
            task_type=TaskType.link_parse,
            input_payload={"url": "https://www.douyin.com/video/123", "task_id": "stale-task-id"},
        )
        task_id = created_task.id

    dispatch_task.run(task_id)

    with Session(engine) as session:
        response = to_task_response(TaskService(session).get_task(task_id))

    assert response.status == TaskStatus.success
    assert response.progress == 100
    assert response.result_payload["platform"] == "douyin"
    assert response.result_payload["source_url"] == "https://www.douyin.com/video/123"
    assert response.result_payload["task_id"] == task_id
    assert response.result_payload["speech_status"] == "skipped"


def test_dispatch_task_keeps_success_when_speech_fails(monkeypatch):
    from app.parsers.link_extractors.base import ExtractedWork

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _ = (media_asset, quota, task, user)
    SQLModel.metadata.create_all(engine)

    import app.workers.tasks as worker_tasks

    monkeypatch.setattr(worker_tasks, "engine", engine)
    monkeypatch.setattr(
        worker_tasks,
        "extract_link_work",
        lambda url, raw_text="": ExtractedWork(platform="douyin", source_url=url, media_type="video", parse_method="public_page"),
    )
    monkeypatch.setattr(
        worker_tasks,
        "download_work_assets",
        lambda task_id, work: {
            "platform": work.platform,
            "source_url": work.source_url,
            "media_type": work.media_type,
            "assets": [],
            "parse_method": work.parse_method,
            "download_status": "success",
            "task_id": task_id,
        },
    )
    monkeypatch.setattr(
        worker_tasks,
        "enrich_result_with_speech",
        lambda result: {**result, "speech_status": "failed", "speech_text": "", "speech_message": "口播识别失败"},
    )

    with Session(engine) as session:
        service = TaskService(session)
        created_task = service.create_task(
            user_id="anonymous",
            task_type=TaskType.link_parse,
            input_payload={"url": "https://www.douyin.com/video/123"},
        )
        task_id = created_task.id

    dispatch_task.run(task_id)

    with Session(engine) as session:
        response = to_task_response(TaskService(session).get_task(task_id))

    assert response.status == TaskStatus.success
    assert response.result_payload["download_status"] == "success"
    assert response.result_payload["speech_status"] == "failed"
    assert response.result_payload["speech_message"] == "口播识别失败"


def test_dispatch_task_updates_task_failure(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _ = (media_asset, quota, task, user)
    SQLModel.metadata.create_all(engine)

    import app.workers.tasks as worker_tasks

    monkeypatch.setattr(worker_tasks, "engine", engine)

    with Session(engine) as session:
        service = TaskService(session)
        created_task = service.create_task(
            user_id="anonymous",
            task_type=TaskType.link_parse,
            input_payload={"url": "https://unsupported.example/item/123"},
        )
        task_id = created_task.id

    with pytest.raises(ValueError, match="unsupported_platform"):
        dispatch_task.run(task_id)

    with Session(engine) as session:
        response = to_task_response(TaskService(session).get_task(task_id))

    assert response.status == TaskStatus.failed
    assert response.progress == 100
    assert response.error_code == "ValueError"
    assert response.error_message == "unsupported_platform"


def test_dispatch_task_uses_link_extraction_error_code(monkeypatch):
    from app.parsers.link_extractors.base import LinkExtractionError

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _ = (media_asset, quota, task, user)
    SQLModel.metadata.create_all(engine)

    import app.workers.tasks as worker_tasks

    def raise_link_error(url: str, raw_text: str = ""):
        raise LinkExtractionError("cookie_expired_or_required", "需要 cookie")

    monkeypatch.setattr(worker_tasks, "engine", engine)
    monkeypatch.setattr(worker_tasks, "extract_link_work", raise_link_error)

    with Session(engine) as session:
        service = TaskService(session)
        created_task = service.create_task(
            user_id="anonymous",
            task_type=TaskType.link_parse,
            input_payload={"url": "https://www.douyin.com/video/123"},
        )
        task_id = created_task.id

    with pytest.raises(LinkExtractionError, match="需要 cookie"):
        dispatch_task.run(task_id)

    with Session(engine) as session:
        response = to_task_response(TaskService(session).get_task(task_id))

    assert response.status == TaskStatus.failed
    assert response.progress == 100
    assert response.error_code == "cookie_expired_or_required"
    assert "需要 cookie" in response.error_message


def test_dispatch_task_marks_bad_input_payload_failed_and_raises(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _ = (media_asset, quota, task, user)
    SQLModel.metadata.create_all(engine)

    import app.workers.tasks as worker_tasks

    monkeypatch.setattr(worker_tasks, "engine", engine)

    with Session(engine) as session:
        service = TaskService(session)
        created_task = service.create_task(
            user_id="anonymous",
            task_type=TaskType.link_parse,
            input_payload={"url": "https://www.douyin.com/video/123"},
        )
        task_id = created_task.id
        created_task.input_payload = "{bad json"
        session.add(created_task)
        session.commit()

    with pytest.raises(json.JSONDecodeError):
        dispatch_task.run(task_id)

    with Session(engine) as session:
        response = TaskService(session).get_task(task_id)

    assert response.status == TaskStatus.failed
    assert response.progress == 100
    assert response.error_code == "JSONDecodeError"
