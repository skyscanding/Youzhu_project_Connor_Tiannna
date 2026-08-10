"""信源配置测试：MD 全量网址覆盖 + 配置完整性 + 与独立测试脚本同步。

数据来源：《城市更新政策官方网址.md》（人工核验，共 85 条表格信源 + 正文内嵌网址）。
本文件是"信源路由表"的同步防线，防止三类 AI 常见回归：
1. MD 增删信源后 crawler/sources.py 未同步（漏部署爬虫）
2. 配置内部漂移（重复 id / 重复 URL / 非法层级 / 空关键词）
3. crawler/sources.py 与 Requesttest/crawler_standalone.py 两处配置不一致
"""
import importlib.util
import re
from pathlib import Path

import pytest

from crawler.sources import SOURCES

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "城市更新政策官方网址.md"
REQUESTTEST = ROOT.parent / "Requesttest" / "crawler_standalone.py"

# 与 sourcelib/models.py VALID_LEVELS 保持一致的合法层级
VALID_LEVELS = {"national", "provincial", "city", "district", "finance"}

# MD 中出现的全部 http(s) 网址：markdown 链接 [label](url) 或正文纯文本（如 "政策库 https://.../ ；"）
# 注意排除 ] 与 )（markdown 链接 [url](url) 的两个结束符）
_URL_RE = re.compile(r"https?://[^\s）；）\]\"'<>,。)]+")
# MD 正文中括号括起来的裸域名，如 "办公厅(bgt.mof.gov.cn)"
_BARE_DOMAIN_RE = re.compile(r"\(([a-z0-9-]+(?:\.[a-z0-9-]+)+\.(?:gov|com)\.cn)\)")

# 别名豁免：MD 中"中国政府网"主站根域由 govcn 信源（政策库子站 https://www.gov.cn/zhengce/zhengceku/）
# 覆盖，不单独部署爬虫（根域首页与政策库内容重复，直接抓政策库）
_ROOT_ALIASES = {"https://www.gov.cn": "https://www.gov.cn/zhengce/zhengceku"}


def _normalize(url: str) -> str:
    """URL 归一化：去尾部斜杠、scheme 与 host 小写（路径大小写保留）。"""
    url = url.strip().rstrip("/")
    scheme, rest = url.split("://", 1)
    host, _, path = rest.partition("/")
    return f"{scheme.lower()}://{host.lower()}" + (f"/{path}" if path else "")


def _md_urls() -> set[str]:
    """解析 MD 中全部网址（链接 + 裸域名），归一化后返回。"""
    text = MD_PATH.read_text(encoding="utf-8")
    urls = set(_URL_RE.findall(text))
    for domain in _BARE_DOMAIN_RE.findall(text):
        urls.add("https://" + domain.lower())
    return {_normalize(u) for u in urls}


def _config_urls() -> set[str]:
    return {_normalize(s.url) for s in SOURCES}


# ---------------------------------------------------------------- MD 全覆盖


def test_md_every_url_has_crawler_source():
    """MD 中的每个网址都必须有爬虫信源（所有网址都要部署爬虫）。"""
    covered = _config_urls() | {_normalize(v) for v in _ROOT_ALIASES.values()} | {
        _normalize(k) for k in _ROOT_ALIASES
    }
    missing = _md_urls() - covered
    assert not missing, f"以下 MD 网址未部署爬虫：{sorted(missing)}"


def test_every_source_url_appears_in_md():
    """反向防线：配置中的网址都必须能追溯到 MD（防止凭空添加信源）。"""
    orphan = _config_urls() - _md_urls()
    assert not orphan, f"以下配置网址在 MD 中找不到出处：{sorted(orphan)}"


def test_md_source_count_is_as_declared():
    """MD 声明 85 条表格信源；配置应为 85 + 正文内嵌网址。"""
    md_count = len(_md_urls())
    assert md_count >= 85, f"MD 网址解析异常：只解析到 {md_count} 个"
    # MD 比配置多出的只能是 _ROOT_ALIASES 中声明过的主站根域
    assert len(SOURCES) + len(_ROOT_ALIASES) == md_count, (
        f"信源数不一致：MD 含 {md_count} 个网址，配置 {len(SOURCES)} 个信源"
        f"（别名豁免 {len(_ROOT_ALIASES)} 个）"
    )


# ---------------------------------------------------------------- 配置完整性


def test_source_ids_unique():
    ids = [s.id for s in SOURCES]
    assert len(ids) == len(set(ids)), f"信源 id 重复：{[i for i in ids if ids.count(i) > 1]}"


def test_source_urls_unique():
    urls = [_normalize(s.url) for s in SOURCES]
    assert len(urls) == len(set(urls)), "存在重复信源 URL"


def test_source_levels_valid():
    bad = [s.id for s in SOURCES if s.level not in VALID_LEVELS]
    assert not bad, f"非法层级：{bad}（合法：{sorted(VALID_LEVELS)}）"


def test_source_keywords_nonempty():
    empty = [s.id for s in SOURCES if not s.keywords]
    assert not empty, f"关键词为空：{empty}"


def test_source_url_schemes_valid():
    bad = [s.id for s in SOURCES if not s.url.startswith(("http://", "https://"))]
    assert not bad, f"URL scheme 非法：{bad}"


def test_levels_present_for_each_category():
    """四类层级齐全：省级、市级、区级、融资平台都要有信源。"""
    by_level = {s.level for s in SOURCES}
    assert by_level == VALID_LEVELS, f"层级覆盖不全：{sorted(by_level)}"


# ---------------------------------------------------------------- 独立脚本同步


def _load_standalone_sources():
    if not REQUESTTEST.exists():
        pytest.skip("Requesttest/crawler_standalone.py 不存在，跳过同步检查")
    spec = importlib.util.spec_from_file_location("standalone_crawler_sources", REQUESTTEST)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SOURCES


def test_standalone_config_synced_with_crawler():
    """独立测试脚本（Requesttest）与 pipeline 爬虫的配置必须完全一致。"""
    standalone = {s.id: (s.name, s.level, _normalize(s.url), tuple(s.keywords)) for s in _load_standalone_sources()}
    crawler = {s.id: (s.name, s.level, _normalize(s.url), tuple(s.keywords)) for s in SOURCES}
    assert set(standalone) == set(crawler), (
        f"id 不一致：仅 standalone 有 {set(standalone) - set(crawler)}，"
        f"仅 crawler 有 {set(crawler) - set(standalone)}"
    )
    for source_id in crawler:
        assert standalone[source_id] == crawler[source_id], (
            f"信源 {source_id} 配置不一致：standalone={standalone[source_id]} crawler={crawler[source_id]}"
        )
