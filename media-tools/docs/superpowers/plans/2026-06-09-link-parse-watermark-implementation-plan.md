# Link Parse Watermark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change link parsing so a Douyin, Xiaohongshu, or WeChat Channels link produces local downloadable watermark-free media assets and platform caption text.

**Architecture:** Keep the existing `link_parse` task type, but replace the current placeholder result assembly with a platform extractor pipeline and a local asset downloader. Extractors return a normalized `ExtractedWork`; the worker downloads assets to `MEDIA_ROOT/link_assets/<task_id>/`, converts them to `/media/...` URLs, and the frontend renders a work-level result with copy/download actions.

**Tech Stack:** FastAPI, Celery, SQLModel, requests, BeautifulSoup, yt-dlp, ffmpeg, uni-app Vue3, WeChat mini program APIs.

---

## File Structure

- Create `backend/app/parsers/link_extractors/base.py`
  - Owns normalized extraction dataclasses and typed extractor interface.
- Create `backend/app/parsers/link_extractors/douyin.py`
  - Douyin short-link/public-page/yt-dlp extraction.
- Create `backend/app/parsers/link_extractors/xiaohongshu.py`
  - Xiaohongshu `xhslink` and note-page JSON extraction.
- Create `backend/app/parsers/link_extractors/wechat_channels.py`
  - WeChat Channels public-page/yt-dlp extraction.
- Create `backend/app/parsers/link_extractors/registry.py`
  - Platform extractor routing and unsupported-platform errors.
- Create `backend/app/workers/processors/link_assets.py`
  - Downloads video/image assets into local media storage.
- Modify `backend/app/workers/tasks.py`
  - Replace current `link_parse` assembly with extractor + downloader pipeline.
- Modify `backend/app/core/config.py`
  - Keep `ytdlp_cookies_file`; no new settings are required for this plan.
- Modify `frontend/src/types/task.ts`
  - Add `assets`, `media_type`, `parse_method`, `download_status`.
- Modify `frontend/src/pages/link-parse/link-parse.vue`
  - Render videos/images, copy caption, download assets.
- Add/modify tests:
  - `backend/tests/test_link_extractors.py`
  - `backend/tests/test_link_asset_downloader.py`
  - `backend/tests/test_worker_dispatch.py`

Do not commit during implementation unless the user explicitly requests a commit.

---

### Task 1: Define Normalized Link Extraction Types

**Files:**
- Create: `backend/app/parsers/link_extractors/base.py`
- Test: `backend/tests/test_link_extractors.py`

- [ ] **Step 1: Write tests for normalized models**

Add this to `backend/tests/test_link_extractors.py`:

```python
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork


def test_extracted_work_defaults():
    work = ExtractedWork(platform="douyin", source_url="https://www.douyin.com/video/123")

    assert work.platform == "douyin"
    assert work.source_url == "https://www.douyin.com/video/123"
    assert work.media_type == "unknown"
    assert work.caption == ""
    assert work.assets == []
    assert work.parse_method == "unknown"


def test_extracted_asset_video():
    asset = ExtractedAsset(
        type="video",
        source_url="https://example.com/video.mp4",
        mime_type="video/mp4",
    )

    assert asset.type == "video"
    assert asset.source_url.endswith(".mp4")
    assert asset.mime_type == "video/mp4"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/tests/test_link_extractors.py" -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.parsers.link_extractors'`.

- [ ] **Step 3: Implement dataclasses**

Create `backend/app/parsers/link_extractors/base.py`:

```python
from dataclasses import dataclass, field
from typing import Literal, Protocol


AssetType = Literal["video", "image"]
MediaType = Literal["video", "image", "mixed", "unknown"]


class LinkExtractionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ExtractedAsset:
    type: AssetType
    source_url: str
    mime_type: str = ""
    width: int | None = None
    height: int | None = None


@dataclass
class ExtractedWork:
    platform: str
    source_url: str
    media_type: MediaType = "unknown"
    caption: str = ""
    title: str = ""
    author: str = ""
    cover_url: str | None = None
    assets: list[ExtractedAsset] = field(default_factory=list)
    parse_method: str = "unknown"


class LinkExtractor(Protocol):
    platform: str

    def supports(self, url: str) -> bool:
        ...

    def extract(self, url: str, raw_text: str = "") -> ExtractedWork:
        ...
```

- [ ] **Step 4: Run tests**

Run the same command. Expected: PASS.

---

### Task 2: Add Extractor Registry

