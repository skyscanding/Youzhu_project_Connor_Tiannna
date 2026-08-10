"""信源库模型校验测试：渠道与政策文档记录的数据完整性规则。"""
import pytest

from sourcelib.models import (
    VALID_STATUSES,
    Channel,
    PolicyDocument,
    ValidationError,
    validate_channel,
    validate_document,
)


def _good_channel(**overrides):
    data = dict(
        id="govcn",
        org="国务院",
        site_name="中国政府网",
        url="https://www.gov.cn/zhengce/zhengceku/",
        level="national",
        pilot=False,
        description="政策库",
    )
    data.update(overrides)
    return Channel(**data)


def test_valid_channel_passes():
    assert validate_channel(_good_channel()) == []


@pytest.mark.parametrize("field,value", [
    ("id", ""),
    ("org", ""),
    ("site_name", ""),
    ("level", "municipal"),  # 非法层级
])
def test_channel_required_fields(field, value):
    errors = validate_channel(_good_channel(**{field: value}))
    assert errors, f"字段 {field}={value!r} 应校验失败"


@pytest.mark.parametrize("url", ["ftp://x.gov.cn", "www.gov.cn", "not a url"])
def test_channel_invalid_url(url):
    assert validate_channel(_good_channel(url=url))


def test_channel_valid_http_urls():
    assert validate_channel(_good_channel(url="http://www.bjdch.gov.cn")) == []
    assert validate_channel(_good_channel(url="https://www.gov.cn/")) == []


def _good_doc(**overrides):
    data = dict(
        id="n-155-guihua",
        title="《城市更新“十五五”规划》",
        doc_number="国发〔2026〕12号",
        effective_date="",
        status="待核验",
        official_url="",
        channel_id="govcn",
        keywords=("城市更新", "十五五"),
        note="",
    )
    data.update(overrides)
    return PolicyDocument(**data)


def test_valid_document_passes():
    assert validate_document(_good_doc()) == []


@pytest.mark.parametrize("field,value", [
    ("id", ""),
    ("title", ""),
    ("status", "现行"),          # 非法状态值
    ("status", ""),
])
def test_document_required_fields(field, value):
    errors = validate_document(_good_doc(**{field: value}))
    assert errors, f"字段 {field}={value!r} 应校验失败"


def test_all_status_values_are_explicit():
    # FR-04：效力状态标签集合必须包含 现行有效/已修改/已废止，且均为人工可核验的取值
    assert {"现行有效", "已修改", "已废止", "待核验"} == set(VALID_STATUSES)


@pytest.mark.parametrize("date", ["2026-1-1", "26-01-01", "2026/01/01", "20260101"])
def test_document_invalid_date_format(date):
    assert validate_document(_good_doc(effective_date=date))


def test_document_empty_date_is_allowed():
    # 未知日期留空，不允许虚构
    assert validate_document(_good_doc(effective_date="")) == []


@pytest.mark.parametrize("url", ["ftp://x.gov.cn", "javascript:void(0)"])
def test_document_invalid_official_url(url):
    assert validate_document(_good_doc(official_url=url))


def test_document_empty_official_url_is_allowed():
    assert validate_document(_good_doc(official_url="")) == []


def test_validation_error_aggregates_all_problems():
    bad = _good_doc(id="", title="", status="X", effective_date="2026-1-1")
    with pytest.raises(ValidationError) as exc:
        validate_document(bad, strict=True)
    message = str(exc.value)
    assert "标题" in message or "id" in message
    assert "状态" in message
