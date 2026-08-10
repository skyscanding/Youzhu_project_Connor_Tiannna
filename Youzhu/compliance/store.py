"""模块2 规则库存储与契约验证。

契约（contract-first）：data/rules/rules.json 为权威边界。
规则记录的 source_doc_id 必须解析到信源库中的真实文档（FR-11 可溯源）；
规则库损坏/非法必须显式报错（与 sourcelib 相同的容错原则）。
"""
import json
from pathlib import Path

from compliance.models import Rule, ValidationError, validate_rule
from sourcelib.store import Library

SCHEMA_VERSION = "1.0"


def validate_rules(rules: tuple[Rule, ...], library: Library) -> list[str]:
    """全库校验：单条规则 + id 唯一性 + 来源文件契约（FR-11）。"""
    errors = []
    for rule in rules:
        errors.extend(validate_rule(rule))
    rule_ids = [r.id for r in rules]
    if len(rule_ids) != len(set(rule_ids)):
        errors.append("规则 id 重复")
    doc_ids = {d.id for d in library.documents}
    for rule in rules:
        if rule.source_doc_id not in doc_ids:
            errors.append(
                f"规则 {rule.id} 引用的来源文件 {rule.source_doc_id} 不在信源库中（FR-11 契约）"
            )
    return errors


def load_rules(path: Path, library: Library) -> tuple[Rule, ...]:
    """读取并校验规则库；文件缺失、JSON 损坏或数据非法均抛异常。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    rules = tuple(Rule.from_dict(r) for r in raw.get("rules", []))
    errors = validate_rules(rules, library)
    if errors:
        raise ValidationError("规则库数据非法：\n- " + "\n- ".join(errors))
    return rules


def save_rules(path: Path, rules: list[Rule], library: Library) -> None:
    """校验后写入规则库 JSON（含契约版本号）。"""
    errors = validate_rules(tuple(rules), library)
    if errors:
        raise ValidationError("规则库数据非法：\n- " + "\n- ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": SCHEMA_VERSION, "rules": [r.to_dict() for r in rules]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
