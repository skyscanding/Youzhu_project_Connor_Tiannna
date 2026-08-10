"""规模预警核心计算：地块级强度预警 + 片区级总量预警。

输入：
- 地块：用地面积、容积率、建筑密度、绿地率等
- 片区：总规模上限、内地块列表

输出：
- RiskLevel: safe / warn / danger
- ScaleWarning: 带原因与归一化值的预警记录
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"
    WARN = "warn"
    DANGER = "danger"

    @property
    def severity(self) -> int:
        return {"safe": 0, "warn": 1, "danger": 2}[self.value]


@dataclass(frozen=True)
class WarningThreshold:
    """可配置的预警阈值。"""

    # 片区总量：占上限比例
    district_total_area_ratio_warn: float = 0.80
    district_total_area_ratio_danger: float = 1.00

    # 地块强度指标
    plot_far_warn: float = 2.5
    plot_far_danger: float = 3.0
    plot_density_warn: float = 0.25
    plot_density_danger: float = 0.35
    plot_green_rate_min: float = 0.30  # 绿地率不得低于该值
    plot_green_rate_danger: float = 0.20

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WarningThreshold":
        return cls(**{k: float(data[k]) for k in asdict(cls()) if k in data})


@dataclass(frozen=True)
class ScaleWarning:
    """一次规模预警结果。"""

    level: RiskLevel
    reason: str
    plot_id: str | None = None
    district_id: str | None = None
    district_name: str | None = None
    total_area: float | None = None
    ratio: float | None = None
    far: float | None = None
    density: float | None = None
    green_rate: float | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["level"] = self.level.value
        return data


def _level_for_value(value: float, warn: float, danger: float, higher_is_worse: bool = True) -> RiskLevel:
    """根据数值判断风险等级。"""
    if value < 0:
        return RiskLevel.DANGER
    if higher_is_worse:
        # 上限型（容积率/密度/总量占比）：达到阈值即触发（从严）
        if value >= danger:
            return RiskLevel.DANGER
        if value >= warn:
            return RiskLevel.WARN
    else:
        # 下限型（绿地率等“不得低于”）：达到阈值即合规，仅严格低于才告警
        if value < danger:
            return RiskLevel.DANGER
        if value < warn:
            return RiskLevel.WARN
    return RiskLevel.SAFE


def _update_level(current: RiskLevel, candidate: RiskLevel) -> RiskLevel:
    return candidate if candidate.severity > current.severity else current


def assess_plot_intensity(
    plot_id: str,
    far: float | None = None,
    density: float | None = None,
    green_rate: float | None = None,
    thresholds: WarningThreshold | None = None,
) -> ScaleWarning:
    """对单个地块做强度预警。"""
    thresholds = thresholds or WarningThreshold()
    reasons: list[str] = []
    level = RiskLevel.SAFE

    if far is not None and far < 0:
        return ScaleWarning(
            plot_id=plot_id,
            level=RiskLevel.DANGER,
            reason=f"容积率非法负值：{far}",
            far=far,
        )

    if far is not None:
        far_level = _level_for_value(far, thresholds.plot_far_warn, thresholds.plot_far_danger)
        level = _update_level(level, far_level)
        if far_level != RiskLevel.SAFE:
            reasons.append(f"容积率 {far} 超过阈值 {thresholds.plot_far_warn}/{thresholds.plot_far_danger}")

    if density is not None:
        density_level = _level_for_value(
            density, thresholds.plot_density_warn, thresholds.plot_density_danger
        )
        level = _update_level(level, density_level)
        if density_level != RiskLevel.SAFE:
            reasons.append(f"建筑密度 {density} 超过阈值 {thresholds.plot_density_warn}/{thresholds.plot_density_danger}")

    if green_rate is not None:
        green_level = _level_for_value(
            green_rate,
            thresholds.plot_green_rate_min,
            thresholds.plot_green_rate_danger,
            higher_is_worse=False,
        )
        level = _update_level(level, green_level)
        if green_level != RiskLevel.SAFE:
            reasons.append(f"绿地率 {green_rate} 低于阈值 {thresholds.plot_green_rate_min}")

    reason = "；".join(reasons) if reasons else "地块强度指标符合要求"
    return ScaleWarning(
        plot_id=plot_id,
        level=level,
        reason=reason,
        far=far,
        density=density,
        green_rate=green_rate,
    )


def assess_district_total(
    district_id: str,
    district_name: str,
    total_area_limit: float,
    plot_areas: list[float],
    thresholds: WarningThreshold | None = None,
) -> ScaleWarning:
    """对片区做总量预警：汇总地块面积与片区上限比较。"""
    thresholds = thresholds or WarningThreshold()
    total_area = sum(plot_areas)

    if total_area_limit <= 0:
        return ScaleWarning(
            district_id=district_id,
            district_name=district_name,
            level=RiskLevel.DANGER,
            reason=f"片区 {district_name} 总规模上限非法：{total_area_limit}",
            total_area=total_area,
            ratio=None,
        )

    ratio = total_area / total_area_limit
    level = _level_for_value(
        ratio,
        thresholds.district_total_area_ratio_warn,
        thresholds.district_total_area_ratio_danger,
    )

    if level == RiskLevel.SAFE:
        reason = f"片区 {district_name} 总用地 {total_area} 公顷，占上限 {ratio:.1%}"
    else:
        reason = (
            f"片区 {district_name} 总用地 {total_area} 公顷，占上限 {ratio:.1%}，"
            f"超过阈值 {thresholds.district_total_area_ratio_warn:.0%}/"
            f"{thresholds.district_total_area_ratio_danger:.0%}"
        )

    return ScaleWarning(
        district_id=district_id,
        district_name=district_name,
        level=level,
        reason=reason,
        total_area=total_area,
        ratio=ratio,
    )


def summarize_warnings(warnings: list[ScaleWarning]) -> dict:
    """汇总预警列表，给出统计与最高风险等级。"""
    counts = {RiskLevel.SAFE: 0, RiskLevel.WARN: 0, RiskLevel.DANGER: 0}
    for w in warnings:
        counts[w.level] = counts.get(w.level, 0) + 1
    max_level = max(
        (w.level for w in warnings),
        key=lambda x: {"safe": 0, "warn": 1, "danger": 2}[x.value],
        default=RiskLevel.SAFE,
    )
    return {
        "safe": counts[RiskLevel.SAFE],
        "warn": counts[RiskLevel.WARN],
        "danger": counts[RiskLevel.DANGER],
        "total": len(warnings),
        "max_level": max_level.value,
    }


def run_scale_assessment(
    district: dict,
    plots: list[dict],
    thresholds: WarningThreshold | None = None,
) -> dict:
    """一次性运行片区+地块规模预警评估。

    district 字段：id, name, total_area_limit
    plot 字段：id, area, far（可选）, density（可选）, green_rate（可选）
    """
    thresholds = thresholds or WarningThreshold()
    warnings: list[ScaleWarning] = []

    plot_areas: list[float] = []
    for plot in plots:
        area = float(plot.get("area", 0))
        plot_areas.append(area)
        warnings.append(
            assess_plot_intensity(
                plot_id=plot["id"],
                far=plot.get("far"),
                density=plot.get("density"),
                green_rate=plot.get("green_rate"),
                thresholds=thresholds,
            )
        )

    warnings.append(
        assess_district_total(
            district_id=district["id"],
            district_name=district["name"],
            total_area_limit=float(district.get("total_area_limit", 0)),
            plot_areas=plot_areas,
            thresholds=thresholds,
        )
    )

    return {
        "thresholds": thresholds.to_dict(),
        "summary": summarize_warnings(warnings),
        "warnings": [w.to_dict() for w in warnings],
    }
