from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from app.models.task import TaskStatus, TaskType


class LinkParseRequest(BaseModel):
    url: HttpUrl
    raw_text: str | None = None
    user_id: str = "anonymous"


class VideoGenerateRequest(BaseModel):
    image_asset_ids: list[str]
    text: str
    template_id: str = "default"
    user_id: str = "anonymous"


class FileProcessRequest(BaseModel):
    process_type: Literal[TaskType.remove_watermark, TaskType.remove_subtitle, TaskType.ocr_extract]
    user_id: str = "anonymous"


class VideoWatermarkOptions(BaseModel):
    """视频去水印的可选参数，与上传表单字段一一对应。"""

    mode: Literal["auto", "manual"] = "auto"
    region: str = ""
    size: Literal["small", "medium", "large"] = "medium"
    method: Literal["delogo", "inpaint"] = "delogo"
    padding: int = Field(default=2, ge=0, le=60)
    box: dict | None = None


class SubtitleBox(BaseModel):
    """用户在前端预览帧上框选的字幕区域，归一化坐标（0~1）。"""

    x: float
    y: float
    w: float
    h: float


class SubtitleFrameRequest(BaseModel):
    """请求抽取一帧预览图，供用户框选字幕区域。"""

    url: str
    user_id: str = "anonymous"


class SubtitleRemoveRequest(BaseModel):
    """按框选区域去除视频字幕，创建异步任务。"""

    url: str
    user_id: str = "anonymous"
    method: Literal["delogo", "inpaint"] = "delogo"
    region: SubtitleBox | None = None


class TaskResponse(BaseModel):
    id: str
    type: TaskType
    status: TaskStatus
    progress: int
    input_payload: dict
    result_payload: dict
    error_code: str | None = None
    error_message: str | None = None
