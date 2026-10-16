# 链接口播文案提取 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有链接解析结果中，为视频作品新增从音频转写得到的口播文案。

**Architecture:** 保持 `link_parse` 任务入口不变。后端在 `extract_link_work -> download_work_assets` 之后调用独立 speech 处理器，只处理本地 mp4 视频 asset，并把 `speech_text / speech_status / speech_message` 合并进结果；前端只扩展结果类型和展示卡片。

**Tech Stack:** FastAPI/Celery/SQLModel, ffmpeg, faster-whisper, uni-app Vue3 TypeScript.

---

## File Structure

- Modify: `backend/pyproject.toml`
  - 增加 `faster-whisper` 依赖。
- Modify: `backend/app/core/config.py`
  - 增加 `speech_model_size` 配置，默认 `tiny`。
- Create: `backend/app/workers/processors/speech.py`
  - 负责从本地视频提取音频、调用 ASR、返回口播识别状态。
- Create: `backend/tests/test_speech_processor.py`
  - 覆盖视频成功、图片跳过、ASR 失败不抛出。
- Modify: `backend/app/workers/tasks.py`
  - 在 `link_parse` 分支下载素材后调用 speech processor。
- Modify: `backend/tests/test_worker_dispatch.py`
  - 覆盖 worker 把 speech 字段合并进结果。
- Modify: `frontend/src/types/task.ts`
  - 扩展 `LinkParseResult`。
- Modify: `frontend/src/pages/link-parse/link-parse.vue`
  - 展示口播文案卡片和复制按钮。

---

### Task 1: Add Speech Dependency and Config

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Add dependency**

In `backend/pyproject.toml`, add:

```toml
faster-whisper = "^1.1.1"
```

under `[tool.poetry.dependencies]`.

- [ ] **Step 2: Add config**

In `backend/app/core/config.py`, change `Settings` to include:

```python
class Settings(BaseSettings):
    app_name: str = "Media Tools API"
    database_url: str = "sqlite:///./data/media_tools.db"
    redis_url: str = "redis://localhost:6379/0"
    media_root: str = "./media"
    public_media_prefix: str = "/media"
    ytdlp_cookies_file: str | None = None
    speech_model_size: str = "tiny"
```

- [ ] **Step 3: Install dependency**

Run:

```bash
cd "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend"
poetry lock
poetry install
```

Expected: dependency lock and install complete.

- [ ] **Step 4: Verify import**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/.venv/bin/python" -c "from app.core.config import settings; print(settings.speech_model_size)"
```

Expected:

```text
tiny
```

---

### Task 2: Implement Speech Processor

**Files:**
- Create: `backend/app/workers/processors/speech.py`
- Create: `backend/tests/test_speech_processor.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_speech_processor.py`:

```python
from pathlib import Path

import pytest

from app.workers.processors.speech import enrich_result_with_speech


def test_enrich_result_with_speech_skips_images(tmp_path):
    result = {
        "assets": [
            {
                "type": "image",
                "local_url": "/media/link_assets/task-1/image_1.jpg",
                "mime_type": "image/jpeg",
            }
        ]
    }

    enriched = enrich_result_with_speech(result)

    assert enriched["speech_status"] == "skipped"
    assert enriched["speech_text"] == ""


def test_enrich_result_with_speech_transcribes_video(monkeypatch, tmp_path):
    video_path = tmp_path / "link_assets" / "task-1" / "video_1.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"video")
    audio_path = tmp_path / "speech" / "task-1.wav"

    result = {
        "assets": [
            {
                "type": "video",
                "local_url": "/media/link_assets/task-1/video_1.mp4",
                "mime_type": "video/mp4",
            }
        ]
    }

    monkeypatch.setattr("app.workers.processors.speech.settings.media_root", str(tmp_path))
    monkeypatch.setattr("app.workers.processors.speech._extract_audio", lambda source, target: audio_path)
    monkeypatch.setattr("app.workers.processors.speech._transcribe_audio", lambda path: "这是口播文案")

    enriched = enrich_result_with_speech(result)

    assert enriched["speech_status"] == "success"
    assert enriched["speech_text"] == "这是口播文案"
    assert enriched["speech_message"] == ""


