import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.task import TaskStatus, TaskType
from app.schemas.task import FileProcessRequest, LinkParseRequest
from app.services.task_service import TaskService, to_task_response


def test_task_service_creates_updates_and_serializes_task():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        service = TaskService(session)
        task = service.create_task(
            user_id="anonymous",
            task_type=TaskType.link_parse,
            input_payload={"url": "https://example.com", "title": "示例标题"},
        )
        original_updated_at = task.updated_at

        assert task.status == TaskStatus.pending
        assert task.input_payload == '{"url": "https://example.com", "title": "示例标题"}'

        updated_task = service.update_task_status(
            task_id=task.id,
            status=TaskStatus.success,
            progress=100,
            result_payload={"message": "处理完成"},
        )
        response = to_task_response(updated_task)

    assert updated_task.updated_at != original_updated_at
    assert updated_task.updated_at.tzinfo is None
    assert response.id == task.id
    assert response.status == TaskStatus.success
    assert response.progress == 100
    assert response.input_payload == {"url": "https://example.com", "title": "示例标题"}
    assert response.result_payload == {"message": "处理完成"}


def test_task_service_encodes_http_url_payloads():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    request = LinkParseRequest(url="https://example.com/video/123")

    with Session(engine) as session:
        service = TaskService(session)
        task = service.create_task(
            user_id=request.user_id,
            task_type=TaskType.link_parse,
            input_payload=request.model_dump(),
        )
        response = to_task_response(task)

    assert response.input_payload["url"] == "https://example.com/video/123"


def test_file_process_request_rejects_non_file_task_types():
    with pytest.raises(ValueError):
        FileProcessRequest(process_type=TaskType.link_parse)
