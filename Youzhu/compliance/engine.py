"""模块2 规则引擎：全部数值判定由程序完成（PRD 人机协作边界）。

- FR-06 适用性判断：规则适用条件 ⊆ 片区属性
- FR-08 地块校验：逐指标比对 → Allowed / Not Allowed / 无法判断
- FR-09 片区总量校验：各地块规模求和，超上限预警
- FR-10 冲突检测：同指标多层级不同值 → 差异提示 + 从严建议
- FR-11 依据条款：每条结论携带 条款号 + 原文片段（可溯源）
"""
from dataclasses import dataclass

from compliance.models import Plot, Rule

_EQ_TOLERANCE = 1e-9


@dataclass(frozen=True)
class IndicatorCheck:
    indicator: str
    rule: Rule
    plot_value: float
    allowed: bool
    basis: str  # FR-11：依据条款（文件+条款号+原文片段）

    @property
    def rule_value(self) -> float | None:
        """限值便利属性（报告层使用）。"""
        return self.rule.value


@dataclass(frozen=True)
class PlotResult:
    plot_id: str
    checks: tuple
    status: str  # allowed / not_allowed / unknown
    missing: tuple  # 有适用规则但地块未录入的指标


@dataclass(frozen=True)
class TotalAreaResult:
    total: float
    limit: float
    exceeded: bool
    excess: float


@dataclass(frozen=True)
class Conflict:
    indicator: str
    values: tuple
    comparisons: tuple
    stricter: float | None  # 从严取值；方向不一致时为 None
    note: str
    rules: tuple


def rule_applies(rule: Rule, attributes: dict) -> bool:
    """规则适用条件（键值对子集）全部命中片区属性时适用。"""
    return all(attributes.get(key) == value for key, value in rule.applies_to.items())


def applicable_rules(rules: list[Rule], attributes: dict) -> list[Rule]:
    """FR-06：按片区属性判定适用的规则。"""
    return [r for r in rules if rule_applies(r, attributes)]


def _compare_allowed(plot_value: float, comparison: str, rule_value: float) -> bool:
    if comparison == "le":
        return plot_value <= rule_value
    if comparison == "ge":
        return plot_value >= rule_value
    return abs(plot_value - rule_value) <= _EQ_TOLERANCE


def _basis(rule: Rule) -> str:
    return f"[{rule.source_doc_id}] {rule.clause}：{rule.clause_text}"


def check_plot(plot: Plot, rules: list[Rule], attributes: dict) -> PlotResult:
    """FR-08：逐指标判定是否踩线。未录入的指标 → unknown（不误判合规）。"""
    checks = []
    missing = []
    for rule in applicable_rules(rules, attributes):
        if rule.value is None:
            continue  # 未标定：引擎不判定，由上层提示人工标定
        if rule.indicator not in plot.indicators:
            missing.append(rule.indicator)
            continue
        plot_value = plot.indicators[rule.indicator]
        checks.append(IndicatorCheck(
            indicator=rule.indicator,
            rule=rule,
            plot_value=plot_value,
            allowed=_compare_allowed(plot_value, rule.comparison, rule.value),
            basis=_basis(rule),
        ))
    if any(not c.allowed for c in checks):
        status = "not_allowed"
    elif checks:
        status = "allowed"
    else:
        status = "unknown"
    return PlotResult(
        plot_id=plot.id,
        checks=tuple(checks),
        status=status,
        missing=tuple(sorted(set(missing))),
    )


def check_total_area(plots: list[Plot], district) -> TotalAreaResult:
    """FR-09：各地块规模求和，超出片区总规模上限则预警。"""
    total = sum(p.area for p in plots)
    exceeded = total > district.total_area_limit
    excess = round(total - district.total_area_limit, 6) if exceeded else 0.0
    return TotalAreaResult(
        total=total,
        limit=district.total_area_limit,
        exceeded=exceeded,
        excess=excess,
    )


def find_conflicts(rules: list[Rule], attributes: dict) -> list[Conflict]:
    """FR-10：同指标在适用规则中出现多个不同取值 → 显式提示差异与从严建议。

    从严原则：≤上限类取小值，≥下限类取大值；
    比较方向不一致时无法计算从严值，提示人工核对。
    """
    by_indicator: dict[str, list[Rule]] = {}
    for rule in applicable_rules(rules, attributes):
        if rule.value is not None:
            by_indicator.setdefault(rule.indicator, []).append(rule)

    conflicts = []
    for indicator, group in by_indicator.items():
        values = {r.value for r in group}
        comparisons = {r.comparison for r in group}
        if len(values) <= 1 and len(comparisons) <= 1:
            continue
        if comparisons == {"le"}:
            stricter = min(values)
            note = f"从严建议：按上限取小值 {stricter}"
        elif comparisons == {"ge"}:
            stricter = max(values)
            note = f"从严建议：按下限取大值 {stricter}"
        else:
            stricter = None
            note = "比较方向不一致，请人工核对"
        conflicts.append(Conflict(
            indicator=indicator,
            values=tuple(sorted(values)),
            comparisons=tuple(sorted(comparisons)),
            stricter=stricter,
            note=note,
            rules=tuple(group),
        ))
    return conflicts
