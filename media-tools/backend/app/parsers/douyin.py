from app.parsers.base import MediaType, ParsedContent, ParsedMedia, PlatformParser, hostname_matches


class DouyinParser(PlatformParser):
    platform = "douyin"

    def supports(self, url: str) -> bool:
        return hostname_matches(url, {"douyin.com", "iesdouyin.com"})

    def parse(self, url: str) -> ParsedContent:
        return ParsedContent(
            platform=self.platform,
            source_url=url,
            title="抖音内容",
            description="抖音链接解析器已识别该链接，真实解析逻辑将在平台适配阶段接入。",
            author="",
            media=[ParsedMedia(type=MediaType.video, url=url)],
        )
