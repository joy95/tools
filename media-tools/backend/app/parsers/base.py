from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse


class MediaType(str, Enum):
    image = "image"
    video = "video"


@dataclass
class ParsedMedia:
    type: MediaType
    url: str


@dataclass
class ParsedContent:
    platform: str
    source_url: str
    title: str
    description: str
    author: str
    cover_url: str | None = None
    media: list[ParsedMedia] = field(default_factory=list)


class PlatformParser:
    platform: str

    def supports(self, url: str) -> bool:
        raise NotImplementedError

    def parse(self, url: str) -> ParsedContent:
        raise NotImplementedError


def hostname_matches(url: str, allowed_hosts: set[str]) -> bool:
    hostname = urlparse(url).hostname
    if hostname is None:
        return False

    hostname = hostname.lower().rstrip(".")
    for allowed_host in allowed_hosts:
        normalized_host = allowed_host.lower().rstrip(".")
        if hostname == normalized_host or hostname.endswith(f".{normalized_host}"):
            return True
    return False
