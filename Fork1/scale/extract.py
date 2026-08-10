"""解析层：从政策标题/正文中抽取规模指标。

支持两类来源：
1. 政策文本（标题 + 正文）中的数量词，如「12.5万平方米」「3亿元」；
2. 爬虫 Record 的 title，用于快速判断政策是否涉及规模。

所有面积指标统一归一化为「公顷」作为内部标准单位，便于跨地块/片区汇总。
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ScaleIndicator:
    """从政策文本中抽取的一条规模指标。"""

    quantity: float
    unit: str
    indicator_type: str
    raw_text: str
    normalized_value: float | None = None  # 归一化到标准单位后的值

    def to_dict(self) -> dict:
        return asdict(self)


# 数字模式：支持 12,345.67 / 1.2万 / 3,000
_NUMBER_RE = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?:\d+\.?\d*))(?:\s*[万亿])?")

# 面积单位及换算到公顷的系数
_AREA_UNITS: dict[str, float] = {
    "平方米": 0.0001,
    "㎡": 0.0001,
    "m2": 0.0001,
    "万平方米": 1.0,
    "万㎡": 1.0,
    "公顷": 1.0,
    "hm2": 1.0,
    "平方千米": 100.0,
    "平方公里": 100.0,
    "km2": 100.0,
    "亩": 1.0 / 15.0,
}

# 投资单位
_INVESTMENT_UNITS = ("亿元", "万元", "元")

# 指标类型关键词映射
_INDICATOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "area": ("占地", "用地面积", "占地面积", "改造范围", "实施范围", "规划范围"),
    "building_area": ("建筑规模", "建筑面积", "新建", "地上建筑", "总建筑面积"),
    "investment": ("总投资", "投资", "投资额"),
    "household": ("户", "居民", "住户"),
    "population": ("人", "人口"),
    "floor_area_ratio": ("容积率", "综合容积率", "容积率控制"),
    "density": ("建筑密度", "密度"),
    "green_rate": ("绿地率", "绿化率"),
}


def _clean_number(raw: str) -> float:
    """把「1,234.56」或「1.2万」中的数字部分转为 float。"""
    raw = raw.replace(",", "")
    # 当前先处理显式带单位「万」的情况；「亿」保持原数量
    multiplier = 1.0
    if raw.endswith("万"):
        multiplier = 1.0
        raw = raw[:-1]
    elif raw.endswith("亿"):
        multiplier = 1.0
        raw = raw[:-1]
    return float(raw) * multiplier


def normalize_area(quantity: float, unit: str) -> float | None:
    """把面积单位统一换算为公顷；非面积单位返回 None。"""
    unit = unit.strip().lower()
    mapping = {k.lower(): v for k, v in _AREA_UNITS.items()}
    factor = mapping.get(unit)
    if factor is None:
        return None
    return quantity * factor


def _deduplicate_matches(matches: list[tuple[int, int, ScaleIndicator]]) -> list[ScaleIndicator]:
    """移除相互重叠的匹配项，保留先匹配到的。"""
    if not matches:
        return []
    matches.sort(key=lambda x: x[0])
    kept: list[tuple[int, int, ScaleIndicator]] = []
    for start, end, indicator in matches:
        if any(start < k_end and end > k_start for k_start, k_end, _ in kept):
            continue
        kept.append((start, end, indicator))
    return [ind for _, _, ind in kept]


def extract_scale_indicators(text: str) -> list[ScaleIndicator]:
    """从政策文本中提取规模指标列表。"""
    if not text:
        return []

    matches: list[tuple[int, int, ScaleIndicator]] = []

    # 1. 面积：数字 + 面积单位
    area_pattern = re.compile(
        r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?:\d+\.?\d*))\s*(万平方米|万㎡|㎡|平方米|m2|公顷|hm2|平方千米|平方公里|km2|亩)"
    )
    for m in area_pattern.finditer(text):
        quantity = _clean_number(m.group(1))
        unit = m.group(2)
        normalized = normalize_area(quantity, unit)
        indicator_type = "building_area" if any(k in text[max(0, m.start() - 15):m.end()] for k in _INDICATOR_KEYWORDS["building_area"]) else "area"
        matches.append(
            (
                m.start(),
                m.end(),
                ScaleIndicator(
                    quantity=quantity,
                    unit=unit,
                    indicator_type=indicator_type,
                    raw_text=m.group(0),
                    normalized_value=normalized,
                ),
            )
        )

    # 2. 投资：数字 + 亿元/万元/元
    investment_pattern = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?:\d+\.?\d*))\s*(亿元|万元|元)")
    for m in investment_pattern.finditer(text):
        quantity = _clean_number(m.group(1))
        unit = m.group(2)
        matches.append(
            (
                m.start(),
                m.end(),
                ScaleIndicator(
                    quantity=quantity,
                    unit=unit,
                    indicator_type="investment",
                    raw_text=m.group(0),
                ),
            )
        )

    # 3. 户数/人口
    household_pattern = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?:\d+\.?\d*))\s*户")
    for m in household_pattern.finditer(text):
        quantity = _clean_number(m.group(1))
        matches.append(
            (
                m.start(),
                m.end(),
                ScaleIndicator(
                    quantity=quantity,
                    unit="户",
                    indicator_type="household",
                    raw_text=m.group(0),
                ),
            )
        )

    population_pattern = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?:\d+\.?\d*))\s*人")
    for m in population_pattern.finditer(text):
        quantity = _clean_number(m.group(1))
        matches.append(
            (
                m.start(),
                m.end(),
                ScaleIndicator(
                    quantity=quantity,
                    unit="人",
                    indicator_type="population",
                    raw_text=m.group(0),
                ),
            )
        )

    # 4. 强度指标：容积率/密度/绿地率（数字 + 可选 %）
    intensity_patterns = [
        (r"容积率.*?控制?在?\s*(\d+\.?\d*)", "floor_area_ratio"),
        (r"综合容积率\s*(\d+\.?\d*)", "floor_area_ratio"),
        (r"容积率\s*(\d+\.?\d*)", "floor_area_ratio"),
        (r"建筑密度.*?不大于?\s*(\d+\.?\d*)\s*%?", "density"),
        (r"建筑密度\s*(\d+\.?\d*)\s*%?", "density"),
        (r"密度\s*(\d+\.?\d*)\s*%?", "density"),
        (r"绿地率.*?不低?于?\s*(\d+\.?\d*)\s*%?", "green_rate"),
        (r"绿地率\s*(\d+\.?\d*)\s*%?", "green_rate"),
        (r"绿化率\s*(\d+\.?\d*)\s*%?", "green_rate"),
    ]
    for pattern, indicator_type in intensity_patterns:
        for m in re.finditer(pattern, text):
            quantity = _clean_number(m.group(1))
            # 密度/绿地率等带 % 的按百分数处理；容积率（floor_area_ratio）不加 %
            if indicator_type != "floor_area_ratio" and "%" in m.group(0):
                quantity = quantity / 100.0 if quantity > 1 else quantity
            unit = "" if indicator_type == "floor_area_ratio" else "%"
            matches.append(
                (
                    m.start(),
                    m.end(),
                    ScaleIndicator(
                        quantity=quantity,
                        unit=unit,
                        indicator_type=indicator_type,
                        raw_text=m.group(0),
                    ),
                )
            )

    return _deduplicate_matches(matches)


def extract_indicators_from_record_title(title: str) -> list[ScaleIndicator]:
    """对爬虫抓取的标题做快速规模指标提取。"""
    return extract_scale_indicators(title)