**Files:**
- Create: `backend/app/parsers/link_extractors/registry.py`
- Modify: `backend/tests/test_link_extractors.py`

- [ ] **Step 1: Add registry tests**

Append to `backend/tests/test_link_extractors.py`:

```python
from dataclasses import dataclass

import pytest

from app.parsers.link_extractors.base import ExtractedWork
from app.parsers.link_extractors.registry import extract_link_work


@dataclass
class DemoExtractor:
    platform: str = "demo"

    def supports(self, url: str) -> bool:
        return "demo.example" in url

    def extract(self, url: str, raw_text: str = "") -> ExtractedWork:
        return ExtractedWork(platform=self.platform, source_url=url, caption=raw_text, parse_method="demo")


def test_extract_link_work_routes_to_supported_extractor():
    work = extract_link_work("https://demo.example/item/1", "hello", extractors=[DemoExtractor()])

    assert work.platform == "demo"
    assert work.caption == "hello"
    assert work.parse_method == "demo"


def test_extract_link_work_unsupported_platform():
    with pytest.raises(ValueError, match="unsupported_platform"):
        extract_link_work("https://example.com/item/1", extractors=[DemoExtractor()])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/tests/test_link_extractors.py" -v
```

Expected: FAIL because registry does not exist.

- [ ] **Step 3: Implement registry**

Create `backend/app/parsers/link_extractors/registry.py`:

```python
from collections.abc import Iterable

from app.parsers.link_extractors.base import ExtractedWork, LinkExtractor


def default_extractors() -> list[LinkExtractor]:
    from app.parsers.link_extractors.douyin import DouyinLinkExtractor
    from app.parsers.link_extractors.wechat_channels import WeChatChannelsLinkExtractor
    from app.parsers.link_extractors.xiaohongshu import XiaohongshuLinkExtractor

    return [DouyinLinkExtractor(), XiaohongshuLinkExtractor(), WeChatChannelsLinkExtractor()]


def extract_link_work(url: str, raw_text: str = "", extractors: Iterable[LinkExtractor] | None = None) -> ExtractedWork:
    for extractor in extractors or default_extractors():
        if extractor.supports(url):
            return extractor.extract(url, raw_text)
    raise ValueError("unsupported_platform")
```

- [ ] **Step 4: Add placeholder extractor modules to satisfy imports**

Create `backend/app/parsers/link_extractors/douyin.py`:

```python
from app.parsers.base import hostname_matches
from app.parsers.link_extractors.base import ExtractedWork


class DouyinLinkExtractor:
    platform = "douyin"

    def supports(self, url: str) -> bool:
        return hostname_matches(url, {"douyin.com", "iesdouyin.com"})

    def extract(self, url: str, raw_text: str = "") -> ExtractedWork:
        return ExtractedWork(platform=self.platform, source_url=url, caption=raw_text, parse_method="placeholder")
```

Create `backend/app/parsers/link_extractors/xiaohongshu.py`:

```python
from app.parsers.base import hostname_matches
from app.parsers.link_extractors.base import ExtractedWork


class XiaohongshuLinkExtractor:
    platform = "xiaohongshu"

    def supports(self, url: str) -> bool:
        return hostname_matches(url, {"xiaohongshu.com", "xhslink.com"})

    def extract(self, url: str, raw_text: str = "") -> ExtractedWork:
        return ExtractedWork(platform=self.platform, source_url=url, caption=raw_text, parse_method="placeholder")
```

Create `backend/app/parsers/link_extractors/wechat_channels.py`:

```python
from app.parsers.base import hostname_matches
from app.parsers.link_extractors.base import ExtractedWork


class WeChatChannelsLinkExtractor:
    platform = "wechat_channels"

    def supports(self, url: str) -> bool:
        return hostname_matches(url, {"channels.weixin.qq.com"})

    def extract(self, url: str, raw_text: str = "") -> ExtractedWork:
        return ExtractedWork(platform=self.platform, source_url=url, caption=raw_text, parse_method="placeholder")
```

- [ ] **Step 5: Run tests**

Run the registry test command. Expected: PASS.

---

### Task 3: Implement Shared Public Page and yt-dlp Helpers

**Files:**
- Create: `backend/app/parsers/link_extractors/helpers.py`
- Modify: `backend/tests/test_link_extractors.py`

- [ ] **Step 1: Add helper tests**

Append:

