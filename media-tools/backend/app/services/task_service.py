import json
from datetime import UTC, datetime

from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select

from app.models.task import Task, TaskStatus, TaskType
from app.schemas.task import TaskResponse
from app.services.quota_service import QuotaService


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TaskService:
    def __init__(self, session: Session):
        self.session = session
        self.quota_service = QuotaService()

    def create_task(self, user_id: str, task_type: TaskType, input_payload: dict) -> Task:
        self.quota_service.assert_can_create_task(user_id=user_id, task_type=task_type)
        task = Task(
            user_id=user_id,
            type=task_type,
            status=TaskStatus.pending,
            progress=0,
            input_payload=json.dumps(jsonable_encoder(input_payload), ensure_ascii=False),
            result_payload="{}",
        )
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self.session.get(Task, task_id)

    def list_tasks(self, user_id: str) -> list[Task]:
        statement = select(Task).where(Task.user_id == user_id).order_by(Task.created_at.desc())
        return list(self.session.exec(statement))

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: int,
        result_payload: dict | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> Task:
        task = self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        task.status = status
        task.progress = progress
        task.updated_at = utc_now()
        if result_payload is not None:
            task.result_payload = json.dumps(jsonable_encoder(result_payload), ensure_ascii=False)
        task.error_code = error_code
        task.error_message = error_message
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task


def to_task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        type=task.type,
        status=task.status,
        progress=task.progress,
        input_payload=json.loads(task.input_payload),
        result_payload=json.loads(task.result_payload),
        error_code=task.error_code,
        error_message=task.error_message,
    )
