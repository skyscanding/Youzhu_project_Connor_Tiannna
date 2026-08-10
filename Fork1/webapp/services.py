"""服务/编排层：加载信源库/规则库 → 调用既有引擎 → 归一化为可渲染 dict。

设计边界（PRD 人机协作）：本层不做任何数值判定，也不含 UI。
- 政策查询：只返回信源库原始记录，未命中显式提示「暂未收录」（FR-01/FR-03）。
- 规模预警：透传 scale.warning 的两级评估。
- 合规校验：透传 compliance.engine 的逐块判定 + 从严冲突 + 总量预警，附条款溯源（FR-08~11）。
"""
from __future__ import annotations

from pathlib import Path

from compliance.engine import check_plot, check_total_area, find_conflicts
from compliance.models import District, Plot
from compliance.store import load_rules
from scale.warning import WarningThreshold, run_scale_assessment
from sourcelib.search import search_documents
from sourcelib.store import Library, load_library

ROOT = Path(__file__).resolve().parent.parent
LIBRARY_PATH = ROOT / "data" / "sourcelib" / "library.json"
RULES_PATH = ROOT / "data" / "rules" / "rules.json"          # 权威空库，待真实数据
SAMPLE_RULES_PATH = ROOT / "data" / "rules" / "rules.sample.json"  # 测试样例（标注非真实条款）

_NOT_FOUND_MSG = "暂未收录，建议前往官方网站检索（可在“政策官方网址”中查渠道入口）。"
_BLANK_MSG = "请输入查询词（如“北京 容积率”或“城市更新”）。"


def get_library(path: Path | None = None) -> Library:
    """加载信源库（人工维护数据，损坏即抛错）。"""
    return load_library(path or LIBRARY_PATH)


# ── 政策查询（FR-01/FR-03/FR-04） ────────────────────────────────────────────
def _doc_to_dict(doc, channel) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "doc_number": doc.doc_number,
        "effective_date": doc.effective_date,
        "status": doc.status,
        "official_url": doc.official_url,
        "channel_id": doc.channel_id,
        "channel_name": (channel.site_name or channel.org) if channel else "",
        "keywords": list(doc.keywords),
    }


def search_policies(query: str, library: Library | None = None) -> dict:
    """按关键词检索信源库，只返回库中原始记录；空查询/未命中给出明确提示。"""
    lib = library or get_library()
    if not query or not query.strip():
        return {"query": query, "count": 0, "results": [], "message": _BLANK_MSG}

    channel_by_id = {c.id: c for c in lib.channels}
    hits = search_documents(list(lib.documents), query, channels=list(lib.channels))
    results = [_doc_to_dict(d, channel_by_id.get(d.channel_id)) for d in hits]
    return {
        "query": query,
        "count": len(results),
        "results": results,
        "message": None if results else _NOT_FOUND_MSG,
    }


# ── 规模预警（FR-09 + 规模传导） ─────────────────────────────────────────────
def assess_scale(district: dict, plots: list[dict], thresholds: dict | None = None) -> dict:
    """片区 + 地块两级规模预警（safe/warn/danger），透传 scale.warning。"""
    wt = WarningThreshold.from_dict(thresholds) if thresholds else WarningThreshold()
    return run_scale_assessment(district, plots, thresholds=wt)


# ── 合规校验（FR-06~11） ─────────────────────────────────────────────────────
def _resolve_rules(library: Library, use_sample: bool):
    """选择规则来源：use_sample→测试样例；否则用权威库（可能为空）。"""
    if use_sample and SAMPLE_RULES_PATH.exists():
        return load_rules(SAMPLE_RULES_PATH, library), True
    return load_rules(RULES_PATH, library), False


def _plot_result_to_dict(result) -> dict:
    return {
        "plot_id": result.plot_id,
        "status": result.status,
        "missing": list(result.missing),
        "checks": [
            {
                "indicator": c.indicator,
                "plot_value": c.plot_value,
                "rule_value": c.rule_value,
                "comparison": c.rule.comparison,
                "allowed": c.allowed,
                "basis": c.basis,
            }
            for c in result.checks
        ],
    }


def check_compliance(
    district: dict,
    plots: list[dict],
    use_sample: bool = True,
    library: Library | None = None,
) -> dict:
    """逐块合规判定 + 多层级从严冲突 + 片区总量预警；每条结论附条款溯源。"""
    lib = library or get_library()
    rules, is_sample = _resolve_rules(lib, use_sample)

    district_obj = District.from_dict(district)
    attributes = district_obj.attributes
    plot_objs = [Plot.from_dict({**p, "district_id": p.get("district_id", district_obj.id)}) for p in plots]

    plot_results = [_plot_result_to_dict(check_plot(p, list(rules), attributes)) for p in plot_objs]
    # 回填地块名（引擎结果只带 id）
    name_by_id = {p["id"]: p.get("name", "") for p in plots}
    for pr in plot_results:
        pr["name"] = name_by_id.get(pr["plot_id"], "")

    conflicts = [
        {
            "indicator": c.indicator,
            "values": list(c.values),
            "comparisons": list(c.comparisons),
            "stricter": c.stricter,
            "note": c.note,
        }
        for c in find_conflicts(list(rules), attributes)
    ]

    total = check_total_area(plot_objs, district_obj)
    return {
        "is_sample": is_sample,
        "rule_count": len(rules),
        "attributes": dict(attributes),
        "plots": plot_results,
        "conflicts": conflicts,
        "total": {
            "total": total.total,
            "limit": total.limit,
            "exceeded": total.exceeded,
            "excess": total.excess,
        },
    }