```python
from app.parsers.link_extractors.helpers import extract_urls_by_suffix, pick_caption


def test_extract_urls_by_suffix_finds_video_and_images():
    html = '"https:\\/\\/cdn.example.com\\/a.mp4" "https://cdn.example.com/b.jpg"'

    assert extract_urls_by_suffix(html, (".mp4",)) == ["https://cdn.example.com/a.mp4"]
    assert extract_urls_by_suffix(html, (".jpg",)) == ["https://cdn.example.com/b.jpg"]


def test_pick_caption_prefers_platform_text():
    assert pick_caption("平台文案", "分享文案") == "平台文案"
    assert pick_caption("", "分享文案") == "分享文案"
```

- [ ] **Step 2: Run tests to verify failure**

Run `test_link_extractors.py`. Expected: FAIL because helpers do not exist.

- [ ] **Step 3: Implement helpers**

Create `backend/app/parsers/link_extractors/helpers.py`:

```python
import html
import re
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_public_page(url: str, timeout: int = 8) -> tuple[str, str]:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response.url, response.text


def meta_content(markup: str, key: str) -> str:
    soup = BeautifulSoup(markup, "lxml")
    for attrs in ({"property": key}, {"name": key}, {"itemprop": key}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return ""


def page_title(markup: str) -> str:
    soup = BeautifulSoup(markup, "lxml")
    tag = soup.find("title")
    return clean_text(tag.get_text(" ", strip=True)) if tag else ""


def extract_urls_by_suffix(markup: str, suffixes: tuple[str, ...]) -> list[str]:
    normalized = html.unescape(markup).replace("\\/", "/")
    normalized = normalized.encode("utf-8").decode("unicode_escape", errors="ignore")
    escaped = "|".join(re.escape(suffix.lstrip(".")) for suffix in suffixes)
    pattern = rf"https?://[^\"'\s<>]+?\.(?:{escaped})(?:\?[^\"'\s<>]*)?"
    urls = [clean_text(unquote(item)) for item in re.findall(pattern, normalized, flags=re.IGNORECASE)]
    deduped: list[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def pick_caption(*values: str) -> str:
    for value in values:
        cleaned = clean_text(value)
        if cleaned:
            return cleaned
    return ""


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip(" ，。；、\n\t")
```

- [ ] **Step 4: Run tests**

Run `test_link_extractors.py`. Expected: PASS for helper tests.

---

### Task 4: Implement Douyin Extractor

**Files:**
- Modify: `backend/app/parsers/link_extractors/douyin.py`
- Modify: `backend/tests/test_link_extractors.py`

- [ ] **Step 1: Add Douyin extractor tests with mocked helpers**

Append:

```python
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork
from app.parsers.link_extractors.douyin import DouyinLinkExtractor


def test_douyin_extractor_uses_public_page_video(monkeypatch):
    def fake_fetch(url: str, timeout: int = 8):
        return (
            "https://www.douyin.com/video/123",
            '<meta property="og:title" content="抖音标题">'
            '<meta property="og:description" content="抖音文案">'
            '"https://cdn.example.com/video.mp4"',
        )

    monkeypatch.setattr("app.parsers.link_extractors.douyin.fetch_public_page", fake_fetch)

    work = DouyinLinkExtractor().extract("https://v.douyin.com/abc", "")

    assert work.platform == "douyin"
    assert work.source_url == "https://www.douyin.com/video/123"
    assert work.media_type == "video"
    assert work.caption == "抖音文案"
    assert work.assets == [ExtractedAsset(type="video", source_url="https://cdn.example.com/video.mp4", mime_type="video/mp4")]
    assert work.parse_method == "public_page"


def test_douyin_extractor_uses_ytdlp_when_public_page_has_no_video(monkeypatch):
    def fake_fetch(url: str, timeout: int = 8):
        return ("https://www.douyin.com/video/123", "<title>抖音标题</title>")

    def fake_ytdlp(url: str):
        return ExtractedWork(
            platform="douyin",
            source_url=url,
            media_type="video",
            caption="yt 文案",
            assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")],
            parse_method="yt_dlp",
        )

    monkeypatch.setattr("app.parsers.link_extractors.douyin.fetch_public_page", fake_fetch)
    monkeypatch.setattr("app.parsers.link_extractors.douyin.extract_with_ytdlp", fake_ytdlp)

    work = DouyinLinkExtractor().extract("https://www.douyin.com/video/123", "")

    assert work.caption == "yt 文案"
    assert work.assets[0].source_url == "https://cdn.example.com/yt.mp4"
```

