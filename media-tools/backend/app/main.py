from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.tasks import router as tasks_router
from app.core.config import settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    media_root.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(tasks_router)

media_root = Path(settings.media_root)
app.mount(settings.public_media_prefix, StaticFiles(directory=media_root, check_dir=False), name="media")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
