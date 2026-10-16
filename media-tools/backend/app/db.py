from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings


connect_args = {}
if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args)


def init_db() -> None:
    from app.models import media_asset, quota, task, user

    _ = (media_asset, quota, task, user)
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
