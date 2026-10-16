from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class MediaAsset(SQLModel, table=True):
    __tablename__ = "media_asset"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    task_id: str = Field(index=True)
    kind: str
    file_path: str
    url: str
    mime_type: str | None = None
    size: int | None = None
    duration: float | None = None
    created_at: datetime = Field(default_factory=utc_now)
