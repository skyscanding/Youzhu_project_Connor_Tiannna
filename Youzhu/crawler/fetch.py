"""抓取层：HTTP 请求、编码识别、重试。"""
import time

import requests
from bs4 import UnicodeDammit

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 policy-monitor/0.1"
)


class FetchError(Exception):
    """抓取失败（网络不可达、超时、HTTP 错误等）。"""


def decode_html(data: bytes) -> str:
    """按页面实际编码解码（政府站点常见 GBK/GB2312/UTF-8）。

    UTF-8 必须排在首位（GBK 能"成功"解码任意字节，顺序反了会把
    UTF-8 页面解成乱码）；无提示时 UnicodeDammit 会把 GBK 误判为
    EUC-KR，因此显式给出候选编码。
    """
    return UnicodeDammit(data, ["utf-8", "gbk", "gb2312"]).unicode_markup


def fetch_html(session, url: str, timeout: float = 8, retries: int = 1, retry_delay: float = 0.5) -> str:
    """GET 并返回解码后的 HTML；失败重试 retries 次后抛 FetchError。"""
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, timeout=timeout, headers={"User-Agent": UA})
            resp.raise_for_status()
            return decode_html(resp.content)
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_delay)
    raise FetchError(f"GET {url} 失败（尝试 {retries + 1} 次）：{last_error}")
