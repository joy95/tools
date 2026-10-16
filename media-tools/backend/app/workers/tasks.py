import json

from sqlmodel import Session

from app.db import engine
from app.models.task import TaskStatus, TaskType
from app.parsers.link_extractors.registry import extract_link_work
from app.services.task_service import TaskService
from app.workers.celery_app import celery_app
from app.workers.processors.link_assets import download_work_assets
from app.workers.processors.ocr import extract_text
from app.workers.processors.speech import enrich_result_with_speech
from app.workers.processors.subtitle import remove_subtitle
from app.workers.processors.video_generate import generate_video
from app.workers.processors.watermark import remove_watermark


@celery_app.task
def dispatch_task(task_id: str) -> None:
    with Session(engine) as session:
        service = TaskService(session)
        task = service.get_task(task_id)
        if task is None:
            return

        service.update_task_status(task_id, TaskStatus.running, 10)

        try:
            input_payload = json.loads(task.input_payload)
            input_payload["task_id"] = task_id
            result = _run_task(task.type, input_payload)
            service.update_task_status(task_id, TaskStatus.success, 100, result_payload=result)
        except Exception as exc:
            service.update_task_status(
                task_id,
                TaskStatus.failed,
                100,
                error_code=getattr(exc, "code", exc.__class__.__name__),
                error_message=str(exc),
            )
            raise


def _run_task(task_type: TaskType, input_payload: dict) -> dict:
    if task_type == TaskType.link_parse:
        work = extract_link_work(input_payload["url"], input_payload.get("raw_text", ""))
        result = download_work_assets(input_payload.get("task_id", "preview"), work)
        return enrich_result_with_speech(result)
    if task_type in {TaskType.remove_watermark, TaskType.video_watermark}:
        return remove_watermark(input_payload)
    if task_type == TaskType.remove_subtitle:
        return remove_subtitle(input_payload)
    if task_type == TaskType.ocr_extract:
        return extract_text(input_payload)
    if task_type == TaskType.video_generate:
        return generate_video(input_payload)
    raise ValueError(f"Unsupported task type: {task_type}")
