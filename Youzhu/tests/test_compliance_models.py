"""模块2 数据模型测试：规则、片区、地块的校验规则（契约的机器可检查部分）。"""
import pytest

from compliance.models import (
    District,
    Plot,
    Rule,
    ValidationError,
    validate_district,
    validate_plot,
    validate_rule,
)


def _good_rule(**overrides):
    data = dict(
        id="r-001",
        indicator="容积率上限",
        level="city",
        source_doc_id="bj-jianzhu-guimo",
        clause="测试样例条款-001",
        clause_text="【测试样例，非真实条款】容积率不得超过 3.5",
        comparison="le",
        value=3.5,
        applies_to={"更新类型": "老旧小区改造"},
        mandatory=True,
        note="",
    )
    data.update(overrides)
    return Rule(**data)


def test_valid_rule_passes():
    assert validate_rule(_good_rule()) == []


@pytest.mark.parametrize("field,value", [
    ("id", ""),
    ("indicator", ""),
    ("level", "municipal"),
    ("source_doc_id", ""),
    ("clause", ""),
    ("clause_text", ""),
    ("comparison", "lt"),
])
def test_rule_required_fields(field, value):
    errors = validate_rule(_good_rule(**{field: value}))
    assert errors, f"字段 {field}={value!r} 应校验失败"


def test_rule_negative_value_rejected():
    assert validate_rule(_good_rule(value=-1.0))


def test_rule_unstipulated_value_requires_note():
    """数值未标定（None）必须注明原因——不允许静默缺失。"""
    assert validate_rule(_good_rule(value=None, note="待规划部门标定")) == []
    assert validate_rule(_good_rule(value=None, note=""))


def test_rule_bad_applies_to_rejected():
    assert validate_rule(_good_rule(applies_to={"": "值"}))
    assert validate_rule(_good_rule(applies_to={"键": ""}))


def _good_district(**overrides):
    data = dict(
        id="d-001",
        name="示范片区",
        attributes={"更新类型": "老旧小区改造", "实施方式": "政府主导"},
        total_area_limit=100.0,
    )
    data.update(overrides)
    return District(**data)


def test_valid_district_passes():
    assert validate_district(_good_district()) == []


@pytest.mark.parametrize("field,value", [
    ("id", ""),
    ("name", ""),
    ("total_area_limit", -1.0),
])
def test_district_required_fields(field, value):
    assert validate_district(_good_district(**{field: value}))


def _good_plot(**overrides):
    data = dict(
        id="p-001",
        district_id="d-001",
        name="地块A",
        area=2.5,
        indicators={"容积率": 3.5},
    )
    data.update(overrides)
    return Plot(**data)


def test_valid_plot_passes():
    assert validate_plot(_good_plot()) == []


@pytest.mark.parametrize("field,value", [
    ("id", ""),
    ("district_id", ""),
    ("name", ""),
    ("area", -0.1),
])
def test_plot_required_fields(field, value):
    assert validate_plot(_good_plot(**{field: value}))


def test_plot_negative_indicator_rejected():
    assert validate_plot(_good_plot(indicators={"容积率": -1.0}))


def test_validation_error_aggregates():
    bad = _good_rule(id="", indicator="", comparison="lt")
    with pytest.raises(ValidationError) as exc:
        validate_rule(bad, strict=True)
    assert "指标" in str(exc.value)
    assert "比较方向" in str(exc.value)


def test_district_and_plot_serialization_roundtrip():
    """District/Plot 序列化往返（表单/录入层的数据契约）。"""
    district = _good_district()
    assert District.from_dict(district.to_dict()) == district

    plot = _good_plot(indicators={"容积率": 3.5, "绿地率": 0.3})
    restored = Plot.from_dict(plot.to_dict())
    assert restored == plot
    assert restored.indicators == {"容积率": 3.5, "绿地率": 0.3}
