from app.parsers.base import ParsedContent
from app.parsers.douyin import DouyinParser
from app.parsers.wechat_channels import WeChatChannelsParser
from app.parsers.xiaohongshu import XiaohongshuParser


PARSERS = [DouyinParser(), XiaohongshuParser(), WeChatChannelsParser()]


def parse_platform_link(url: str) -> ParsedContent:
    for parser in PARSERS:
        if parser.supports(url):
            return parser.parse(url)
    raise ValueError("unsupported_platform")
