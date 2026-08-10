"""python -m compliance：规则库初始化与校验（模块2 契约工具）。"""
import argparse
import sys
from pathlib import Path

from compliance.store import load_rules, save_rules
from sourcelib.store import load_library

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES_DIR = PROJECT_ROOT / "data" / "rules"
LIBRARY_PATH = PROJECT_ROOT / "data" / "sourcelib" / "library.json"


def _force_utf8_stdio() -> None:
    """确保在非 UTF-8 控制台（Windows cp1252/cp936 等）下也能输出中文，避免 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def _library():
    return load_library(LIBRARY_PATH)


def init_rules(rules_dir: Path) -> Path:
    """初始化空规则库（数值由专业人员后续录入）。"""
    path = rules_dir / "rules.json"
    save_rules(path, [], _library())
    print(f"规则库已初始化（空）：{path}（schema v{1.0}，待专业人员录入）")
    return path


def validate_rules_file(rules_dir: Path) -> int:
    """校验规则库（含与信源库的引用契约）。"""
    path = rules_dir / "rules.json"
    rules = load_rules(path, _library())
    print(f"规则库校验通过：{path}（{len(rules)} 条规则）")
    return len(rules)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="python -m compliance", description="模块2 规则库工具")
    parser.add_argument("--init", action="store_true", help="初始化空规则库")
    parser.add_argument("--validate", action="store_true", help="校验规则库（含信源库引用契约）")
    parser.add_argument("--rules-dir", default=str(DEFAULT_RULES_DIR), help=f"规则库目录（默认 {DEFAULT_RULES_DIR}）")
    args = parser.parse_args()

    _force_utf8_stdio()
    rules_dir = Path(args.rules_dir)
    if args.init:
        init_rules(rules_dir)
    elif args.validate:
        validate_rules_file(rules_dir)
    else:
        parser.error("请指定 --init 或 --validate")
    sys.exit(0)
