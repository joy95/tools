# Media Tools

自媒体工具箱小程序，包含 `uni-app + Vue3` 前端和 `Python + FastAPI` 后端。

## 功能

- 链接解析：抖音、小红书、视频号链接解析，返回文案和媒体信息。
- 文件处理：上传图片/视频，创建去水印、去字幕、OCR 任务。
- 视频去水印：上传本地视频，自动定位并去除 AI 生成水印/角标，支持手动指定位置与快速/精细两种算法。
- 视频去字幕：粘贴视频链接，读取视频后抽取预览帧，在画面上框选字幕区域即可去除，支持快速/精细两种算法。
- 图文生成视频：上传图片和文案，生成基础短视频。

## 目录

- `frontend/`：小程序前端。
- `backend/`：FastAPI 后端和异步任务。
- `docs/`：规格和实施计划。

## 后端启动

```bash
cd "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools"
docker compose up --build
```

备注：
- Dockerfile 已改用阿里云 Debian / PyPI 镜像，避免官方源超时（常见于安装 `ctranslate2`）。
- 若构建时报 DaoCloud 等镜像源 `502`，改用：`DOCKER_BUILDKIT=0 docker compose up --build`
- 健康检查地址：`http://127.0.0.1:8082/health`

## 启动后验证
```
curl http://127.0.0.1:8082/health
看到 {"status":"ok"} 就说明后端正常
```

## 前端启动

进入 `frontend/` 后运行微信小程序开发命令：

```bash
cd frontend
npm run dev:media-tools
```