- [ ] **Step 2: Run tests to verify failure**

Run `test_link_extractors.py`. Expected: FAIL because implementation does not parse public pages or yt-dlp.

- [ ] **Step 3: Implement Douyin extractor**

Replace `backend/app/parsers/link_extractors/douyin.py` with:

```python
from app.parsers.base import hostname_matches
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork, LinkExtractionError
from app.parsers.link_extractors.helpers import extract_urls_by_suffix, fetch_public_page, meta_content, page_title, pick_caption
from app.parsers.link_extractors.ytdlp import extract_with_ytdlp


class DouyinLinkExtractor:
    platform = "douyin"

    def supports(self, url: str) -> bool:
        return hostname_matches(url, {"douyin.com", "iesdouyin.com"})

    def extract(self, url: str, raw_text: str = "") -> ExtractedWork:
        final_url, markup = fetch_public_page(url)
        video_urls = extract_urls_by_suffix(markup, (".mp4", ".m3u8"))
        caption = pick_caption(meta_content(markup, "og:description"), meta_content(markup, "description"), page_title(markup))
        title = pick_caption(meta_content(markup, "og:title"), page_title(markup))

        if video_urls:
            return ExtractedWork(
                platform=self.platform,
                source_url=final_url,
                media_type="video",
                caption=caption,
                title=title,
                cover_url=meta_content(markup, "og:image") or None,
                assets=[ExtractedAsset(type="video", source_url=video_urls[0], mime_type="video/mp4")],
                parse_method="public_page",
            )

        work = extract_with_ytdlp(final_url)
        if work.assets:
            work.platform = self.platform
            return work

        raise LinkExtractionError("cookie_expired_or_required", "抖音解析失败，请更新 backend/data/cookies.txt")
```

- [ ] **Step 4: Implement yt-dlp helper**

Create `backend/app/parsers/link_extractors/ytdlp.py`:

```python
from pathlib import Path

from app.core.config import settings
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork


def extract_with_ytdlp(url: str) -> ExtractedWork:
    from yt_dlp import YoutubeDL

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bv*+ba/best",
    }
    if settings.ytdlp_cookies_file and Path(settings.ytdlp_cookies_file).exists():
        options["cookiefile"] = settings.ytdlp_cookies_file

    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)

    media_url = info.get("url") or ""
    if not media_url:
        formats = sorted(
            [item for item in info.get("formats", []) if item.get("url")],
            key=lambda item: (item.get("height") or 0, item.get("tbr") or 0),
            reverse=True,
        )
        media_url = formats[0]["url"] if formats else ""

    assets = [ExtractedAsset(type="video", source_url=media_url, mime_type="video/mp4")] if media_url else []
    return ExtractedWork(
        platform="unknown",
        source_url=info.get("webpage_url") or url,
        media_type="video" if assets else "unknown",
        caption=info.get("description") or info.get("title") or "",
        title=info.get("title") or "",
        cover_url=info.get("thumbnail") or None,
        assets=assets,
        parse_method="yt_dlp",
    )
```

- [ ] **Step 5: Run tests**

Run `test_link_extractors.py`. Expected: PASS.

---

### Task 5: Implement Xiaohongshu Extractor

**Files:**
- Modify: `backend/app/parsers/link_extractors/xiaohongshu.py`
- Modify: `backend/tests/test_link_extractors.py`

- [ ] **Step 1: Add Xiaohongshu tests**

Append:

```python
from app.parsers.link_extractors.xiaohongshu import XiaohongshuLinkExtractor


def test_xiaohongshu_extractor_extracts_images(monkeypatch):
    markup = """
    <meta property="og:title" content="小红书标题">
    <meta name="description" content="小红书正文">
    "https://sns-img.example.com/a.jpg"
    "https://sns-img.example.com/b.png"
    """

    monkeypatch.setattr("app.parsers.link_extractors.xiaohongshu.fetch_public_page", lambda url, timeout=8: ("https://www.xiaohongshu.com/explore/123", markup))

    work = XiaohongshuLinkExtractor().extract("https://xhslink.com/abc", "")

    assert work.platform == "xiaohongshu"
    assert work.media_type == "image"
    assert work.caption == "小红书正文"
    assert [asset.type for asset in work.assets] == ["image", "image"]


def test_xiaohongshu_extractor_extracts_video(monkeypatch):
    markup = '"https://sns-video.example.com/a.mp4"'

    monkeypatch.setattr("app.parsers.link_extractors.xiaohongshu.fetch_public_page", lambda url, timeout=8: ("https://www.xiaohongshu.com/explore/123", markup))

    work = XiaohongshuLinkExtractor().extract("https://www.xiaohongshu.com/explore/123", "")

    assert work.media_type == "video"
    assert work.assets[0].type == "video"
```

