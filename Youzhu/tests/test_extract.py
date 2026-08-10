"""解析层测试：政策列表页 HTML → 政策记录（标题/URL/日期/发文号）。"""
from pathlib import Path

from crawler.extract import extract_records, find_date, find_date_from_url, find_doc_number
from crawler.fetch import decode_html

FIXTURES = Path(__file__).parent / "fixtures"

# 与 sources.py 中专栏信源的默认关键词一致
DEFAULT_KEYWORDS = ("城市更新", "老旧小区", "城中村")


def test_find_doc_number_from_title():
    assert find_doc_number("国务院关于印发《城市更新“十五五”规划》的通知（国发〔2026〕12号）") == "国发〔2026〕12号"
    assert find_doc_number("关于印发《北京市城市更新政策激励工具箱（1.0版）》的通知") is None


def test_find_date_variants():
    assert find_date("2026-07-01") == "2026-07-01"
    assert find_date("2026年7月1日") == "2026-07-01"
    assert find_date("2026/07/01") == "2026-07-01"
    assert find_date("没有日期") is None


def test_find_date_from_url_variants():
    """URL 日期兜底：政府站四种 URL 模式。"""
    assert find_date_from_url("http://x.gov.cn/a/2026/7/29/9de975b.shtml") == "2026-07-29"
    assert find_date_from_url("http://x.gov.cn/content/20260729/xxx.htm") == "2026-07-29"
    assert find_date_from_url("http://x.gov.cn/jsdt/202406/t20240614_3205251.html") == "2024-06-14"
    assert find_date_from_url("http://x.gov.cn/jsdt/202607/t20260722_5295194.html") == "2026-07-22"
    assert find_date_from_url("http://x.gov.cn/xxgk/202607/content.shtml") == "2026-07"
    assert find_date_from_url("http://x.gov.cn/no-date-here") == ""


def test_extract_date_falls_back_to_url():
    """首都之窗专栏类页面：链接不在 <li> 内，日期从 URL 兜底提取。"""
    html = (
        '<ul class="list">'
        '<li><a href="/fuwu/lqfw/ztzl/bjchshgx/202605/t20260510_1000001.html">城市更新政策测试通知</a></li>'
        "</ul>"
    )
    records = extract_records(html, "https://www.beijing.gov.cn", DEFAULT_KEYWORDS)
    assert len(records) == 1
    assert records[0].date == "2026-05-10"


def test_extract_gov_list_page():
    html = (FIXTURES / "gov_list_utf8.html").read_text(encoding="utf-8")
    records = extract_records(html, "https://www.gov.cn/zhengce/zhengceku/", DEFAULT_KEYWORDS)

    assert len(records) == 3
    # 无关链接（不含关键词）被过滤
    assert not any("答记者问" in r.title for r in records)
    # 相对链接解析为绝对链接
    assert all(r.url.startswith("https://www.gov.cn/") for r in records)
    # 标题与日期被提取
    assert all(r.title and r.date for r in records)
    # 发文号提取
    assert any(r.doc_number for r in records)
    assert any("国发〔2026〕12号" == r.doc_number for r in records)


def test_extract_beijing_gbk_page():
    """GBK 编码页面：解码后仍能正确提取记录。"""
    html = decode_html((FIXTURES / "beijing_list_gbk.html").read_bytes())
    records = extract_records(
        html,
        "https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/aztfl64/csgx/index.shtml",
        DEFAULT_KEYWORDS,
    )

    assert len(records) == 3
    assert any("政策激励工具箱" in r.title for r in records)
    assert all(r.date for r in records)


def test_extract_empty_page():
    assert extract_records(
        "<html><body><p>暂无内容</p></body></html>", "https://example.gov.cn/", DEFAULT_KEYWORDS
    ) == []


def test_extract_deduplicates_same_url():
    html = """
    <ul>
      <li><a href="/a/1.htm">城市更新测试通知</a><span>2026-07-01</span></li>
      <li><a href="/a/1.htm">城市更新测试通知（重复链接）</a><span>2026-07-01</span></li>
    </ul>
    """
    records = extract_records(html, "https://example.gov.cn/", DEFAULT_KEYWORDS)
    assert len(records) == 1


def test_extract_skips_non_content_links():
    html = """
    <a href="#">城市更新</a>
    <a href="javascript:void(0)">城市更新政策</a>
    <a href="mailto:webmaster@example.gov.cn">联系我们</a>
    <a href="/content/1.htm">城市更新示范项目公示</a>
    """
    records = extract_records(html, "https://example.gov.cn/", DEFAULT_KEYWORDS)
    assert len(records) == 1
    assert records[0].url == "https://example.gov.cn/content/1.htm"


def test_extract_skips_link_back_to_list_page():
    """指向列表页自身的链接（如"更多"）不应作为记录收录。"""
    html = """
    <ul>
      <li><a href="/zhengce/zhengceku/">城市更新政策库首页</a><span>2026-01-01</span></li>
      <li><a href="/zhengce/content/1.htm">城市更新试点政策</a><span>2026-01-02</span></li>
    </ul>
    """
    records = extract_records(html, "https://www.gov.cn/zhengce/zhengceku/", DEFAULT_KEYWORDS)
    assert len(records) == 1
    assert records[0].url == "https://www.gov.cn/zhengce/content/1.htm"
