"""抓取层测试：HTTP 请求、编码识别、重试。使用 FakeSession，不依赖网络。"""
import requests
import pytest

from crawler.fetch import FetchError, decode_html, fetch_html


class FakeResponse:
    def __init__(self, content: bytes, url: str, status: int = 200):
        self.content = content
        self.url = url
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error for {self.url}")


class FakeSession:
    """依次吐出预设响应；预设为 Exception 时直接抛出。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.request_kwargs = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        self.request_kwargs.append(kwargs)
        if not self._responses:
            raise AssertionError("没有预设的响应了")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_decode_gbk_bytes():
    data = "北京市城市更新条例".encode("gbk")
    assert "北京市城市更新条例" in decode_html(data)


def test_decode_utf8_bytes():
    data = "住房城乡建设部城市更新行动".encode("utf-8")
    assert "城市更新行动" in decode_html(data)


def test_fetch_success_uses_timeout_and_ua():
    html = "<html>城市更新</html>"
    session = FakeSession([FakeResponse(html.encode("utf-8"), "https://example.gov.cn/a")])

    out = fetch_html(session, "https://example.gov.cn/a", timeout=8, retries=1)

    assert out == html
    kwargs = session.request_kwargs[0]
    assert kwargs["timeout"] == 8
    assert "User-Agent" in kwargs["headers"]


def test_fetch_retries_then_succeeds():
    session = FakeSession(
        [
            requests.ConnectionError("boom"),
            FakeResponse(b"<html>ok</html>", "https://example.gov.cn/a"),
        ]
    )

    out = fetch_html(session, "https://example.gov.cn/a", retries=1, retry_delay=0)

    assert "ok" in out
    assert len(session.calls) == 2


def test_fetch_raises_fetch_error_after_retries_exhausted():
    session = FakeSession(
        [
            requests.ConnectionError("boom"),
            requests.ConnectionError("boom2"),
        ]
    )

    with pytest.raises(FetchError):
        fetch_html(session, "https://example.gov.cn/a", retries=1, retry_delay=0)


def test_fetch_http_error_raises_fetch_error():
    session = FakeSession([FakeResponse(b"", "https://example.gov.cn/a", status=404)])

    with pytest.raises(FetchError):
        fetch_html(session, "https://example.gov.cn/a", retries=0)
