from collections.abc import Iterable

from app.parsers.link_extractors.base import ExtractedWork, LinkExtractor


def default_extractors() -> list[LinkExtractor]:
    from app.parsers.link_extractors.douyin import DouyinLinkExtractor
    from app.parsers.link_extractors.wechat_channels import WeChatChannelsLinkExtractor
    from app.parsers.link_extractors.xiaohongshu import XiaohongshuLinkExtractor

    return [DouyinLinkExtractor(), XiaohongshuLinkExtractor(), WeChatChannelsLinkExtractor()]


def extract_link_work(url: str, raw_text: str = "", extractors: Iterable[LinkExtractor] | None = None) -> ExtractedWork:
    active_extractors = default_extractors() if extractors is None else extractors
    for extractor in active_extractors:
        if extractor.supports(url):
            return extractor.extract(url, raw_text)
    raise ValueError("unsupported_platform")
