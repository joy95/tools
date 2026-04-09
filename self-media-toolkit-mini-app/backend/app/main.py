from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
import os
import shutil
import uuid
from pydantic import BaseModel

from .tasks import remove_watermark_task, extract_text_task, generate_video_task
from .dependencies import verify_api_key # 假设你有一个API Key验证机制

app = FastAPI(
    title="自媒体工具箱后端API",
    description="提供去水印、文案提取、图文生成视频等功能",
    version="1.0.0"
)

# 配置静态文件服务，用于提供处理后的媒体文件
MEDIA_DIR = "./media"
if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

class URLInput(BaseModel):
    url: str

class VideoGenerateInput(BaseModel):
    images: List[str] # 图片的URL列表
    text: str
    templateId: Optional[str] = "default"
    audioOption: Optional[str] = "default"

# ==== 认证鉴权 (示例) ====
# @app.middleware("http")
# async def api_key_middleware(request: Request, call_next):
#     if request.url.path.startswith("/media") or request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
#         return await call_next(request)
#     api_key = request.headers.get("X-API-Key")
#     if not verify_api_key(api_key):
#         raise HTTPException(status_code=401, detail="Invalid API Key")
#     response = await call_next(request)
#     return response

# ==== 文件管理服务 ====
@app.post("/api/upload")
async def upload_file_endpoint(file: UploadFile = File(...)): # 这是一个通用的文件上传接口
    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    file_path = os.path.join(MEDIA_DIR, f"{file_id}{file_extension}")
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()
    
    return {"url": f"/media/{file_id}{file_extension}"}

# ==== 去水印 API ====
@app.post("/api/watermark/remove")
async def remove_watermark_endpoint(
    file: Optional[UploadFile] = File(None), 
    url: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    if not file and not url:
        raise HTTPException(status_code=400, detail="请提供文件或链接")

    if file:
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        input_path = os.path.join(MEDIA_DIR, f"input_{file_id}{file_extension}")
        try:
            with open(input_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        finally:
            file.file.close()
        # 提交去水印任务到 Celery
        task = remove_watermark_task.delay(input_path, file_extension, is_url=False)
        return JSONResponse(content={"taskId": task.id}, status_code=202)
    elif url:
        # 提交去水印任务到 Celery (从URL下载并处理)
        task = remove_watermark_task.delay(url, is_url=True)
        return JSONResponse(content={"taskId": task.id}, status_code=202)

# ==== 文案提取 API ====
@app.post("/api/text/extract")
async def extract_text_endpoint(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None)
):
    if not file and not url:
        raise HTTPException(status_code=400, detail="请提供图片或链接")

    if file:
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        input_path = os.path.join(MEDIA_DIR, f"input_{file_id}{file_extension}")
        try:
            with open(input_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        finally:
            file.file.close()
        # 提交文案提取任务到 Celery
        task = extract_text_task.delay(input_path, is_url=False)
        return JSONResponse(content={"taskId": task.id}, status_code=202)
    elif url:
        # 提交文案提取任务到 Celery (从URL下载并处理)
        task = extract_text_task.delay(url, is_url=True)
        return JSONResponse(content={"taskId": task.id}, status_code=202)

# ==== 图文生成视频 API ====
@app.post("/api/video/generate")
async def generate_video_endpoint(input_data: VideoGenerateInput):
    # 提交视频生成任务到 Celery
    task = generate_video_task.delay(
        input_data.images,
        input_data.text,
        input_data.templateId,
        input_data.audioOption
    )
    return JSONResponse(content={"taskId": task.id}, status_code=202)

@app.get("/api/video/status/{task_id}")
async def get_video_status(task_id: str):
    from .celery_app import celery_app
    task_result = celery_app.AsyncResult(task_id)
    if task_result.ready():
        result = task_result.get()
        return JSONResponse(content={"status": "SUCCESS", "url": result}, status_code=200)
    else:
        return JSONResponse(content={"status": "PENDING"}, status_code=200)

# ==== 其他 API 模块（待创建）====
# from .api.v1 import some_other_feature
# app.include_router(some_other_feature.router, prefix="/api/v1")