def test_enrich_result_with_speech_handles_asr_failure(monkeypatch, tmp_path):
    video_path = tmp_path / "link_assets" / "task-1" / "video_1.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"video")
    audio_path = tmp_path / "speech" / "task-1.wav"

    result = {
        "assets": [
            {
                "type": "video",
                "local_url": "/media/link_assets/task-1/video_1.mp4",
                "mime_type": "video/mp4",
            }
        ]
    }

    def raise_asr(path: Path) -> str:
        raise RuntimeError("asr failed")

    monkeypatch.setattr("app.workers.processors.speech.settings.media_root", str(tmp_path))
    monkeypatch.setattr("app.workers.processors.speech._extract_audio", lambda source, target: audio_path)
    monkeypatch.setattr("app.workers.processors.speech._transcribe_audio", raise_asr)

    enriched = enrich_result_with_speech(result)

    assert enriched["speech_status"] == "failed"
    assert enriched["speech_text"] == ""
    assert "asr failed" in enriched["speech_message"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/tests/test_speech_processor.py" -v
```

Expected: FAIL because `app.workers.processors.speech` does not exist.

- [ ] **Step 3: Implement speech processor**

Create `backend/app/workers/processors/speech.py`:

```python
import subprocess
from pathlib import Path

from app.core.config import settings


def enrich_result_with_speech(result: dict) -> dict:
    enriched = dict(result)
    video_path = _first_local_mp4(enriched)
    if video_path is None:
        enriched.update(
            {
                "speech_text": "",
                "speech_status": "skipped",
                "speech_message": "当前作品无需提取口播文案",
            }
        )
        return enriched

    try:
        audio_path = _extract_audio(video_path, _audio_path_for(video_path))
        speech_text = _transcribe_audio(audio_path).strip()
        enriched.update(
            {
                "speech_text": speech_text,
                "speech_status": "success" if speech_text else "empty",
                "speech_message": "" if speech_text else "未识别到有效口播内容",
            }
        )
    except Exception as exc:
        enriched.update(
            {
                "speech_text": "",
                "speech_status": "failed",
                "speech_message": str(exc),
            }
        )
    return enriched


def _first_local_mp4(result: dict) -> Path | None:
    media_root = Path(settings.media_root).resolve()
    prefix = settings.public_media_prefix.rstrip("/") + "/"
    for asset in result.get("assets", []):
        if asset.get("type") != "video":
            continue
        if asset.get("mime_type") != "video/mp4":
            continue
        local_url = str(asset.get("local_url") or "")
        if not local_url.startswith(prefix):
            continue
        relative = local_url.removeprefix(prefix)
        path = (media_root / relative).resolve()
        if path.is_relative_to(media_root) and path.suffix.lower() == ".mp4" and path.exists():
            return path
    return None


def _audio_path_for(video_path: Path) -> Path:
    target_dir = Path(settings.media_root) / "speech" / video_path.parent.name
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / f"{video_path.stem}.wav"


def _extract_audio(video_path: Path, audio_path: Path) -> Path:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return audio_path


def _transcribe_audio(audio_path: Path) -> str:
    from faster_whisper import WhisperModel

    model = WhisperModel(settings.speech_model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path), language="zh", vad_filter=True)
    return "".join(segment.text for segment in segments).strip()
```

- [ ] **Step 4: Run tests**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/tests/test_speech_processor.py" -v
```

Expected: PASS.

---

### Task 3: Integrate Speech Into Link Parse Worker

**Files:**
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/tests/test_worker_dispatch.py`

- [ ] **Step 1: Update worker tests**

In `backend/tests/test_worker_dispatch.py`, update `test_run_link_parse_task` to also monkeypatch speech:

```python
def test_run_link_parse_task(monkeypatch):
    from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork

    def fake_extract(url: str, raw_text: str = ""):
        return ExtractedWork(
            platform="douyin",
            source_url=url,
            media_type="video",
            caption="平台文案",
            assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/a.mp4", mime_type="video/mp4")],
            parse_method="public_page",
        )

    def fake_download(task_id: str, work):
        return {
            "platform": work.platform,
            "source_url": work.source_url,
            "media_type": work.media_type,
            "caption": work.caption,
            "assets": [
                {
                    "type": "video",
                    "source_url": "https://cdn.example.com/a.mp4",
                    "local_url": "/media/link_assets/test-task/video_1.mp4",
                    "mime_type": "video/mp4",
                }
            ],
            "parse_method": work.parse_method,
            "download_status": "success",
        }

    def fake_speech(result):
        enriched = dict(result)
        enriched["speech_text"] = "这是口播文案"
        enriched["speech_status"] = "success"
        enriched["speech_message"] = ""
        return enriched

    monkeypatch.setattr("app.workers.tasks.extract_link_work", fake_extract)
    monkeypatch.setattr("app.workers.tasks.download_work_assets", fake_download)
    monkeypatch.setattr("app.workers.tasks.enrich_result_with_speech", fake_speech)

    result = _run_task(TaskType.link_parse, {"url": "https://www.douyin.com/video/123", "raw_text": "分享文案", "task_id": "test-task"})

    assert result["platform"] == "douyin"
    assert result["media_type"] == "video"
    assert result["caption"] == "平台文案"
    assert result["assets"][0]["local_url"] == "/media/link_assets/test-task/video_1.mp4"
    assert result["download_status"] == "success"
    assert result["speech_status"] == "success"
    assert result["speech_text"] == "这是口播文案"
