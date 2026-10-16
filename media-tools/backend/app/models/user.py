from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    openid: str | None = Field(default=None, index=True)
    nickname: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
