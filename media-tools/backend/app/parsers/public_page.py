import html
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup


@dataclass
class PublicPageExtraction:
    final_url: str
    title: str = ""
    description: str = ""
    author: str = ""
    cover_url: str | None = None
    video_url: str = ""


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def extract_public_page(url: str, timeout: int = 8) -> PublicPageExtraction:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout, allow_redirects=True)
    response.raise_for_status()

    content = response.text
    soup = BeautifulSoup(content, "lxml")
    extracted = PublicPageExtraction(final_url=response.url)

    extracted.title = _first_text(
        _meta_content(soup, "og:title"),
        _meta_content(soup, "twitter:title"),
        _tag_text(soup, "title"),
    )
    extracted.description = _first_text(
        _meta_content(soup, "og:description"),
        _meta_content(soup, "description"),
        _meta_content(soup, "twitter:description"),
    )
    extracted.author = _first_text(_meta_content(soup, "author"), _meta_content(soup, "article:author"))
    extracted.cover_url = _first_text(
        _meta_content(soup, "og:image"),
        _meta_content(soup, "twitter:image"),
        _meta_content(soup, "image"),
    ) or None
    extracted.video_url = _first_text(
        _meta_content(soup, "og:video"),
        _meta_content(soup, "og:video:url"),
        _meta_content(soup, "og:video:secure_url"),
        _meta_content(soup, "twitter:player:stream"),
        _video_tag_src(soup),
        _json_ld_value(soup, ("contentUrl", "embedUrl", "url")),
        _regex_video_url(content),
    )

    return extracted


def _meta_content(soup: BeautifulSoup, key: str) -> str:
    selectors = [
        {"property": key},
        {"name": key},
        {"itemprop": key},
    ]
    for attrs in selectors:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return _clean(tag["content"])
    return ""


def _tag_text(soup: BeautifulSoup, tag_name: str) -> str:
    tag = soup.find(tag_name)
    return _clean(tag.get_text(" ", strip=True)) if tag else ""


def _video_tag_src(soup: BeautifulSoup) -> str:
    for tag_name in ("video", "source"):
        tag = soup.find(tag_name)
        if tag and tag.get("src"):
            return _clean(tag["src"])
    return ""


def _json_ld_value(soup: BeautifulSoup, keys: tuple[str, ...]) -> str:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        value = _walk_json_for_value(data, keys)
        if value:
            return _clean(value)
    return ""


def _walk_json_for_value(value: Any, keys: tuple[str, ...]) -> str:
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                return candidate
        for child in value.values():
            found = _walk_json_for_value(child, keys)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _walk_json_for_value(child, keys)
            if found:
                return found
    return ""


def _regex_video_url(content: str) -> str:
    normalized = html.unescape(content).replace("\\/", "/")
    normalized = normalized.encode("utf-8").decode("unicode_escape", errors="ignore")
    candidates = re.findall(r"https?://[^\"'\s<>]+?\.(?:mp4|m3u8)(?:\?[^\"'\s<>]*)?", normalized, flags=re.IGNORECASE)
    if not candidates:
        return ""

    decoded = [_clean(unquote(candidate)) for candidate in candidates]
    decoded.sort(key=_video_score, reverse=True)
    return decoded[0]


def _video_score(url: str) -> int:
    score = 0
    lowered = url.lower()
    if "watermark" not in lowered and "%e6%b0%b4%e5%8d%b0" not in lowered:
        score += 2
    if ".mp4" in lowered:
        score += 1
    if "play" in lowered or "video" in lowered:
        score += 1
    return score


def _first_text(*values: str | None) -> str:
    for value in values:
        if value:
            return _clean(value)
    return ""


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()