```

Also update `test_dispatch_task_updates_task_success` to monkeypatch:

```python
monkeypatch.setattr(worker_tasks, "enrich_result_with_speech", lambda result: {**result, "speech_status": "skipped", "speech_text": "", "speech_message": "当前作品无需提取口播文案"})
```

and assert:

```python
assert response.result_payload["speech_status"] == "skipped"
```

- [ ] **Step 2: Run worker tests to verify failure**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/tests/test_worker_dispatch.py::test_run_link_parse_task" -v
```

Expected: FAIL because `app.workers.tasks.enrich_result_with_speech` is not imported.

- [ ] **Step 3: Update worker implementation**

In `backend/app/workers/tasks.py`, add:

```python
from app.workers.processors.speech import enrich_result_with_speech
```

Replace the `TaskType.link_parse` branch with:

```python
if task_type == TaskType.link_parse:
    work = extract_link_work(input_payload["url"], input_payload.get("raw_text", ""))
    result = download_work_assets(input_payload.get("task_id", "preview"), work)
    return enrich_result_with_speech(result)
```

- [ ] **Step 4: Run worker tests**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/tests/test_worker_dispatch.py" -v
```

Expected: PASS.

---

### Task 4: Update Frontend Result Types and Display

**Files:**
- Modify: `frontend/src/types/task.ts`
- Modify: `frontend/src/pages/link-parse/link-parse.vue`

- [ ] **Step 1: Update TypeScript result type**

In `frontend/src/types/task.ts`, extend `LinkParseResult`:

```ts
export interface LinkParseResult {
  platform?: string;
  source_url?: string;
  media_type?: "video" | "image" | "mixed" | "unknown";
  caption?: string | null;
  title?: string | null;
  author?: string | null;
  cover_url?: string | null;
  assets?: LinkAsset[];
  parse_method?: string;
  download_status?: "success" | "empty";
  speech_text?: string | null;
  speech_status?: "success" | "empty" | "skipped" | "failed";
  speech_message?: string | null;
}
```

- [ ] **Step 2: Add display helper**

In `frontend/src/pages/link-parse/link-parse.vue` script, add:

```ts
function speechDisplayText(result: LinkParseResult): string {
  if (result.speech_text) {
    return result.speech_text;
  }
  if (result.speech_status === "skipped") {
    return "当前作品无需提取口播文案";
  }
  if (result.speech_status === "failed") {
    return result.speech_message || "口播文案提取失败";
  }
  if (result.speech_status === "empty") {
    return result.speech_message || "未识别到有效口播内容";
  }
  return "-";
}
```

- [ ] **Step 3: Add speech card**

In the result panel of `frontend/src/pages/link-parse/link-parse.vue`, after the “作品文案” block, add:

```vue
<view class="result-block highlight">
  <text class="key">口播文案</text>
  <text class="value">{{ speechDisplayText(result) }}</text>
  <button v-if="result.speech_text" class="copy-button" @tap="copy(result.speech_text)">复制口播文案</button>
</view>
```

- [ ] **Step 4: Build frontend**

Run:

```bash
source "$HOME/.nvm/nvm.sh" && nvm use 24.13.0 && npm --prefix "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/frontend" run build:mp-weixin
```

Expected:

```text
DONE  Build complete.
```

---

### Task 5: Full Verification

**Files:**
- No new implementation files.

- [ ] **Step 1: Run backend tests**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/backend/tests" -v
```

Expected: all tests pass.

- [ ] **Step 2: Build frontend**

Run:

```bash
source "$HOME/.nvm/nvm.sh" && nvm use 24.13.0 && npm --prefix "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview/frontend" run build:mp-weixin
```

Expected:

```text
DONE  Build complete.
```

- [ ] **Step 3: Rebuild backend stack**

Run:

```bash
cd "/Users/luckincoffee/Desktop/cxj/tools/media-tools-preview"
docker compose up --build -d backend worker redis
```

Expected: backend, worker, redis are running.

- [ ] **Step 4: Health check**

Run:

```bash
curl -sS http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

- [ ] **Step 5: Manual check with a real video link**

Submit a real short-video link from the mini program link parse page.

Expected:

- Result still shows existing media preview/download.
- Result shows “口播文案”.
- If speech extraction fails, result still shows media and `speech_status` is `failed`.

---

## Self-Review

- Spec coverage:
  - Existing link parse entry is preserved: Task 3 and Task 4.
  - Audio extraction and local ASR are covered: Task 1 and Task 2.
  - Speech status fields are covered: Task 2, Task 3, Task 4.
  - Speech failure does not fail link parse: Task 2 tests `failed` status without raising.
  - Frontend display and copy behavior are covered: Task 4.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency:
  - Backend result fields match frontend type names: `speech_text`, `speech_status`, `speech_message`.
  - Speech status values match spec: `success`, `empty`, `skipped`, `failed`.
