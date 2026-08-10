"""解析层：列表页 HTML → 政策记录（标题/URL/日期/发文号）。

通用解析为 best-effort：遍历页面所有 <a>，按信源关键词过滤，
日期取自所在 <li> 文本，发文号从标题正则提取（无则不填）。
"""
import re
from dataclasses import asdict, dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# 发文号：如 国发〔2026〕12号 / 自然资发〔2025〕226号 / (2026)12号
_DOC_RE = re.compile(r"([\u4e00-\u9fff]{0,8}[〔\[(（]?\d{4}[〕\])）]?\s*\d+号)")
# 日期：2026-07-01 / 2026年7月1日 / 2026/07/01
_DATE_RE = re.compile(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})日?")
# URL 日期兜底（政府站 URL 常见模式，列表页无日期时启用）：
#   /2026/7/29/          → 2026-07-29
#   /20260729/           → 2026-07-29
#   t20240614_xxx.shtml  → 2024-06-14
#   /202607/             → 2026-07（仅年月，未知日）
_URL_DATE_FULL = re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})/")
_URL_DATE_COMPACT = re.compile(r"/(\d{4})(\d{2})(\d{2})/")
_URL_DATE_STAMP = re.compile(r"t(\d{4})(\d{2})(\d{2})_")
_URL_DATE_YM = re.compile(r"/(\d{4})(\d{2})/")
_SKIP_HREF = re.compile(r"^(javascript|mailto|tel|#|$)", re.IGNORECASE)


@dataclass
class Record:
    """一条政策文件元信息记录（不含正文）。"""

    title: str
    url: str
    date: str = ""
    doc_number: str = ""
    first_seen: str = ""
    last_seen: str = ""

    @property
    def identity(self) -> str:
        """记录唯一标识：URL 优先，无 URL 时用 标题+日期。"""
        return self.url if self.url else f"{self.title}|{self.date}"

    def signature(self) -> tuple:
        """内容指纹：任一字段变化视为「更新」。"""
        return (self.title, self.date, self.doc_number)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Record":
        fields = ("title", "url", "date", "doc_number", "first_seen", "last_seen")
        return cls(**{f: data.get(f, "") for f in fields})


def find_doc_number(text: str) -> str | None:
    match = _DOC_RE.search(text)
    return match.group(1).strip() if match else None


def find_date(text: str) -> str | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def find_date_from_url(url: str) -> str:
    """从 URL 提取日期兜底：完整日期优先，其次年月（未知日）。"""
    match = _URL_DATE_FULL.search(url) or _URL_DATE_COMPACT.search(url) or _URL_DATE_STAMP.search(url)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    match = _URL_DATE_YM.search(url)
    if match:
        year, month = match.groups()
        return f"{year}-{month}"
    return ""


def extract_records(html: str, base_url: str, keywords=()) -> list[Record]:
    """从列表页提取政策记录，按 URL 去重。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[Record] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if _SKIP_HREF.match(href):
            continue
        title = anchor.get_text(" ", strip=True)
        if not title or len(title) < 4:
            continue
        if keywords and not any(k in title for k in keywords):
            continue
        url = urljoin(base_url, href)
        if url in seen or url.rstrip("#") == base_url.rstrip("#"):
            continue
        seen.add(url)
        parent = anchor.find_parent("li")
        context = parent.get_text(" ", strip=True) if parent else title
        records.append(
            Record(
                title=title,
                url=url,
                date=find_date(context) or find_date_from_url(url) or "",
                doc_number=find_doc_number(title) or "",
            )
        )
    return records
