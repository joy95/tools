# 本地视频去水印（AI 生成水印）设计

**状态**：已实现（2026-09-22）
**范围**：新增「视频去水印」能力——上传本地视频，自动定位并去除画面中固定位置的 AI 生成显式标识（平台角标、"AI生成" 文字等）。

---

## 背景

按《人工智能生成合成内容标识办法》（2025-09-01 施行），国内 AI 生成内容必须带显式标识。各平台（即梦、可灵、豆包、通义万相、Vidu、海螺等）的标识绝大多数是**固定在画面某个角落的半透明文字/角标**。原有的 `remove_watermark` 处理器对 3 个写死区域做 delogo，位置不准、无法指定、也没有区域可见性。

## 方案总览

```
上传视频 ──> /api/tasks/video-watermark ──> Celery 任务 video_watermark
                                              │
                                    ┌─────────┴──────────┐
                                    │  定位（mode）        │
                                    │  auto: 帧采样检测    │
                                    │  manual: 预设角标区  │
                                    └─────────┬──────────┘
                                              │
                                    ┌─────────┴──────────┐
                                    │  去除（method）      │
                                    │  delogo: ffmpeg 插值│
                                    │  inpaint: OpenCV 修复│
                                    └─────────┬──────────┘
                                              │
                              输出 mp4 + 区域预览图 + 区域坐标
```

## 水印定位（`app/workers/processors/watermark_detect.py`）

固定水印的两个物理特征：

1. **时域稳定性** —— 水印像素在整段视频中几乎不变，逐像素时域标准差远低于画面平均运动量；
2. **结构显著性** —— 文字/图标存在明显高频边缘（中值帧与高斯模糊的差值）。

流程：等距采样 24 帧（避开首尾 3%）→ 降采样到最长边 480 → 计算时域中值与标准差 →
`静止（std 低）∧ 有结构（边缘强）`得到候选像素 → 限制在画面四周 34% 的「角标带」→
形态学闭运算连接笔画 → 连通域过滤（面积 0.04%~20%、填充率 ≥6%、置信度 ≥0.25）→
重叠框合并 → 取前 4 个映射回原图坐标。

置信度 = 0.55 × 静止程度 + 0.45 × 结构强度。

**兜底**：检测不到（纯静止画面、水印过于透明）时，默认按国内平台最常见的右下角处理，并在结果 message 里明确提示可改用手动模式。

## 水印去除（`app/workers/processors/watermark.py`）

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `watermark_mode` | `auto` / `manual` | 智能检测 / 手动指定 |
| `watermark_region` | `bottom_right` 等 6 种 | 手动模式的位置预设，支持中文别名 |
| `watermark_size` | `small` / `medium` / `large` | 预设区域缩放，锚定角保持贴边 |
| `watermark_box` | `{x,y,w,h}` | 归一化或像素的自定义框（API 扩展用） |
| `watermark_method` | `delogo` / `inpaint` | 快速插值 / 逐帧 Telea 修复 |
| `watermark_padding` | 0~60 px | 区域外扩，默认 10 |

- 区域先 `expand_region` 外扩 padding（贴边时改为向内扩，保证 delogo 有干净边框且完整覆盖水印），再合并重叠框。
- `delogo`：ffmpeg 链式滤镜，H.264 CRF20 + AAC 160k + faststart，保留原分辨率/帧率/音轨。
- `inpaint`：OpenCV 逐帧 Telea 修复，帧数据经管道喂给 ffmpeg 编码；失败自动回退 delogo。
- 奇数分辨率自动补 `scale=trunc(iw/2)*2:trunc(ih/2)*2`。

## API

`POST /api/tasks/video-watermark`（multipart）

| 字段 | 类型 | 默认 |
| --- | --- | --- |
| `file` | file | 必填，视频文件 |
| `mode` | `auto` \| `manual` | `auto` |
| `region` | string | `""` |
| `size` | `small` \| `medium` \| `large` | `medium` |
| `method` | `delogo` \| `inpaint` | `delogo` |
| `padding` | int | 10 |
| `box` | JSON string | `""` |

错误：`invalid_options` / `manual_region_required` / `unsupported_file_type` / `invalid_box`。

结果 `result_payload` 新增字段：`status`、`mode`、`algorithm`、`regions[]`、`detected_regions[]`、`video_meta`、`original_video_url`、`preview_url`（抽帧并画出区域框的示意图），并保留原有 `download_url` / `processed_video_url` / `message`。

## 前端

- 新页面 `pages/video-watermark/video-watermark.vue`：上传 → 选定位方式（智能/手动 + 六宫格位置 + 大小档）→ 选去除方式 → 提交并轮询（2s 间隔，上限 10 分钟）→ 展示区域示意图、去除区域数、处理后视频，可一键保存相册。
- 首页新增「视频去水印」入口，并把原本错指向链接解析的「去水印」卡片改正。
- 任务列表标签映射补充 `video_watermark`。

## 已验证

- `pytest tests/` 99 项全部通过（含区域换算、检测、处理器、API 校验）。
- 合成视频（720×1280 动态渐变背景 + 右下角 AI 角标）端到端：自动检测框住整个角标，delogo 与 inpaint 两种算法处理后画面水印完全消失，背景重建自然。
- `vue-tsc --noEmit` 无错误，`uni build -p mp-weixin` 构建通过。

## 已知限制

- 水印若为**移动式**（如抖音个人号角标）不在本方案范围内，需先做轨迹跟踪。
- 半透明度极高或贴字过小的水印可能检测不到，此时走右下角兜底或手动指定。
- 纯静止画面（无运动）失去时域判据，检测可靠性下降。
