# 视频去字幕功能设计

日期：2026-10-13

## 背景与目标

已有「视频去水印」面向的是 AI 生成视频**固定在角落的显式标识**，位置固定、可自动检测。
字幕与水印是两类不同对象：字幕是视频底部或任意位置的人造文字条，位置随视频而异，
无法可靠自动定位，**必须让用户手动框选**。

本次新增「视频去字幕」功能：

- 输入方式为**视频链接**（直链 mp4/mov，或可被 yt-dlp 解析的作品分享链接），而非本地上传；
- 用户在预览帧上**框选字幕区域**后再去除；
- 两段式流程：先取帧供框选，再按框选区域处理整段视频。

## 后端设计

### 处理器 `backend/app/workers/processors/subtitle.py`

- `extract_frame_for_selection(source_url) -> dict`
  解析并下载视频（复用 `link_video` 的 `_resolve_video` / `_download_video`，落到
  `media/link_videos/<sha1(url)[:16]>/original.mp4` 并复用已有文件），随后用 ffmpeg
  在视频中点抽一帧，输出 `subtitle_frame.jpg`，返回 `frame_url / width / height / duration`。
  本地文件路径也可直接作为输入（便于测试与本地调试）。
- `remove_subtitle(input_payload) -> dict`（Celery 任务入口）
  读取 `url`（或 `file_path`）与归一化框选区域 `subtitle_region`，复用
  `watermark` 模块的去除原语（`custom_region` / `expand_region` / `merge_overlapping` /
  `render_region_preview` / `_apply_removal`）完成去除：
  - 区域来自框选（归一化坐标，`custom_region` 同时兼容像素坐标）；
  - 未框选时兜底处理画面底部 12% 字幕带；
  - 输出保留原分辨率、帧率与音轨，H.264 + faststart；
  - 同时生成区域示意图 `subtitle_preview.jpg`。

### 接口 `backend/app/api/tasks.py`

- `POST /api/tasks/subtitle/frame`（同步）
  请求体 `{url, user_id}`，返回抽取帧信息。下载与抽帧通常数秒内完成，故同步返回，
  前端拿到帧即可框选。
- `POST /api/tasks/subtitle/remove`（异步任务）
  请求体 `{url, user_id, method, region:{x,y,w,h}}`，创建 `remove_subtitle` 任务，
  复用现有 `GET /api/tasks/{id}` 轮询进度与结果。

### 数据模型 / Schema

- 复用既有 `TaskType.remove_subtitle`，无需新增任务类型。
- `schemas/task.py` 新增 `SubtitleBox`、`SubtitleFrameRequest`、`SubtitleRemoveRequest`。

## 前端设计

新页面 `frontend/src/pages/video-subtitle/video-subtitle.vue`：

1. 粘贴视频链接 → 「读取视频并获取预览帧」；
2. 在预览帧上**按住拖动框选**字幕区域（触摸事件 + `boundingClientRect` 归一化坐标，
   框选面积过小自动忽略）；未框选时提交会二次确认走底部兜底；
3. 选择去除方式（快速 delogo / 精细 inpaint）→ 提交异步任务 → 轮询 → 结果预览 + 保存相册。

配套改动：`types/task.ts`（`SubtitleFrameInfo` / `VideoSubtitleResult` / `SubtitleBox`）、
`services/api.ts`（`fetchSubtitleFrame` / `createSubtitleRemoveTask`）、
`pages.json` 路由、首页入口卡片。

## 局限

- 移动式字幕（跟随画面位移）暂不支持，需逐帧跟踪；
- 字幕区域贴近画面底边且为整条不透明底衬时，修复依赖相邻画面回填，可能出现轻微渐变过渡；
- 分享链接解析依赖 `yt-dlp`，直链 mp4 无需额外依赖。
