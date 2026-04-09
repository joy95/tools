# 自媒体工具箱后端 (Python FastAPI)

这是一个基于 `Python FastAPI` 开发的自媒体工具箱后端服务，提供去水印、文案提取和图文生成视频等核心功能。

## 技术栈

*   **Python 版本**: 3.9+
*   **Web 框架**: `FastAPI`
*   **ASGI 服务器**: `Uvicorn`
*   **异步任务队列**: `Celery` + `Redis`
*   **文件存储**: 本地文件系统 (初期)
*   **依赖管理**: `Poetry`
*   **核心库**: `OpenCV`, `Pillow`, `PaddleOCR`, `MoviePy`, `gTTS`, `requests`, `BeautifulSoup`

## 项目结构

```
backend/
├── app/                  # FastAPI 应用模块
│   ├── __init__.py
│   ├── main.py           # FastAPI 主应用和路由定义
│   ├── celery_app.py     # Celery 应用配置
│   ├── tasks.py          # Celery 异步任务 (去水印、文案提取、视频生成逻辑)
│   └── dependencies.py   # 依赖注入 (如 API Key 验证)
├── media/                # 媒体文件存储目录 (由 Docker 挂载)
├── Dockerfile            # Docker 镜像构建文件
├── pyproject.toml        # Poetry 项目配置和依赖管理
└── poetry.lock           # Poetry 依赖锁定文件 (通过 poetry install 生成)
```

## 开发与部署指南

### 1. 前提条件

*   已安装 Docker 和 Docker Compose。
*   如果需要，已配置 Docker 镜像加速器 (推荐使用国内加速器以提高镜像拉取速度)。

### 2. 构建与运行 (使用 Docker Compose)

进入项目根目录 `self-media-toolkit-mini-app`，然后执行以下命令来构建 Docker 镜像并启动所有服务 (FastAPI, Redis, Celery Worker)：

```bash
cd self-media-toolkit-mini-app
docker-compose up --build
```

如果需要后台运行，可以使用：

```bash
docker-compose up -d --build
```

### 3. 后端 API 文档

服务启动后，你可以通过浏览器访问以下地址查看自动生成的 API 文档：

*   **Swagger UI**: `http://localhost:8000/docs`
*   **ReDoc**: `http://localhost:8000/redoc`

### 4. API Key 验证

默认情况下，API Key 验证功能是启用的。你需要在 `backend/app/dependencies.py` 中设置你的 `API_KEY`，并在前端请求的 `headers` 中添加 `X-API-Key` 字段进行认证。

```python
# backend/app/dependencies.py
def verify_api_key(api_key: str | None) -> bool:
    if api_key is None or api_key != "YOUR_SUPER_SECRET_API_KEY": # 替换为你的实际API Key
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True
```

### 5. 后端测试

参考实施计划中的后端测试策略进行单元测试和集成测试。

### 6. 注意事项

*   **链接解析**: `backend/app/tasks.py` 中的 `parse_platform_link` 函数目前为模拟实现。真正的抖音、小红书、视频号内容抓取需要投入大量精力应对反爬机制、法律合规风险和持续维护。
*   **去水印和视频生成逻辑**: `backend/app/tasks.py` 中的去水印和视频生成逻辑为简化版本，实际部署时需要更高级的图像处理和 AI 算法。
*   **性能调优**: 随着用户量增长，可能需要对 Celery Worker 数量、Redis 缓存、API 性能等进行优化。
*   **HTTPS**: 生产环境部署时，务必配置 HTTPS 以确保数据传输安全。
