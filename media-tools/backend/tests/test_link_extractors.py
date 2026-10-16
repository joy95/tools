import sys
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.parsers.link_extractors import ytdlp
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork, LinkExtractionError
from app.parsers.link_extractors.douyin import DouyinLinkExtractor
from app.parsers.link_extractors.helpers import extract_urls_by_suffix, pick_caption
from app.parsers.link_extractors.registry import extract_link_work
from app.parsers.link_extractors.wechat_channels import WeChatChannelsLinkExtractor
from app.parsers.link_extractors.xiaohongshu import XiaohongshuLinkExtractor


def test_extracted_work_defaults():
    work = ExtractedWork(platform="douyin", source_url="https://www.douyin.com/video/123")

    assert work.platform == "douyin"
    assert work.source_url == "https://www.douyin.com/video/123"
    assert work.media_type == "unknown"
    assert work.caption == ""
    assert work.title == ""
    assert work.author == ""
    assert work.cover_url is None
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


def test_extract_link_work_respects_empty_extractors():
    with pytest.raises(ValueError, match="unsupported_platform"):
        extract_link_work("https://www.douyin.com/video/123", extractors=[])


def test_extract_urls_by_suffix_finds_video_and_images():
    html = '"https:\\/\\/cdn.example.com\\/a.mp4" "https://cdn.example.com/b.jpg"'

    assert extract_urls_by_suffix(html, (".mp4",)) == ["https://cdn.example.com/a.mp4"]
    assert extract_urls_by_suffix(html, (".jpg",)) == ["https://cdn.example.com/b.jpg"]


def test_extract_urls_by_suffix_preserves_encoded_signature_query():
    html = '"https://cdn.example.com/a.mp4?token=a%26b%2Bc%3D"'

    assert extract_urls_by_suffix(html, (".mp4",)) == [
        "https://cdn.example.com/a.mp4?token=a%26b%2Bc%3D"
    ]


def test_extract_urls_by_suffix_preserves_non_ascii_path():
    html = '"https://cdn.example.com/咖啡.mp4"'

    assert extract_urls_by_suffix(html, (".mp4",)) == ["https://cdn.example.com/咖啡.mp4"]


def test_extract_urls_by_suffix_does_not_truncate_hls_urls():
    html = (
        '"https://cdn.example.com/video.mp4.m3u8" '
        '"https://cdn.example.com/video.mp4/master.m3u8" '
        '"https://cdn.example.com/real.mp4?token=a%26b"'
    )

    assert extract_urls_by_suffix(html, (".mp4",)) == ["https://cdn.example.com/real.mp4?token=a%26b"]
    assert extract_urls_by_suffix(html, (".m3u8",)) == [
        "https://cdn.example.com/video.mp4.m3u8",
        "https://cdn.example.com/video.mp4/master.m3u8",
    ]


def test_pick_caption_prefers_platform_text():
    assert pick_caption("平台文案", "分享文案") == "平台文案"
    assert pick_caption("", "分享文案") == "分享文案"


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


