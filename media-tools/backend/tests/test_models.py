import os
import subprocess
import sys

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine

from app.db import init_db, engine
from app.models.media_asset import MediaAsset
from app.models.quota import UsageQuota
from app.models.task import Task, TaskStatus, TaskType
from app.models.user import User


EXPECTED_TABLE_NAMES = {"task", "user", "media_asset", "usage_quota"}


def test_task_defaults():
    task = Task(user_id="anonymous", type=TaskType.link_parse)

    assert task.status == TaskStatus.pending
    assert task.progress == 0
    assert task.input_payload == "{}"
    assert task.result_payload == "{}"
    assert task.created_at.tzinfo is None
    assert task.updated_at.tzinfo is None


def test_init_db_creates_model_tables():
    init_db()

    table_names = set(inspect(engine).get_table_names())

    assert Task.__tablename__ == "task"
    assert User.__tablename__ == "user"
    assert MediaAsset.__tablename__ == "media_asset"
    assert UsageQuota.__tablename__ == "usage_quota"
    assert EXPECTED_TABLE_NAMES <= table_names


def test_init_db_registers_models_without_prior_model_imports(tmp_path):
    database_path = tmp_path / "self_contained.db"
    script = """
from sqlalchemy import inspect

from app.db import engine, init_db

init_db()
table_names = set(inspect(engine).get_table_names())
expected = {"task", "user", "media_asset", "usage_quota"}
missing = expected - table_names
raise SystemExit(1 if missing else 0)
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{database_path}"},
        text=True,
    )

    assert result.returncode == 0


def test_task_timestamps_round_trip_as_naive_utc():
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        task = Task(user_id="anonymous", type=TaskType.link_parse)
        session.add(task)
        session.commit()
        session.refresh(task)
        loaded_task = session.get(Task, task.id)

    assert loaded_task is not None
    assert loaded_task.created_at is not None
    assert loaded_task.updated_at is not None
    assert loaded_task.created_at.tzinfo is None
    assert loaded_task.updated_at.tzinfo is None
