"""模块2 规则引擎测试：适用性判断（FR-06）、地块校验（FR-08）、
总量校验（FR-09）、冲突检测（FR-10）。

所有 fixture 规则均为测试样例（clause_text 已标注"测试样例，非真实条款"），
数值不构成任何真实政策依据。
"""
import pytest

from compliance.engine import (
    applicable_rules,
    check_plot,
    check_total_area,
    find_conflicts,
)
from compliance.models import District, Plot, Rule

DISTRICT_ATTRS = {"更新类型": "老旧小区改造", "实施方式": "政府主导", "区位": "一般地区"}


def _rule(rule_id, indicator="容积率", comparison="le", value=3.5, level="city",
          applies_to=None, clause=None):
    return Rule(
        id=rule_id,
        indicator=indicator,
        level=level,
        source_doc_id="bj-jianzhu-guimo",
        clause=clause or f"测试样例条款-{rule_id}",
        clause_text=f"【测试样例，非真实条款】{indicator} {comparison} {value}",
        comparison=comparison,
        value=value,
        applies_to=dict(applies_to or {}),
    )


def _plot(plot_id="p-001", area=2.5, indicators=None):
    return Plot(id=plot_id, district_id="d-001", name=f"地块{plot_id}", area=area,
                indicators=dict(indicators) if indicators is not None else {"容积率": 3.5})


def _district(limit=100.0, attributes=None):
    return District(id="d-001", name="示范片区",
                    attributes=dict(attributes or DISTRICT_ATTRS),
                    total_area_limit=limit)


# ---------------------------------------------------------------- FR-06 适用性
def test_applicable_when_all_conditions_match():
    rule = _rule("r1", applies_to={"更新类型": "老旧小区改造", "区位": "一般地区"})
    assert applicable_rules([rule], DISTRICT_ATTRS) == [rule]


def test_applicable_when_conditions_are_subset():
    rule = _rule("r1", applies_to={"更新类型": "老旧小区改造"})
    assert applicable_rules([rule], DISTRICT_ATTRS) == [rule]


def test_not_applicable_when_condition_mismatch():
    rule = _rule("r1", applies_to={"更新类型": "城中村改造"})
    assert applicable_rules([rule], DISTRICT_ATTRS) == []


def test_empty_conditions_applies_everywhere():
    rule = _rule("r1", applies_to=None)
    assert applicable_rules([rule], {}) == [rule]


# ---------------------------------------------------------------- FR-08 地块校验
def test_plot_within_limit_is_allowed():
    rule = _rule("r1", comparison="le", value=4.0)
    result = check_plot(_plot(indicators={"容积率": 3.5}), [rule], DISTRICT_ATTRS)

    assert result.status == "allowed"
    assert result.checks[0].allowed is True
    assert result.checks[0].basis  # 依据条款可见


def test_plot_exceeding_limit_is_not_allowed():
    """PRD 11.1 FR-08 验收：录入超出限值的容积率 → Not Allowed。"""
    rule = _rule("r1", comparison="le", value=3.0)
    result = check_plot(_plot(indicators={"容积率": 3.5}), [rule], DISTRICT_ATTRS)

    assert result.status == "not_allowed"
    assert result.checks[0].allowed is False
    assert result.checks[0].plot_value == 3.5
    assert result.checks[0].rule_value == 3.0


def test_ge_rule_checks_minimum():
    rule = _rule("r1", indicator="绿地率", comparison="ge", value=0.3)
    assert check_plot(_plot(indicators={"绿地率": 0.35}), [rule], DISTRICT_ATTRS).status == "allowed"
    assert check_plot(_plot(indicators={"绿地率": 0.2}), [rule], DISTRICT_ATTRS).status == "not_allowed"


def test_eq_rule_with_tolerance():
    rule = _rule("r1", indicator="退线距离", comparison="eq", value=10.0)
    assert check_plot(_plot(indicators={"退线距离": 10.0 + 1e-12}), [rule], DISTRICT_ATTRS).status == "allowed"
    assert check_plot(_plot(indicators={"退线距离": 9.5}), [rule], DISTRICT_ATTRS).status == "not_allowed"


