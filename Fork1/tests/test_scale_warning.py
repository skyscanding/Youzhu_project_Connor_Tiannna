"""Tests for scale.warning: two-level (district/plot) scale warning engine."""
import pytest

from scale.warning import (
    RiskLevel,
    ScaleWarning,
    WarningThreshold,
    assess_district_total,
    assess_plot_intensity,
    summarize_warnings,
)


class TestWarningThreshold:
    def test_default_thresholds(self):
        t = WarningThreshold()
        assert t.district_total_area_ratio_warn == 0.8
        assert t.district_total_area_ratio_danger == 1.0
        assert t.plot_far_warn == 2.5
        assert t.plot_far_danger == 3.0


class TestAssessPlotIntensity:
    def test_safe_floor_area_ratio(self):
        result = assess_plot_intensity(plot_id="p1", far=2.0, density=0.20, green_rate=0.35)
        assert result.level == RiskLevel.SAFE
        assert result.plot_id == "p1"

    def test_warn_floor_area_ratio(self):
        result = assess_plot_intensity(plot_id="p1", far=2.7, density=0.20, green_rate=0.35)
        assert result.level == RiskLevel.WARN
        assert "容积率" in result.reason

    def test_danger_floor_area_ratio(self):
        result = assess_plot_intensity(plot_id="p1", far=3.2, density=0.20, green_rate=0.35)
        assert result.level == RiskLevel.DANGER

    def test_density_warning(self):
        result = assess_plot_intensity(plot_id="p2", far=2.0, density=0.30, green_rate=0.35)
        assert result.level == RiskLevel.WARN

    def test_green_rate_warning(self):
        result = assess_plot_intensity(plot_id="p3", far=2.0, density=0.20, green_rate=0.25)
        assert result.level == RiskLevel.WARN

    def test_green_rate_danger(self):
        # 绿地率低于 danger 阈值(0.20) 应为 DANGER，而非仅 WARN
        result = assess_plot_intensity(plot_id="p3d", far=2.0, density=0.20, green_rate=0.15)
        assert result.level == RiskLevel.DANGER

    def test_green_rate_safe_at_min(self):
        # 绿地率恰好达到下限 0.30 即合规（“不得低于该值”→ 等于视为达标）
        result = assess_plot_intensity(plot_id="p3s", far=2.0, density=0.20, green_rate=0.30)
        assert result.level == RiskLevel.SAFE

    def test_only_provided_indicators_are_checked(self):
        result = assess_plot_intensity(plot_id="p4", far=2.0)
        assert result.level == RiskLevel.SAFE
        assert result.density is None

    def test_negative_indicator_is_danger(self):
        result = assess_plot_intensity(plot_id="p5", far=-1.0)
        assert result.level == RiskLevel.DANGER
        assert "非法" in result.reason


class TestAssessDistrictTotal:
    def test_safe_when_under_warn(self):
        result = assess_district_total(
            district_id="d1",
            district_name="片区A",
            total_area_limit=100.0,
            plot_areas=[30.0, 40.0],
        )
        assert result.level == RiskLevel.SAFE
        assert result.total_area == pytest.approx(70.0)

    def test_warn_when_near_limit(self):
        result = assess_district_total(
            district_id="d1",
            district_name="片区A",
            total_area_limit=100.0,
            plot_areas=[45.0, 40.0],
        )
        assert result.level == RiskLevel.WARN
        assert result.ratio == pytest.approx(0.85)

    def test_danger_when_exceeds_limit(self):
        result = assess_district_total(
            district_id="d1",
            district_name="片区A",
            total_area_limit=100.0,
            plot_areas=[60.0, 50.0],
        )
        assert result.level == RiskLevel.DANGER
        assert result.ratio == pytest.approx(1.1)

    def test_danger_with_zero_limit(self):
        result = assess_district_total(
            district_id="d1",
            district_name="片区A",
            total_area_limit=0.0,
            plot_areas=[10.0],
        )
        assert result.level == RiskLevel.DANGER

    def test_empty_plot_areas_is_safe(self):
        result = assess_district_total(
            district_id="d1",
            district_name="片区A",
            total_area_limit=100.0,
            plot_areas=[],
        )
        assert result.level == RiskLevel.SAFE
        assert result.total_area == pytest.approx(0.0)


class TestSummarizeWarnings:
    def test_summary_counts(self):
        warnings = [
            ScaleWarning(plot_id="p1", level=RiskLevel.SAFE, reason="ok"),
            ScaleWarning(plot_id="p2", level=RiskLevel.WARN, reason="warn"),
            ScaleWarning(district_id="d1", level=RiskLevel.DANGER, reason="danger"),
        ]
        summary = summarize_warnings(warnings)
        assert summary["safe"] == 1
        assert summary["warn"] == 1
        assert summary["danger"] == 1
        assert summary["max_level"] == "danger"

    def test_empty_summary(self):
        summary = summarize_warnings([])
        assert summary["safe"] == 0
        assert summary["max_level"] == "safe"