- [ ] **Step 2: Run tests to verify failure**

Run `test_link_extractors.py`. Expected: FAIL.

- [ ] **Step 3: Implement Xiaohongshu extractor**

Replace `backend/app/parsers/link_extractors/xiaohongshu.py` with:

```python
from app.parsers.base import hostname_matches
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork, LinkExtractionError
from app.parsers.link_extractors.helpers import extract_urls_by_suffix, fetch_public_page, meta_content, page_title, pick_caption
from app.parsers.link_extractors.ytdlp import extract_with_ytdlp


class XiaohongshuLinkExtractor:
    platform = "xiaohongshu"

    def supports(self, url: str) -> bool:
        return hostname_matches(url, {"xiaohongshu.com", "xhslink.com"})

    def extract(self, url: str, raw_text: str = "") -> ExtractedWork:
        final_url, markup = fetch_public_page(url)
        caption = pick_caption(meta_content(markup, "description"), meta_content(markup, "og:description"), page_title(markup))
        title = pick_caption(meta_content(markup, "og:title"), page_title(markup))
        video_urls = extract_urls_by_suffix(markup, (".mp4", ".m3u8"))
        image_urls = extract_urls_by_suffix(markup, (".jpg", ".jpeg", ".png", ".webp"))

        if video_urls:
            return ExtractedWork(
                platform=self.platform,
                source_url=final_url,
                media_type="video",
                caption=caption,
                title=title,
                assets=[ExtractedAsset(type="video", source_url=video_urls[0], mime_type="video/mp4")],
                parse_method="public_page",
            )

        if image_urls:
            return ExtractedWork(
                platform=self.platform,
                source_url=final_url,
                media_type="image",
                caption=caption,
                title=title,
                assets=[ExtractedAsset(type="image", source_url=url, mime_type=_image_mime(url)) for url in image_urls],
                parse_method="public_page",
            )

        work = extract_with_ytdlp(final_url)
        if work.assets:
            work.platform = self.platform
            return work

        raise LinkExtractionError("cookie_expired_or_required", "小红书解析失败，请更新 backend/data/cookies.txt")


def _image_mime(url: str) -> str:
    lowered = url.lower()
    if ".png" in lowered:
        return "image/png"
    if ".webp" in lowered:
        return "image/webp"
    return "image/jpeg"
```

- [ ] **Step 4: Run tests**

Run `test_link_extractors.py`. Expected: PASS.

---

### Task 6: Implement WeChat Channels Extractor

**Files:**
- Modify: `backend/app/parsers/link_extractors/wechat_channels.py`
- Modify: `backend/tests/test_link_extractors.py`

- [ ] **Step 1: Add WeChat Channels tests**

Append:

```python
from app.parsers.link_extractors.wechat_channels import WeChatChannelsLinkExtractor


def test_wechat_channels_extractor_extracts_video(monkeypatch):
    markup = """
    <meta property="og:title" content="视频号标题">
    <meta property="og:description" content="视频号文案">
    "https://finder.video.example.com/a.mp4"
    """

    monkeypatch.setattr("app.parsers.link_extractors.wechat_channels.fetch_public_page", lambda url, timeout=8: ("https://channels.weixin.qq.com/platform/post/123", markup))

    work = WeChatChannelsLinkExtractor().extract("https://channels.weixin.qq.com/platform/post/123", "")

    assert work.platform == "wechat_channels"
    assert work.media_type == "video"
    assert work.caption == "视频号文案"
    assert work.assets[0].source_url == "https://finder.video.example.com/a.mp4"
```

- [ ] **Step 2: Run tests to verify failure**

Run `test_link_extractors.py`. Expected: FAIL.

- [ ] **Step 3: Implement WeChat Channels extractor**

Replace `backend/app/parsers/link_extractors/wechat_channels.py` with:

