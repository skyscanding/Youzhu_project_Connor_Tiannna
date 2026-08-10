"""模块2 存储与契约测试：规则库 JSON 读写 + 与信源库的交叉引用（FR-11 条款核验的数据基础）。

契约（contract-first）：data/rules/rules.json 的 schema 为权威边界；
规则记录的 source_doc_id 必须解析到信源库中的真实文档——测试即契约验证。
"""
import subprocess
import sys
from pathlib import Path

import pytest

from compliance.models import Rule
from compliance.store import load_rules, save_rules
from sourcelib.store import load_library

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_PATH = PROJECT_ROOT / "data" / "sourcelib" / "library.json"


def _rule(rule_id="r-001", source_doc_id="bj-jianzhu-guimo", value=3.5, **overrides):
    data = dict(
        id=rule_id,
        indicator="容积率上限",
        level="city",
        source_doc_id=source_doc_id,
        clause=f"测试样例条款-{rule_id}",
        clause_text="【测试样例，非真实条款】容积率不得超过 3.5",
        comparison="le",
        value=value,
        applies_to={"更新类型": "老旧小区改造"},
        mandatory=True,
        note="",
    )
    data.update(overrides)
    return Rule(**data)


@pytest.fixture(scope="module")
def library():
    return load_library(LIBRARY_PATH)


def test_save_and_load_roundtrip(tmp_path, library):
    path = tmp_path / "rules.json"
    rules = [_rule(), _rule("r-002", indicator="绿地率下限", comparison="ge", value=0.3)]
    save_rules(path, rules, library)

    loaded = load_rules(path, library)
    assert list(loaded) == rules


def test_missing_file_raises(tmp_path, library):
    with pytest.raises(FileNotFoundError):
        load_rules(tmp_path / "nope.json", library)


def test_corrupt_json_raises(tmp_path, library):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_rules(path, library)


def test_rule_with_unknown_source_doc_rejected(tmp_path, library):
    """FR-11 契约：规则引用的来源文件必须存在于信源库（写入时即拦截）。"""
    path = tmp_path / "dangling.json"
    with pytest.raises(ValueError, match="ghost-doc"):
        save_rules(path, [_rule(source_doc_id="ghost-doc")], library)


def test_load_rejects_rule_with_unknown_doc(tmp_path, library):
    """手工编辑的 JSON 若违反契约，读取时必须报错（load 侧同样拦截）。"""
    path = tmp_path / "raw.json"
    path.write_text(
        '{"rules": [{"id": "x", "indicator": "容积率", "level": "city",'
        ' "source_doc_id": "ghost-doc", "clause": "c", "clause_text": "t",'
        ' "comparison": "le", "value": 1.0}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="ghost-doc"):
        load_rules(path, library)


def test_duplicate_rule_ids_rejected(tmp_path, library):
    path = tmp_path / "dup.json"
    with pytest.raises(ValueError):
        save_rules(path, [_rule("r-dup"), _rule("r-dup")], library)


def test_empty_rules_library_is_valid(tmp_path, library):
    path = tmp_path / "empty.json"
    save_rules(path, [], library)
    assert list(load_rules(path, library)) == []


def test_contract_real_library_has_documents(library):
    """前置契约：信源库中必须存在可被规则引用的文档。"""
    assert len(library.documents) >= 15


def test_cli_init_and_validate(tmp_path, library):
    """python -m compliance --init 生成空规则库；--validate 校验通过。"""
    out = tmp_path / "rules"
    proc = subprocess.run(
        [sys.executable, "-m", "compliance", "--init", "--rules-dir", str(out)],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    rules_path = out / "rules.json"
    assert rules_path.exists()
    assert list(load_rules(rules_path, library)) == []

    proc2 = subprocess.run(
        [sys.executable, "-m", "compliance", "--validate", "--rules-dir", str(out)],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=60,
    )
    assert proc2.returncode == 0, proc2.stderr
