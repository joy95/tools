from app.parsers.base import hostname_matches
from app.parsers.link_extractors.base import ExtractedAsset, ExtractedWork, LinkExtractionError
from app.parsers.link_extractors.helpers import extract_urls_by_suffix, fetch_public_page, meta_content, page_title, pick_caption
from app.parsers.link_extractors.ytdlp import extract_with_ytdlp, video_mime_type


class DouyinLinkExtractor:
    platform = "douyin"

    def supports(self, url: str) -> bool:
        return hostname_matches(url, {"douyin.com", "iesdouyin.com"})

    def extract(self, url: str, raw_text: str = "") -> ExtractedWork:
        try:
            final_url, markup = fetch_public_page(url)
        except Exception:
            final_url, markup = url, ""

        video_urls = extract_urls_by_suffix(markup, (".mp4",))
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
                assets=[ExtractedAsset(type="video", source_url=video_urls[0], mime_type=video_mime_type(video_urls[0]))],
                parse_method="public_page",
            )

        try:
            work = extract_with_ytdlp(final_url)
        except Exception as exc:
            raise LinkExtractionError("cookie_expired_or_required", "抖音解析失败，请更新 backend/data/cookies.txt") from exc

        if work.assets and all(video_mime_type(asset.source_url) != "application/vnd.apple.mpegurl" for asset in work.assets):
            work.platform = self.platform
            return work

        raise LinkExtractionError("cookie_expired_or_required", "抖音解析失败，请更新 backend/data/cookies.txt")