```python
from app.parsers.base import hostname_matches
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork, LinkExtractionError
from app.parsers.link_extractors.helpers import extract_urls_by_suffix, fetch_public_page, meta_content, page_title, pick_caption
from app.parsers.link_extractors.ytdlp import extract_with_ytdlp


class WeChatChannelsLinkExtractor:
    platform = "wechat_channels"

    def supports(self, url: str) -> bool:
        return hostname_matches(url, {"channels.weixin.qq.com"})

    def extract(self, url: str, raw_text: str = "") -> ExtractedWork:
        final_url, markup = fetch_public_page(url)
        caption = pick_caption(meta_content(markup, "og:description"), meta_content(markup, "description"), page_title(markup))
        title = pick_caption(meta_content(markup, "og:title"), page_title(markup))
        video_urls = extract_urls_by_suffix(markup, (".mp4", ".m3u8"))

        if video_urls:
            return ExtractedWork(
                platform=self.platform,
                source_url=final_url,
                media_type="video",
                caption=caption,
                title=title,
                assets=[ExtractedAsset(type="video", source_url=video_urls[0], mime_type="video/mp4")],
                parse_method="public_page",
            )

        work = extract_with_ytdlp(final_url)
        if work.assets:
            work.platform = self.platform
            return work

        raise LinkExtractionError("cookie_expired_or_required", "视频号解析失败，请更新 backend/data/cookies.txt")
```

- [ ] **Step 4: Run tests**

Run `test_link_extractors.py`. Expected: PASS.

---

### Task 7: Implement Local Asset Downloader

**Files:**
- Create: `backend/app/workers/processors/link_assets.py`
- Test: `backend/tests/test_link_asset_downloader.py`

- [ ] **Step 1: Write downloader tests**

Create `backend/tests/test_link_asset_downloader.py`:

```python
from pathlib import Path

from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork
from app.workers.processors.link_assets import download_work_assets


class FakeResponse:
    def __init__(self, body: bytes, content_type: str):
        self.body = body
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_download_work_assets_video(monkeypatch, tmp_path):
    work = ExtractedWork(
        platform="douyin",
        source_url="https://www.douyin.com/video/123",
        media_type="video",
        caption="文案",
        assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/a.mp4", mime_type="video/mp4")],
        parse_method="public_page",
    )

    monkeypatch.setattr("app.workers.processors.link_assets.requests.get", lambda *args, **kwargs: FakeResponse(b"video", "video/mp4"))
    monkeypatch.setattr("app.workers.processors.link_assets.settings.media_root", str(tmp_path))

    result = download_work_assets("task-1", work)

    assert result["assets"][0]["local_url"] == "/media/link_assets/task-1/video_1.mp4"
    assert (tmp_path / "link_assets" / "task-1" / "video_1.mp4").read_bytes() == b"video"
    assert result["download_status"] == "success"


def test_download_work_assets_images(monkeypatch, tmp_path):
    work = ExtractedWork(
        platform="xiaohongshu",
        source_url="https://www.xiaohongshu.com/explore/123",
        media_type="image",
        caption="文案",
        assets=[
            ExtractedAsset(type="image", source_url="https://cdn.example.com/a.jpg", mime_type="image/jpeg"),
            ExtractedAsset(type="image", source_url="https://cdn.example.com/b.png", mime_type="image/png"),
        ],
        parse_method="public_page",
    )

    monkeypatch.setattr("app.workers.processors.link_assets.requests.get", lambda *args, **kwargs: FakeResponse(b"image", "image/jpeg"))
    monkeypatch.setattr("app.workers.processors.link_assets.settings.media_root", str(tmp_path))

    result = download_work_assets("task-2", work)

    assert [asset["type"] for asset in result["assets"]] == ["image", "image"]
    assert result["assets"][0]["local_url"] == "/media/link_assets/task-2/image_1.jpg"
    assert result["assets"][1]["local_url"] == "/media/link_assets/task-2/image_2.png"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/tests/test_link_asset_downloader.py" -v
```

Expected: FAIL because downloader does not exist.

- [ ] **Step 3: Implement downloader**

Create `backend/app/workers/processors/link_assets.py`:

