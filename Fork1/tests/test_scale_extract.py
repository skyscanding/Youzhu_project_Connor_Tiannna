"""Tests for scale.extract: parse scale indicators from policy text/title."""
import pytest

from scale.extract import extract_scale_indicators, normalize_area


class TestNormalizeArea:
    def test_wan_square_meter(self):
        assert normalize_area(10.0, "万平方米") == pytest.approx(10.0)
        assert normalize_area(10.0, "万㎡") == pytest.approx(10.0)

    def test_square_meter(self):
        assert normalize_area(100000.0, "平方米") == pytest.approx(10.0)
        assert normalize_area(100000.0, "㎡") == pytest.approx(10.0)

    def test_hectare(self):
        assert normalize_area(1.0, "公顷") == pytest.approx(1.0)
        assert normalize_area(1.0, "hm2") == pytest.approx(1.0)

    def test_mu(self):
        assert normalize_area(15.0, "亩") == pytest.approx(1.0)

    def test_square_kilometer(self):
        # 1 平方千米 = 100 公顷，故 0.1 平方千米 = 10 公顷
        assert normalize_area(0.1, "平方千米") == pytest.approx(10.0)
        assert normalize_area(0.1, "km2") == pytest.approx(10.0)
        # 边界：0.01 平方千米 = 1 公顷（回归防呆，防止误改换算系数）
        assert normalize_area(0.01, "平方千米") == pytest.approx(1.0)

    def test_unknown_unit_returns_none(self):
        assert normalize_area(10.0, "光年") is None


class TestExtractScaleIndicators:
    def test_extract_area_units(self):
        text = "项目占地约12.5万平方米，总投资3亿元"
        indicators = extract_scale_indicators(text)
        assert len(indicators) >= 2
        area = next(i for i in indicators if i.indicator_type == "area")
        assert area.quantity == pytest.approx(12.5)
        assert area.unit == "万平方米"
        assert area.normalized_value == pytest.approx(12.5)
        investment = next(i for i in indicators if i.indicator_type == "investment")
        assert investment.quantity == pytest.approx(3.0)
        assert investment.unit == "亿元"

    def test_extract_hectare_and_mu(self):
        text = "改造范围约50公顷，折合750亩"
        indicators = extract_scale_indicators(text)
        values = {i.unit: i.normalized_value for i in indicators if i.indicator_type == "area"}
        assert values["公顷"] == pytest.approx(50.0)
        assert values["亩"] == pytest.approx(50.0)

    def test_extract_household_and_population(self):
        text = "涉及居民1200户、人口约3500人"
        indicators = extract_scale_indicators(text)
        household = next(i for i in indicators if i.indicator_type == "household")
        assert household.quantity == pytest.approx(1200.0)
        population = next(i for i in indicators if i.indicator_type == "population")
        assert population.quantity == pytest.approx(3500.0)

    def test_extract_building_area(self):
        text = "新建地上建筑规模不超过8.6万㎡"
        indicators = extract_scale_indicators(text)
        area = next(i for i in indicators if i.indicator_type == "building_area")
        assert area.quantity == pytest.approx(8.6)
        assert area.unit == "万㎡"

    def test_extract_floor_area_ratio(self):
        text = "综合容积率控制在2.5以内"
        indicators = extract_scale_indicators(text)
        far = next(i for i in indicators if i.indicator_type == "floor_area_ratio")
        assert far.quantity == pytest.approx(2.5)
        assert far.unit == ""

    def test_extract_density(self):
        text = "居住建筑密度不大于22%"
        indicators = extract_scale_indicators(text)
        density = next(i for i in indicators if i.indicator_type == "density")
        assert density.quantity == pytest.approx(0.22)

    def test_extract_green_rate(self):
        text = "绿地率不低于30%"
        indicators = extract_scale_indicators(text)
        green = next(i for i in indicators if i.indicator_type == "green_rate")
        assert green.quantity == pytest.approx(0.30)

    def test_no_duplicate_overlapping_matches(self):
        text = "投资约2.5亿元"
        indicators = extract_scale_indicators(text)
        assert len([i for i in indicators if i.indicator_type == "investment"]) == 1

    def test_empty_text_returns_empty(self):
        assert extract_scale_indicators("") == []

    def test_text_without_numbers_returns_empty(self):
        assert extract_scale_indicators("本办法自发布之日起施行。") == []