def test_missing_indicator_marks_unknown():
    """未录入的指标 → 无法判断（诚实拒答），不误判为合规。"""
    rule = _rule("r1", comparison="le", value=3.0)
    result = check_plot(_plot(indicators={}), [rule], DISTRICT_ATTRS)

    assert result.status == "unknown"
    assert result.missing == ("容积率",)


def test_unstipulated_value_rule_is_skipped():
    rule = _rule("r1", value=None, clause="测试样例条款-待标定")
    result = check_plot(_plot(), [rule], DISTRICT_ATTRS)
    assert result.status == "unknown"
    assert result.missing == ()


def test_any_violation_fails_plot():
    rules = [
        _rule("r1", comparison="le", value=4.0),
        _rule("r2", indicator="绿地率", comparison="ge", value=0.3),
    ]
    result = check_plot(_plot(indicators={"容积率": 3.5, "绿地率": 0.2}), rules, DISTRICT_ATTRS)
    assert result.status == "not_allowed"
    assert [c.indicator for c in result.checks if not c.allowed] == ["绿地率"]


def test_rule_outside_district_scope_is_ignored():
    rule = _rule("r1", applies_to={"更新类型": "城中村改造"})
    result = check_plot(_plot(indicators={"容积率": 9.9}), [rule], DISTRICT_ATTRS)
    assert result.status == "unknown"


# ---------------------------------------------------------------- FR-09 总量校验
def test_total_area_within_limit():
    plots = [_plot("p1", area=30.0), _plot("p2", area=40.0)]
    result = check_total_area(plots, _district(limit=100.0))
    assert result.exceeded is False
    assert result.total == 70.0


def test_total_area_at_limit_is_not_exceeded():
    plots = [_plot("p1", area=60.0), _plot("p2", area=40.0)]
    result = check_total_area(plots, _district(limit=100.0))
    assert result.exceeded is False


def test_total_area_exceeds_limit_with_excess():
    plots = [_plot("p1", area=60.0), _plot("p2", area=50.0)]
    result = check_total_area(plots, _district(limit=100.0))
    assert result.exceeded is True
    assert result.excess == 10.0


def test_empty_plots_never_exceed():
    result = check_total_area([], _district(limit=100.0))
    assert result.exceeded is False
    assert result.total == 0.0


# ---------------------------------------------------------------- FR-10 冲突检测
def test_conflict_detected_for_same_indicator_different_levels():
    rules = [
        _rule("national", level="national", value=4.0),
        _rule("city", level="city", value=3.0),
    ]
    conflicts = find_conflicts(rules, DISTRICT_ATTRS)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.indicator == "容积率"
    # ≤上限类从严取小值 → 市级 3.0
    assert conflict.stricter == 3.0


def test_ge_conflict_stricter_is_larger():
    rules = [
        _rule("r1", indicator="绿地率下限", comparison="ge", value=0.25, level="national"),
        _rule("r2", indicator="绿地率下限", comparison="ge", value=0.30, level="city"),
    ]
    conflict = find_conflicts(rules, DISTRICT_ATTRS)[0]
    assert conflict.stricter == 0.30


def test_no_conflict_when_values_agree():
    rules = [
        _rule("r1", level="national", value=3.0),
        _rule("r2", level="city", value=3.0),
    ]
    assert find_conflicts(rules, DISTRICT_ATTRS) == []


def test_conflict_only_among_applicable_rules():
    rules = [
        _rule("r1", value=3.0, applies_to={"更新类型": "城中村改造"}),
        _rule("r2", value=4.0),
    ]
    assert find_conflicts(rules, DISTRICT_ATTRS) == []


def test_mixed_comparison_conflict_flags_manual_review():
    rules = [
        _rule("r1", comparison="le", value=3.0),
        _rule("r2", comparison="ge", value=3.0),
    ]
    conflict = find_conflicts(rules, DISTRICT_ATTRS)[0]
    assert conflict.stricter is None
    assert "人工核对" in conflict.note
