"""信源库检索测试（FR-01：关键词检索返回原始记录，不允许生成记录）。"""
import pytest

from sourcelib.models import Channel, PolicyDocument
from sourcelib.search import search_documents


def _doc(doc_id, title, doc_number="", keywords=(), channel_id=""):
    return PolicyDocument(
        id=doc_id, title=title, doc_number=doc_number, effective_date="",
        status="待核验", official_url="", channel_id=channel_id, keywords=tuple(keywords), note="",
    )


@pytest.fixture
def docs():
    return [
        _doc("bj-gongjuxiang", "北京市城市更新政策激励工具箱（1.0版）",
             keywords=("工具箱", "激励", "容积率", "奖励", "北京")),
        _doc("n-155", "《城市更新“十五五”规划》", doc_number="国发〔2026〕12号",
             keywords=("城市更新", "十五五")),
        _doc("bj-tiaoli", "北京市城市更新条例", keywords=("条例", "北京")),
    ]


def test_empty_query_returns_empty(docs):
    assert search_documents(docs, "") == []
    assert search_documents(docs, "   ") == []


def test_single_token_matches_title(docs):
    assert [d.id for d in search_documents(docs, "工具箱")] == ["bj-gongjuxiang"]


def test_single_token_matches_keyword(docs):
    assert [d.id for d in search_documents(docs, "容积率")] == ["bj-gongjuxiang"]


def test_doc_number_search(docs):
    assert [d.id for d in search_documents(docs, "国发〔2026〕12号")] == ["n-155"]


def test_multi_token_requires_all_tokens(docs):
    # AND 语义：北京 + 容积率 → 工具箱
    assert [d.id for d in search_documents(docs, "北京 容积率")] == ["bj-gongjuxiang"]
    # 上限 无任何文档命中 → 空（FR-03 由界面层回"暂未收录"）
    assert search_documents(docs, "容积率 上限") == []


def test_prd_acceptance_query_without_spaces(docs):
    """PRD 11.1 FR-01 验收：输入"北京容积率上限"（无空格）应返回北京相关政策。"""
    hits = search_documents(docs, "北京容积率上限")
    assert [d.id for d in hits] == ["bj-gongjuxiang"]


def test_unknown_token_stays_required(docs):
    """切分后仍无关键词可匹配的词条保持 AND 语义：命中必须包含它。"""
    assert search_documents(docs, "工具箱 不存在的词") == []
    assert [d.id for d in search_documents(docs, "工具箱 容积率")] == ["bj-gongjuxiang"]


def test_no_match_returns_empty(docs):
    assert search_documents(docs, "土地出让金") == []


def test_case_insensitive_english_token(docs):
    hit = _doc("x-abc", "ABC 城市更新导则", keywords=("abc",))
    assert [d.id for d in search_documents([hit], "abc")] == ["x-abc"]


def test_channel_name_expands_match_scope():
    docs = [_doc("bj-portal-doc", "城市更新政策汇总", channel_id="bj-portal")]
    channels = [
        Channel(
            id="bj-portal", org="北京市人民政府", site_name="首都之窗·北京城市更新专栏",
            url="https://www.beijing.gov.cn/fuwu/lqfw/ztzl/bjchshgx/index.html",
            level="city", pilot=True, description="",
        )
    ]
    # 不传渠道：渠道名不参与匹配 → 空
    assert search_documents(docs, "首都之窗") == []
    # 传渠道：站点名/机构名参与匹配 → 命中
    assert [d.id for d in search_documents(docs, "首都之窗", channels=channels)] == ["bj-portal-doc"]
