"""导出抓取结果 Excel：读取 Requesttest/data 快照 + 最新运行报告 + 连通性扫描。

输出三个 Sheet：
1. 抓取总览：信源总数/可达数/命中记录数/日期填充率等
2. 政策记录：全部快照记录（含来源信息，与 URL 日期兜底后的日期字段）
3. 信源状态：全量信源的连通性与错误原因

用法：python export_excel.py [输出路径]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DEFAULT_OUT = BASE.parent / "城市更新政策抓取结果2.xlsx"

LEVEL_CN = {"national": "国家", "provincial": "省级", "city": "市级",
            "district": "区级", "finance": "融资平台"}


def _sources():
    sys.path.insert(0, str(BASE))
    import crawler_standalone as cw
    return cw.SOURCES_BY_ID


def _latest_report() -> dict:
    reports = sorted((DATA / "reports").glob("变更清单-*.json"))
    if not reports:
        raise SystemExit("未找到运行报告（data/reports/）")
    return json.loads(reports[-1].read_text(encoding="utf-8"))


def _scan_data() -> dict:
    path = DATA / "scan_full.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _records_df(sources) -> pd.DataFrame:
    rows = []
    for snapshot in sorted((DATA / "snapshot").glob("*.json")):
        src = sources.get(snapshot.stem)
        if src is None:
            continue
        for rec in json.loads(snapshot.read_text(encoding="utf-8")):
            rows.append({
                "信源ID": src.id,
                "信源名称": src.name,
                "层级": LEVEL_CN.get(src.level, src.level),
                "信源URL": src.url,
                "标题": rec.get("title", ""),
                "记录URL": rec.get("url", ""),
                "日期": rec.get("date", ""),
                "发文号": rec.get("doc_number", ""),
                "首次发现": rec.get("first_seen", ""),
                "最后发现": rec.get("last_seen", ""),
            })
    return pd.DataFrame(rows)


def _status_df(report: dict, scan: dict, sources) -> pd.DataFrame:
    rows = []
    for entry in report["sources"]:
        sid = entry["id"]
        ok = entry["status"] == "ok"
        rows.append({
            "信源ID": sid,
            "信源名称": entry["name"],
            "层级": LEVEL_CN.get(entry["level"], entry["level"]),
            "URL": entry["url"],
            "连通性": "可达" if ok else "不可达",
            "命中记录数": entry["records_found"] if ok else None,
            "页面字节数": scan.get(sid, {}).get("html_len") if ok and scan.get(sid, {}).get("html_len") else None,
            "错误信息": "" if ok else entry["error"],
        })
    return pd.DataFrame(rows)


def main(out_path: Path = DEFAULT_OUT) -> Path:
    sources = _sources()
    report = _latest_report()
    scan = _scan_data()
    summary = report["summary"]

    records_df = _records_df(sources)
    status_df = _status_df(report, scan, sources)

    dated = int(records_df["日期"].astype(str).str.startswith("20").sum()) if len(records_df) else 0
    overview = pd.DataFrame({
        "项目": [
            "生成时间", "MD 信源总数", "可通信源数", "不可达信源数",
            "命中记录数", "新增记录", "更新记录", "消失记录",
            "带日期记录数", "日期填充率", "数据目录",
        ],
        "值": [
            datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            summary["sources_total"], summary["sources_ok"], summary["sources_failed"],
            summary["records_found"], summary["added"], summary["updated"], summary["vanished"],
            dated, f"{dated / len(records_df):.1%}" if len(records_df) else "-",
            str(DATA),
        ],
    })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        overview.to_excel(writer, sheet_name="抓取总览", index=False)
        records_df.to_excel(writer, sheet_name="政策记录", index=False)
        status_df.to_excel(writer, sheet_name="信源状态", index=False)

    print(f"已生成：{out_path}")
    print(f"政策记录 {len(records_df)} 条；带日期 {dated} 条（填充率 {dated / len(records_df):.1%}）")
    return out_path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    main(out)
