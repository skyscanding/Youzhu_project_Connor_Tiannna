"""种子数据测试：数据完整性、交付物数量要求、与爬虫信源配置的一致性。

数据来源于《城市更新政策官方网址.md》（人工核验），测试防止三类回归：
1. 结构化数据字段缺失/非法（人工录入错误）
2. 与 crawler/sources.py 信源配置漂移（同一渠道两处定义不一致）
3. 虚构发文号/日期（PRD 核心红线：不允许编造记录）
"""
import re

from crawler.sources import SOURCES
from sourcelib.models import validate_channel, validate_document
from sourcelib.seed import CHANNELS, DOCUMENTS

# 交付物要求（PRD 11.3）：政策信源清单不少于 20 份
MIN_CHANNELS = 20
MIN_DOCUMENTS = 15

_DOC_NUMBER_RE = re.compile(r"[〔\[(（]?\d{4}[〕\])）]?\s*\d+号")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def test_channel_count_meets_deliverable():
    assert len(CHANNELS) >= MIN_CHANNELS


def test_document_count_meets_deliverable():
    assert len(DOCUMENTS) >= MIN_DOCUMENTS


def test_all_channels_valid_and_unique():
    ids = [c.id for c in CHANNELS]
    assert len(ids) == len(set(ids)), "渠道 id 重复"
    for channel in CHANNELS:
        assert validate_channel(channel) == [], f"渠道 {channel.id} 校验失败"


def test_all_documents_valid_and_unique():
    ids = [d.id for d in DOCUMENTS]
    assert len(ids) == len(set(ids)), "文档 id 重复"
    for doc in DOCUMENTS:
        assert validate_document(doc) == [], f"文档 {doc.id} 校验失败"


def test_document_channel_references_exist():
    channel_ids = {c.id for c in CHANNELS}
    for doc in DOCUMENTS:
        if doc.channel_id:
            assert doc.channel_id in channel_ids, (
                f"文档 {doc.id} 引用了不存在的渠道 {doc.channel_id}"
            )


def test_documents_have_searchable_keywords():
    """FR-01 检索依赖关键词：每条记录至少一个检索关键词。"""
    for doc in DOCUMENTS:
        assert doc.keywords, f"文档 {doc.id} 缺少检索关键词"


def test_no_invented_doc_numbers():
    """发文号只允许两种：符合〔〕号格式（来自 MD），或留空（待核验）。"""
    for doc in DOCUMENTS:
        if doc.doc_number:
            assert _DOC_NUMBER_RE.search(doc.doc_number), (
                f"文档 {doc.id} 的发文号 {doc.doc_number!r} 格式异常，疑似虚构"
            )


def test_dates_are_iso_or_empty():
    for doc in DOCUMENTS:
        if doc.effective_date:
            assert _DATE_RE.match(doc.effective_date), (
                f"文档 {doc.id} 日期 {doc.effective_date!r} 非 ISO 格式"
            )


def test_status_is_explicit_or_pending():
    for doc in DOCUMENTS:
        assert doc.status in ("现行有效", "已修改", "已废止", "待核验"), (
            f"文档 {doc.id} 状态 {doc.status!r} 非法"
        )


def test_channels_align_with_crawler_sources():
    """信源库渠道表与爬虫信源配置必须一致（同一份信源路由表的两个消费方）。"""
    crawler = {s.id: s for s in SOURCES}
    library = {c.id: c for c in CHANNELS}

    assert set(crawler) == set(library), (
        f"id 不一致：仅爬虫有 {set(crawler) - set(library)}，仅信源库有 {set(library) - set(crawler)}"
    )
    for source_id, source in crawler.items():
        assert library[source_id].url == source.url, (
            f"信源 {source_id} URL 不一致：爬虫={source.url} 信源库={library[source_id].url}"
        )
        assert library[source_id].level == source.level


def test_district_channels_marked_correctly():
    """第一批试点城市/区按 MD 标注：北京市级为试点，区级条目标注为否。"""
    pilot = {c.id for c in CHANNELS if c.pilot}
    assert {"bj-portal", "bj-zjw", "bj-zjw-csgx", "bj-ghzrzyw"} <= pilot
    assert not {"bj-dc", "bj-cy"} & pilot, "区级站点不应标记为第一批试点"


def test_beijing_documents_are_beijing_specific():
    """北京文档的关键词应包含'北京'，避免检索时与全国政策混淆。"""
    for doc in DOCUMENTS:
        if doc.id.startswith("bj-"):
            assert "北京" in doc.keywords, f"北京文档 {doc.id} 关键词缺少'北京'"
