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