```python
from pathlib import Path

import requests

from app.core.config import settings
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    )
}


def download_work_assets(task_id: str, work: ExtractedWork) -> dict:
    target_dir = Path(settings.media_root) / "link_assets" / task_id
    target_dir.mkdir(parents=True, exist_ok=True)

    local_assets = []
    for index, asset in enumerate(work.assets, start=1):
        suffix = _suffix_for_asset(asset)
        filename = f"{asset.type}_{index}{suffix}"
        target_path = target_dir / filename
        _download(asset.source_url, target_path)
        local_assets.append(
            {
                "type": asset.type,
                "source_url": asset.source_url,
                "local_url": _public_url(target_path),
                "mime_type": asset.mime_type or _mime_from_suffix(suffix),
            }
        )

    return {
        "platform": work.platform,
        "source_url": work.source_url,
        "media_type": work.media_type,
        "caption": work.caption,
        "title": work.title,
        "author": work.author,
        "cover_url": work.cover_url,
        "assets": local_assets,
        "parse_method": work.parse_method,
        "download_status": "success" if local_assets else "empty",
    }


def _download(url: str, target_path: Path) -> None:
    with requests.get(url, headers=REQUEST_HEADERS, stream=True, timeout=60) as response:
        response.raise_for_status()
        with target_path.open("wb") as target_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    target_file.write(chunk)


def _suffix_for_asset(asset: ExtractedAsset) -> str:
    lowered = asset.source_url.lower().split("?", 1)[0]
    for suffix in (".mp4", ".m3u8", ".jpg", ".jpeg", ".png", ".webp"):
        if lowered.endswith(suffix):
            return ".jpg" if suffix == ".jpeg" else suffix
    if asset.type == "video":
        return ".mp4"
    return ".jpg"


def _mime_from_suffix(suffix: str) -> str:
    if suffix == ".mp4":
        return "video/mp4"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


def _public_url(path: Path) -> str:
    relative = path.relative_to(Path(settings.media_root))
    return f"{settings.public_media_prefix}/{relative.as_posix()}"
```

- [ ] **Step 4: Run downloader tests**

Run the same downloader test command. Expected: PASS.

---

### Task 8: Integrate Link Parse Worker Result

**Files:**
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/tests/test_worker_dispatch.py`

- [ ] **Step 1: Add worker tests for new result structure**

Update `test_run_link_parse_task` in `backend/tests/test_worker_dispatch.py`:

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

    monkeypatch.setattr("app.workers.tasks.extract_link_work", fake_extract)
    monkeypatch.setattr("app.workers.tasks.download_work_assets", fake_download)

    result = _run_task(TaskType.link_parse, {"url": "https://www.douyin.com/video/123", "raw_text": "分享文案", "task_id": "test-task"})

    assert result["platform"] == "douyin"
    assert result["media_type"] == "video"
    assert result["caption"] == "平台文案"
    assert result["assets"][0]["local_url"] == "/media/link_assets/test-task/video_1.mp4"
    assert result["download_status"] == "success"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/tests/test_worker_dispatch.py::test_run_link_parse_task" -v
```

Expected: FAIL because `tasks.py` still uses old parser/download flow.

- [ ] **Step 3: Update worker implementation**

In `backend/app/workers/tasks.py`:

```python
from app.parsers.link_extractors.registry import extract_link_work
from app.workers.processors.link_assets import download_work_assets
```

Change `dispatch_task` after JSON load:

```python
input_payload = json.loads(task.input_payload)
input_payload.setdefault("task_id", task_id)
result = _run_task(task.type, input_payload)
```

Replace the `TaskType.link_parse` branch in `_run_task` with:

```python
if task_type == TaskType.link_parse:
    work = extract_link_work(input_payload["url"], input_payload.get("raw_text", ""))
    return download_work_assets(input_payload.get("task_id", "preview"), work)
```

Keep existing branches for `remove_watermark`, `remove_subtitle`, `ocr_extract`, and `video_generate`.

- [ ] **Step 4: Run worker tests**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/tests/test_worker_dispatch.py" -v
```

Expected: PASS.

---

### Task 9: Update Frontend Types and Link Parse Page

**Files:**
- Modify: `frontend/src/types/task.ts`
- Modify: `frontend/src/pages/link-parse/link-parse.vue`

- [ ] **Step 1: Update TypeScript result type**

Replace `LinkParseResult` in `frontend/src/types/task.ts` with:

```ts
export interface LinkAsset {
  type: "video" | "image";
  source_url: string;
  local_url: string;
  mime_type: string;
}

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
}
```

- [ ] **Step 2: Update frontend render logic**

In `frontend/src/pages/link-parse/link-parse.vue`, replace the result section with:

```vue
<view v-if="result" class="panel">
  <text class="section-title">解析结果</text>
  <view class="result-line">
    <text class="key">平台</text>
    <text class="value">{{ result.platform || "-" }}</text>
  </view>
  <view class="result-line">
    <text class="key">作品类型</text>
    <text class="value">{{ result.media_type || "-" }}</text>
  </view>
  <view class="result-block highlight">
    <text class="key">作品文案</text>
    <text class="value">{{ result.caption || "-" }}</text>
    <button v-if="result.caption" class="copy-button" @tap="copy(result.caption)">复制文案</button>
  </view>
  <view class="result-block highlight">
    <text class="key">媒体文件</text>
    <view v-for="(asset, index) in result.assets || []" :key="asset.local_url" class="media-item">
      <text>{{ asset.type }} {{ index + 1 }}</text>
      <text class="media-url">{{ asset.local_url }}</text>
      <button class="copy-button" @tap="downloadAsset(asset)">下载到本地</button>
    </view>
  </view>
  <view class="result-block">
    <text class="key">解析方式</text>
    <text class="value">{{ result.parse_method || "-" }} / {{ result.download_status || "-" }}</text>
  </view>
