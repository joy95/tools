import html
import re
from urllib.parse import urlsplit

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
    normalized = normalized.replace("\\u002F", "/").replace("\\u002f", "/")
    normalized = normalized.replace("\\u0026", "&")
    wanted_suffixes = tuple(f".{suffix.lstrip('.').lower()}" for suffix in suffixes)
    candidates = re.findall(r"https?://[^\"'\s<>]+", normalized, flags=re.IGNORECASE)
    urls = [
        clean_text(candidate)
        for candidate in candidates
        if urlsplit(candidate).path.lower().endswith(wanted_suffixes)
    ]
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
