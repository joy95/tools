from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TaskType(str, Enum):
    link_parse = "link_parse"
    remove_watermark = "remove_watermark"
    video_watermark = "video_watermark"
    remove_subtitle = "remove_subtitle"
    ocr_extract = "ocr_extract"
    video_generate = "video_generate"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class Task(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(index=True)
    type: TaskType = Field(index=True)
    status: TaskStatus = Field(default=TaskStatus.pending, index=True)
    progress: int = 0
    input_payload: str = "{}"
    result_payload: str = "{}"
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
