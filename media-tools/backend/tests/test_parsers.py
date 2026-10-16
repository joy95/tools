import pytest

from app.parsers.registry import parse_platform_link


def test_parse_douyin_link():
    url = "https://www.douyin.com/video/123"

    result = parse_platform_link(url)

    assert result.platform == "douyin"
    assert result.source_url == url
    assert result.title
    assert result.description
    assert result.author == ""
    assert result.media[0].type == "video"
    assert result.media[0].url == url


def test_parse_xiaohongshu_link():
    url = "https://www.xiaohongshu.com/explore/123"

    result = parse_platform_link(url)

    assert result.platform == "xiaohongshu"
    assert result.source_url == url
    assert result.title
    assert result.description
    assert result.author == ""
    assert result.media[0].type == "image"
    assert result.media[0].url == url


def test_parse_wechat_channels_link():
    url = "https://channels.weixin.qq.com/platform/post/123"

    result = parse_platform_link(url)

    assert result.platform == "wechat_channels"
    assert result.source_url == url
    assert result.title
    assert result.description
    assert result.author == ""
    assert result.media[0].type == "video"
    assert result.media[0].url == url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/item/123?target=https://www.douyin.com/video/123",
        "https://douyin.com.evil.test/video/123",
        "https://www.xiaohongshu.com.evil.test/explore/123",
        "https://weixin.qq.com/some/article/123",
        "https://example.com/item/123",
    ],
)
def test_unsupported_link_raises(url):
    with pytest.raises(ValueError, match="unsupported_platform"):
        parse_platform_link(url)