</view>
```

Add script helper:

```ts
import type { LinkAsset, LinkParseResult, TaskResponse } from "../../types/task";

function downloadAsset(asset: LinkAsset) {
  const targetUrl = toAbsoluteUrl(asset.local_url);
  uni.downloadFile({
    url: targetUrl,
    success: (response) => {
      if (response.statusCode !== 200) {
        showError(new Error("下载失败"));
        return;
      }
      if (asset.type === "video") {
        uni.saveVideoToPhotosAlbum({
          filePath: response.tempFilePath,
          success: () => uni.showToast({ title: "已保存到相册", icon: "success" }),
          fail: () => showError(new Error("保存失败，请检查相册权限")),
        });
        return;
      }
      uni.saveImageToPhotosAlbum({
        filePath: response.tempFilePath,
        success: () => uni.showToast({ title: "已保存到相册", icon: "success" }),
        fail: () => showError(new Error("保存失败，请检查相册权限")),
      });
    },
    fail: () => showError(new Error("下载失败")),
  });
}
```

- [ ] **Step 3: Build frontend**

Run:

```bash
cd "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/frontend"
source "$HOME/.nvm/nvm.sh" && nvm use 24.13.0 && npm run build:mp-weixin
```

Expected: `DONE  Build complete.`

---

### Task 10: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run backend tests**

Run:

```bash
PYTHONPATH="/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/.venv/bin/pytest" "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/backend/tests"
```

Expected: all tests pass.

- [ ] **Step 2: Rebuild/restart backend stack**

Run:

```bash
cd "/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools"
docker compose up --build -d backend worker redis
```

Expected: backend, worker, redis running. If PyPI timeout occurs during Docker build, retry once after Docker network recovers.

- [ ] **Step 3: Health check**

Run:

```bash
curl -sS http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

- [ ] **Step 4: Manual platform checks**

Use the FastAPI docs or mini program page with real links:

- Douyin video link should return `media_type: "video"` and at least one asset with `/media/link_assets/...`.
- Xiaohongshu image note should return `media_type: "image"` and multiple image assets.
- Xiaohongshu video note should return `media_type: "video"` and one video asset.
- WeChat Channels link should return `media_type: "video"` or a clear `cookie_expired_or_required` failure.

- [ ] **Step 5: Frontend import**

Open WeChat Developer Tools and import:

```text
/Users/luckincoffee/Desktop/cxj/tools/.worktrees/media-tools/media-tools/frontend/dist/build/mp-weixin
```

Expected: link parse page shows caption, media cards, and download buttons.

---

## Self-Review

Spec coverage:

- Supported platforms: Tasks 4, 5, 6 cover Douyin, Xiaohongshu, and WeChat Channels.
- Cookie strategy: Task 4/5/6 route through `extract_with_ytdlp`, which reads `settings.ytdlp_cookies_file`.
- Local media assets: Task 7 downloads into `MEDIA_ROOT/link_assets/<task_id>/`.
- Worker integration: Task 8 keeps existing `link_parse` API while changing result payload.
- Frontend display and download: Task 9 updates types and page behavior.
- Verification: Task 10 covers tests, Docker, health check, and manual platform checks.

Placeholder scan:

- No placeholder markers are intentionally left.
- Every error-handling step names the exact behavior or code path.

Type consistency:

- Backend returns `assets`, `media_type`, `caption`, `parse_method`, and `download_status`.
- Frontend `LinkParseResult` uses the same field names.
- `ExtractedAsset.type` matches frontend `LinkAsset.type`.
