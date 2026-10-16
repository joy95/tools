from app.parsers.base import MediaType, ParsedContent, ParsedMedia, PlatformParser, hostname_matches


class XiaohongshuParser(PlatformParser):
    platform = "xiaohongshu"

    def supports(self, url: str) -> bool:
        return hostname_matches(url, {"xiaohongshu.com", "xhslink.com"})

    def parse(self, url: str) -> ParsedContent:
        return ParsedContent(
            platform=self.platform,
            source_url=url,
            title="小红书内容",
            description="小红书链接解析器已识别该链接，真实解析逻辑将在平台适配阶段接入。",
            author="",
            media=[ParsedMedia(type=MediaType.image, url=url)],
        )
