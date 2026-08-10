"""模块2 数据模型：规则、片区、地块 + 校验规则（规则库 JSON 契约的机器可检查部分）。"""
from dataclasses import asdict, dataclass, field

VALID_LEVELS = ("national", "city", "district")
# 约束方向：le=不得超过上限，ge=不得低于下限，eq=精确取值
VALID_COMPARISONS = ("le", "ge", "eq")


class ValidationError(ValueError):
    """合规数据校验失败（人工维护数据，非法必须显式暴露）。"""


def _validate_attributes(attributes: dict, label: str, errors: list[str]) -> None:
    for key, value in attributes.items():
        if not key:
            errors.append(f"{label} 存在空键")
        if not value:
            errors.append(f"{label} 存在空值（键 {key!r}）")


@dataclass(frozen=True)
class Rule:
    """一条指标规则（由专业人员录入，不允许程序生成）。"""

    id: str
    indicator: str          # 指标名：容积率上限/绿地率下限/退线距离…
    level: str              # 文件层级：national/city/district
    source_doc_id: str      # 来源文件（信源库文档 id，契约约束）
    clause: str             # 条款号（如 第X条；人工录入原文）
    clause_text: str        # 条款原文片段（人工录入，FR-11 核验的数据基础）
    comparison: str = "le"  # le/ge/eq
    value: float | None = None   # 限值；None=未标定（须在 note 注明）
    applies_to: dict = field(default_factory=dict)  # 适用条件（片区属性子集）
    mandatory: bool = True  # 是否强制性条文
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        value = data.get("value")
        return cls(
            id=data.get("id", ""),
            indicator=data.get("indicator", ""),
            level=data.get("level", ""),
            source_doc_id=data.get("source_doc_id", ""),
            clause=data.get("clause", ""),
            clause_text=data.get("clause_text", ""),
            comparison=data.get("comparison", "le"),
            value=float(value) if value is not None else None,
            applies_to=dict(data.get("applies_to") or {}),
            mandatory=bool(data.get("mandatory", True)),
            note=data.get("note", ""),
        )


@dataclass(frozen=True)
class District:
    """片区：合规校验的单位，携带适用性判断所需的属性。"""

    id: str
    name: str
    total_area_limit: float        # 片区总规模上限（万㎡）
    attributes: dict = field(default_factory=dict)  # 更新类型/实施方式/区位/特定范围

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "District":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            total_area_limit=float(data.get("total_area_limit", 0)),
            attributes=dict(data.get("attributes") or {}),
        )


@dataclass(frozen=True)
class Plot:
    """地块：片区内按分期切分的用地，携带指标值（表单/LLM 抽取回填后确认）。"""

    id: str
    district_id: str
    name: str
    area: float                   # 用地面积（万㎡）
    indicators: dict = field(default_factory=dict)  # 指标名 → 数值

    def to_dict(self) -> dict:
        data = asdict(self)
        data["indicators"] = {k: float(v) for k, v in self.indicators.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Plot":
        return cls(
            id=data.get("id", ""),
            district_id=data.get("district_id", ""),
            name=data.get("name", ""),
            area=float(data.get("area", 0)),
            indicators={k: float(v) for k, v in (data.get("indicators") or {}).items()},
        )


def validate_rule(rule: Rule, strict: bool = False) -> list[str]:
    """返回校验错误列表；strict=True 时直接抛 ValidationError。"""
    errors = []
    if not rule.id:
        errors.append("规则 id 为空")
    if not rule.indicator:
        errors.append(f"[{rule.id}] 指标为空")
    if rule.level not in VALID_LEVELS:
        errors.append(f"[{rule.id}] 文件层级非法：{rule.level!r}")
    if not rule.source_doc_id:
        errors.append(f"[{rule.id}] 来源文件为空（FR-11 需可溯源）")
    if not rule.clause:
        errors.append(f"[{rule.id}] 条款号为空（FR-11 需可溯源）")
    if not rule.clause_text:
        errors.append(f"[{rule.id}] 条款原文片段为空（FR-11 核验依据）")
    if rule.comparison not in VALID_COMPARISONS:
        errors.append(f"[{rule.id}] 比较方向非法：{rule.comparison!r}")
    if rule.value is not None and rule.value < 0:
        errors.append(f"[{rule.id}] 限值不能为负：{rule.value}")
    if rule.value is None and not rule.note:
        errors.append(f"[{rule.id}] 数值未标定（None）必须注明原因")
    _validate_attributes(rule.applies_to, f"[{rule.id}] 适用条件", errors)
    if strict and errors:
        raise ValidationError("；".join(errors))
    return errors


def validate_district(district: District) -> list[str]:
    errors = []
    if not district.id:
        errors.append("片区 id 为空")
    if not district.name:
        errors.append(f"[{district.id}] 名称为空")
    if district.total_area_limit < 0:
        errors.append(f"[{district.id}] 总规模上限不能为负")
    _validate_attributes(district.attributes, f"[{district.id}] 片区属性", errors)
    return errors


def validate_plot(plot: Plot) -> list[str]:
    errors = []
    if not plot.id:
        errors.append("地块 id 为空")
    if not plot.district_id:
        errors.append(f"[{plot.id}] 所属片区为空")
    if not plot.name:
        errors.append(f"[{plot.id}] 名称为空")
    if plot.area < 0:
        errors.append(f"[{plot.id}] 用地面积不能为负")
    for indicator, value in plot.indicators.items():
        if value < 0:
            errors.append(f"[{plot.id}] 指标 {indicator} 数值不能为负：{value}")
    return errors
