import json
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from app.core.config import settings
from app.db import get_session
from app.models.task import TaskType
from app.schemas.task import (
    LinkParseRequest,
    SubtitleFrameRequest,
    SubtitleRemoveRequest,
    TaskResponse,
    VideoGenerateRequest,
    VideoWatermarkOptions,
)
from app.services.task_service import TaskService, to_task_response
from app.workers.processors.watermark import VIDEO_SUFFIXES


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def enqueue_task(task_id: str) -> None:
    try:
        from app.workers.tasks import dispatch_task
    except ModuleNotFoundError as exc:
        if exc.name != "app.workers.tasks":
            raise
        return

    dispatch_task.delay(task_id)


@router.post("/link-parse", response_model=TaskResponse)
def create_link_parse_task(payload: LinkParseRequest, session: Session = Depends(get_session)):
    service = TaskService(session)
    task = service.create_task(
        user_id=payload.user_id,
        task_type=TaskType.link_parse,
        input_payload={"url": str(payload.url), "raw_text": payload.raw_text or ""},
    )
    enqueue_task(task.id)
    return to_task_response(task)


@router.post("/file-process", response_model=TaskResponse)
def create_file_process_task(
    process_type: str = Form(...),
    file: UploadFile = File(...),
    user_id: str = Form("anonymous"),
    session: Session = Depends(get_session),
):
    task_type = _parse_file_process_type(process_type)
    if task_type is None:
        raise HTTPException(status_code=400, detail="invalid_process_type")

    file_payload = _save_upload_file(file)
    service = TaskService(session)
    task = service.create_task(
        user_id=user_id,
        task_type=task_type,
        input_payload=file_payload,
    )
    enqueue_task(task.id)
    return to_task_response(task)


@router.post("/video-watermark", response_model=TaskResponse)
def create_video_watermark_task(
    file: UploadFile = File(...),
    user_id: str = Form("anonymous"),
    mode: str = Form("auto"),
    region: str = Form(""),
    size: str = Form("medium"),
    method: str = Form("delogo"),
    padding: int = Form(2),
    box: str = Form(""),
    session: Session = Depends(get_session),
):
    """上传本地视频，去掉画面里的 AI 生成水印/角标。"""
    try:
        options = VideoWatermarkOptions(mode=mode, region=region, size=size, method=method, padding=padding)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid_options: {exc}") from exc

    suffix = Path(file.filename or "").suffix.lower()
    if suffix and suffix not in VIDEO_SUFFIXES:
        raise HTTPException(status_code=400, detail="unsupported_file_type")

    if options.mode == "manual" and not options.region and not box:
        raise HTTPException(status_code=400, detail="manual_region_required")

    file_payload = _save_upload_file(file)
    input_payload = {
        **file_payload,
        "watermark_mode": options.mode,
        "watermark_region": options.region,
        "watermark_size": options.size,
        "watermark_method": options.method,
        "watermark_padding": options.padding,
        "watermark_box": _parse_box(box),
    }

    service = TaskService(session)
    task = service.create_task(
        user_id=user_id,
        task_type=TaskType.video_watermark,
        input_payload={key: value for key, value in input_payload.items() if value not in ("", None)},
    )
    enqueue_task(task.id)
    return to_task_response(task)


@router.post("/video-generate", response_model=TaskResponse)
def create_video_generate_task(payload: VideoGenerateRequest, session: Session = Depends(get_session)):
    service = TaskService(session)
    task = service.create_task(
        user_id=payload.user_id,
        task_type=TaskType.video_generate,
        input_payload=payload.model_dump(mode="json", exclude={"user_id"}),
    )
    enqueue_task(task.id)
    return to_task_response(task)


@router.post("/subtitle/frame")
def fetch_subtitle_frame(payload: SubtitleFrameRequest):
    """下载视频并抽取一帧预览图，供用户框选字幕区域。"""
    from app.workers.processors.subtitle import extract_frame_for_selection

    return extract_frame_for_selection(payload.url)


@router.post("/subtitle/remove", response_model=TaskResponse)
def create_subtitle_remove_task(payload: SubtitleRemoveRequest, session: Session = Depends(get_session)):
    """按用户框选的字幕区域，创建去字幕异步任务。"""
    if not payload.url:
        raise HTTPException(status_code=400, detail="url_required")

    box = payload.region.model_dump() if payload.region is not None else None
    service = TaskService(session)
    task = service.create_task(
        user_id=payload.user_id,
        task_type=TaskType.remove_subtitle,
        input_payload={
            "url": payload.url,
            "subtitle_method": payload.method,
            "subtitle_region": box,
        },
    )
    enqueue_task(task.id)
    return to_task_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, session: Session = Depends(get_session)):
    task = TaskService(session).get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_not_found")
    return to_task_response(task)


@router.get("", response_model=list[TaskResponse])
def list_tasks(user_id: str = "anonymous", session: Session = Depends(get_session)):
    tasks = TaskService(session).list_tasks(user_id)
    return [to_task_response(task) for task in tasks]


def _parse_box(raw: str) -> dict | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_box") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="invalid_box")
    return parsed


def _parse_file_process_type(process_type: str) -> TaskType | None:
    try:
        task_type = TaskType(process_type)
    except ValueError:
        return None

    if task_type not in {TaskType.remove_watermark, TaskType.remove_subtitle, TaskType.ocr_extract}:
        return None
    return task_type


def _save_upload_file(file: UploadFile) -> dict:
    uploads_dir = Path(settings.media_root) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    original_filename = file.filename or "upload"
    suffix = Path(original_filename).suffix
    target_path = uploads_dir / f"{uuid4()}{suffix}"
    with target_path.open("wb") as target_file:
        shutil.copyfileobj(file.file, target_file)

    return {
        "filename": original_filename,
        "file_path": str(target_path),
        "mime_type": file.content_type,
        "size": target_path.stat().st_size,
    }