def test_douyin_extractor_falls_back_when_public_page_only_has_m3u8(monkeypatch):
    def fake_fetch(url: str, timeout: int = 8):
        return (
            "https://www.douyin.com/video/123",
            '<meta property="og:description" content="抖音文案">'
            '"https://cdn.example.com/video.m3u8"',
        )

    def fake_ytdlp(url: str):
        return ExtractedWork(
            platform="unknown",
            source_url=url,
            media_type="video",
            assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")],
            parse_method="yt_dlp",
        )

    monkeypatch.setattr("app.parsers.link_extractors.douyin.fetch_public_page", fake_fetch)
    monkeypatch.setattr("app.parsers.link_extractors.douyin.extract_with_ytdlp", fake_ytdlp)

    work = DouyinLinkExtractor().extract("https://v.douyin.com/abc", "")

    assert work.platform == "douyin"
    assert work.assets == [ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")]
    assert work.parse_method == "yt_dlp"


def test_douyin_extractor_falls_back_when_public_page_fails(monkeypatch):
    def fake_ytdlp(url: str):
        return ExtractedWork(
            platform="unknown",
            source_url=url,
            media_type="video",
            assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")],
            parse_method="yt_dlp",
        )

    monkeypatch.setattr(
        "app.parsers.link_extractors.douyin.fetch_public_page",
        lambda url, timeout=8: (_ for _ in ()).throw(RuntimeError("public page boom")),
    )
    monkeypatch.setattr("app.parsers.link_extractors.douyin.extract_with_ytdlp", fake_ytdlp)

    work = DouyinLinkExtractor().extract("https://v.douyin.com/abc", "")

    assert work.platform == "douyin"
    assert work.assets[0].source_url == "https://cdn.example.com/yt.mp4"


def test_douyin_extractor_raises_platform_error_when_all_fallbacks_fail(monkeypatch):
    monkeypatch.setattr(
        "app.parsers.link_extractors.douyin.fetch_public_page",
        lambda url, timeout=8: (_ for _ in ()).throw(RuntimeError("public page boom")),
    )
    monkeypatch.setattr(
        "app.parsers.link_extractors.douyin.extract_with_ytdlp",
        lambda url: (_ for _ in ()).throw(LinkExtractionError("ytdlp_extract_failed", "yt-dlp 解析失败")),
    )

    with pytest.raises(LinkExtractionError) as exc_info:
        DouyinLinkExtractor().extract("https://v.douyin.com/abc", "")

    assert exc_info.value.code == "cookie_expired_or_required"


def test_xiaohongshu_extractor_extracts_images(monkeypatch):
    markup = """
    <meta property="og:title" content="小红书标题">
    <meta name="description" content="小红书正文">
    "https://sns-img.example.com/a.jpg?x=.png"
    "https://sns-img.example.com/a.jpg?x=.png"
    "https://sns-img.example.com/b.png"
    """

    monkeypatch.setattr(
        "app.parsers.link_extractors.xiaohongshu.fetch_public_page",
        lambda url, timeout=8: ("https://www.xiaohongshu.com/explore/123", markup),
    )

    work = XiaohongshuLinkExtractor().extract("https://xhslink.com/abc", "")

    assert work.platform == "xiaohongshu"
    assert work.media_type == "image"
    assert work.caption == "小红书正文"
    assert [asset.type for asset in work.assets] == ["image", "image"]
    assert [asset.source_url for asset in work.assets] == [
        "https://sns-img.example.com/a.jpg?x=.png",
        "https://sns-img.example.com/b.png",
    ]
    assert [asset.mime_type for asset in work.assets] == ["image/jpeg", "image/png"]


def test_xiaohongshu_extractor_extracts_video(monkeypatch):
    markup = '"https://sns-video.example.com/a.mp4"'

    monkeypatch.setattr(
        "app.parsers.link_extractors.xiaohongshu.fetch_public_page",
        lambda url, timeout=8: ("https://www.xiaohongshu.com/explore/123", markup),
    )

    work = XiaohongshuLinkExtractor().extract("https://www.xiaohongshu.com/explore/123", "")

    assert work.media_type == "video"
    assert work.assets[0].type == "video"


def test_xiaohongshu_extractor_falls_back_when_public_page_only_has_m3u8(monkeypatch):
    markup = '"https://sns-video.example.com/a.m3u8"'

    def fake_ytdlp(url: str):
        return ExtractedWork(
            platform="unknown",
            source_url=url,
            media_type="video",
            assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")],
            parse_method="yt_dlp",
        )

    monkeypatch.setattr(
        "app.parsers.link_extractors.xiaohongshu.fetch_public_page",
        lambda url, timeout=8: ("https://www.xiaohongshu.com/explore/123", markup),
    )
    monkeypatch.setattr("app.parsers.link_extractors.xiaohongshu.extract_with_ytdlp", fake_ytdlp)

    work = XiaohongshuLinkExtractor().extract("https://www.xiaohongshu.com/explore/123", "")

    assert work.platform == "xiaohongshu"
    assert work.assets == [ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")]
    assert work.parse_method == "yt_dlp"


def test_xiaohongshu_extractor_uses_ytdlp_when_public_page_has_no_assets(monkeypatch):
    def fake_ytdlp(url: str):
        return ExtractedWork(
            platform="unknown",
            source_url=url,
            media_type="video",
            caption="yt 文案",
            assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")],
            parse_method="yt_dlp",
        )

    monkeypatch.setattr(
        "app.parsers.link_extractors.xiaohongshu.fetch_public_page",
        lambda url, timeout=8: ("https://www.xiaohongshu.com/explore/123", "<title>小红书标题</title>"),
    )
    monkeypatch.setattr("app.parsers.link_extractors.xiaohongshu.extract_with_ytdlp", fake_ytdlp)

    work = XiaohongshuLinkExtractor().extract("https://www.xiaohongshu.com/explore/123", "")

    assert work.platform == "xiaohongshu"
    assert work.caption == "yt 文案"
    assert work.assets[0].source_url == "https://cdn.example.com/yt.mp4"


def test_xiaohongshu_extractor_raises_platform_error_when_all_fallbacks_fail(monkeypatch):
    monkeypatch.setattr(
        "app.parsers.link_extractors.xiaohongshu.fetch_public_page",
        lambda url, timeout=8: (_ for _ in ()).throw(RuntimeError("public page boom")),
    )
    monkeypatch.setattr(
        "app.parsers.link_extractors.xiaohongshu.extract_with_ytdlp",
        lambda url: (_ for _ in ()).throw(LinkExtractionError("ytdlp_extract_failed", "yt failed")),
    )

    with pytest.raises(LinkExtractionError) as exc_info:
        XiaohongshuLinkExtractor().extract("https://www.xiaohongshu.com/explore/123", "")

    assert exc_info.value.code == "cookie_expired_or_required"


def test_wechat_channels_extractor_extracts_video(monkeypatch):
    markup = """
    <meta property="og:title" content="视频号标题">
    <meta property="og:description" content="视频号文案">
    "https://finder.video.example.com/a.mp4"
    """

    monkeypatch.setattr(
        "app.parsers.link_extractors.wechat_channels.fetch_public_page",
        lambda url, timeout=8: ("https://channels.weixin.qq.com/platform/post/123", markup),
    )

    work = WeChatChannelsLinkExtractor().extract("https://channels.weixin.qq.com/platform/post/123", "")

    assert work.platform == "wechat_channels"
    assert work.media_type == "video"
    assert work.caption == "视频号文案"
    assert work.assets[0].source_url == "https://finder.video.example.com/a.mp4"


def test_wechat_channels_extractor_falls_back_when_public_page_only_has_m3u8(monkeypatch):
    markup = '"https://finder.video.example.com/a.m3u8"'

    def fake_ytdlp(url: str):
        return ExtractedWork(
            platform="unknown",
            source_url=url,
            media_type="video",
            assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")],
            parse_method="yt_dlp",
        )

    monkeypatch.setattr(
        "app.parsers.link_extractors.wechat_channels.fetch_public_page",
        lambda url, timeout=8: ("https://channels.weixin.qq.com/platform/post/123", markup),
    )
    monkeypatch.setattr("app.parsers.link_extractors.wechat_channels.extract_with_ytdlp", fake_ytdlp)

    work = WeChatChannelsLinkExtractor().extract("https://channels.weixin.qq.com/platform/post/123", "")

    assert work.platform == "wechat_channels"
    assert work.assets == [ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")]
    assert work.parse_method == "yt_dlp"


def test_wechat_channels_extractor_uses_ytdlp_when_public_page_has_no_video(monkeypatch):
    def fake_ytdlp(url: str):
        return ExtractedWork(
            platform="unknown",
            source_url=url,
            media_type="video",
            caption="yt 文案",
            assets=[ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")],
            parse_method="yt_dlp",
        )

    monkeypatch.setattr(
        "app.parsers.link_extractors.wechat_channels.fetch_public_page",
        lambda url, timeout=8: ("https://channels.weixin.qq.com/platform/post/123", "<title>视频号标题</title>"),
    )
    monkeypatch.setattr("app.parsers.link_extractors.wechat_channels.extract_with_ytdlp", fake_ytdlp)

    work = WeChatChannelsLinkExtractor().extract("https://channels.weixin.qq.com/platform/post/123", "")

    assert work.platform == "wechat_channels"
    assert work.assets == [
        ExtractedAsset(type="video", source_url="https://cdn.example.com/yt.mp4", mime_type="video/mp4")
    ]


def test_wechat_channels_extractor_raises_platform_error_when_all_fallbacks_fail(monkeypatch):
    monkeypatch.setattr(
        "app.parsers.link_extractors.wechat_channels.fetch_public_page",
        lambda url, timeout=8: (_ for _ in ()).throw(RuntimeError("public page boom")),
    )
    monkeypatch.setattr(
        "app.parsers.link_extractors.wechat_channels.extract_with_ytdlp",
        lambda url: (_ for _ in ()).throw(LinkExtractionError("ytdlp_extract_failed", "yt failed")),
    )

    with pytest.raises(LinkExtractionError) as exc_info:
        WeChatChannelsLinkExtractor().extract("https://channels.weixin.qq.com/platform/post/123", "")

    assert exc_info.value.code == "cookie_expired_or_required"


def test_ytdlp_prefers_mp4_over_m3u8_format(monkeypatch):
    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, url: str, download: bool = False):
            return {
                "webpage_url": url,
                "formats": [
                    {"url": "https://cdn.example.com/video.mp4", "height": 720, "tbr": 1000},
                    {"url": "https://cdn.example.com/video.m3u8", "height": 1080, "tbr": 2000},
                ],
            }

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYoutubeDL))

    work = ytdlp.extract_with_ytdlp("https://www.douyin.com/video/123")

    assert work.assets == [
        ExtractedAsset(
            type="video",
            source_url="https://cdn.example.com/video.mp4",
            mime_type="video/mp4",
        )
    ]


def test_ytdlp_rejects_m3u8_only_formats(monkeypatch):
    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, url: str, download: bool = False):
            return {
                "webpage_url": url,
                "formats": [
                    {"url": "https://cdn.example.com/video.m3u8", "height": 1080, "tbr": 2000, "protocol": "m3u8"},
                ],
            }

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYoutubeDL))

    with pytest.raises(LinkExtractionError) as exc_info:
        ytdlp.extract_with_ytdlp("https://www.douyin.com/video/123")

    assert exc_info.value.code == "ytdlp_extract_failed"


def test_ytdlp_wraps_extract_errors(monkeypatch):
    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, url: str, download: bool = False):
            raise RuntimeError("network boom")

    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYoutubeDL))

    with pytest.raises(LinkExtractionError) as exc_info:
        ytdlp.extract_with_ytdlp("https://www.douyin.com/video/123")

    assert exc_info.value.code == "ytdlp_extract_failed"


def test_ytdlp_wraps_import_errors(monkeypatch):
    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yt_dlp":
            raise ImportError("missing yt-dlp")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(LinkExtractionError) as exc_info:
        ytdlp.extract_with_ytdlp("https://www.douyin.com/video/123")

    assert exc_info.value.code == "ytdlp_unavailable"
