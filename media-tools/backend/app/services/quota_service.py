from app.models.task import TaskType


class QuotaService:
    def assert_can_create_task(self, user_id: str, task_type: TaskType) -> None:
        return None
