"""CLI 入口：逐信源抓取 → 对比快照 → 输出变更清单。

用法：
    python -m crawler                     # 检查全部 25 个信源
    python -m crawler --source govcn      # 只检查指定信源
    python -m crawler --list-sources      # 列出全部信源
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from crawler import diff, extract, fetch, snapshot
from crawler.sources import SOURCES

DEFAULT_DATA_DIR = str(Path(__file__).resolve().parent.parent / "data")


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="python -m crawler",
        description="城市更新政策定向爬虫：抓取官方信源列表页，对比快照输出变更清单（只读，不修改规则库）。",
    )
    parser.add_argument("--source", action="append", metavar="ID", help="只检查指定信源（可多次指定）；缺省为全部信源")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help=f"数据目录（默认 {DEFAULT_DATA_DIR}）")
    parser.add_argument("--timeout", type=float, default=8.0, help="单次请求超时秒数（默认 8）")
    parser.add_argument("--retries", type=int, default=1, help="失败重试次数（默认 1）")
    parser.add_argument("--politeness-delay", type=float, default=1.0, help="信源之间的礼貌延时秒数（默认 1）")
    parser.add_argument("--proxy", help="HTTP(S) 代理地址，如 http://127.0.0.1:7897；也可用 HTTPS_PROXY/HTTP_PROXY 环境变量")
    parser.add_argument("--list-sources", action="store_true", help="列出全部信源后退出")
    return parser.parse_args(argv)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _snapshot_path(data_dir: Path, source_id: str) -> Path:
    return data_dir / "snapshot" / f"{source_id}.json"


def _changes_dict(result: diff.DiffResult) -> dict:
    return {
        "added": [r.to_dict() for r in result.added],
        "updated": [{"old": old.to_dict(), "new": new.to_dict()} for old, new in result.updated],
        "vanished": [r.to_dict() for r in result.vanished],
    }


def _summarize(sources_report: list[dict]) -> dict:
    ok = [s for s in sources_report if s["status"] == "ok"]
    return {
        "sources_total": len(sources_report),
        "sources_ok": len(ok),
        "sources_failed": len(sources_report) - len(ok),
        "records_found": sum(s["records_found"] for s in ok),
        "added": sum(len(s["changes"]["added"]) for s in ok),
        "updated": sum(len(s["changes"]["updated"]) for s in ok),
        "vanished": sum(len(s["changes"]["vanished"]) for s in ok),
    }


def main(argv=None, now: str | None = None) -> dict | None:
    """运行一轮抓取与对比，返回报告字典；未知信源 ID 时返回 None。"""
    args = _parse_args(argv)

    if args.list_sources:
        for src in SOURCES:
            print(f"{src.id}\t{src.level}\t{src.name}\t{src.url}")
        return {}

    unknown = set(args.source or []) - {s.id for s in SOURCES}
    if unknown:
        print(f"未知信源 ID：{', '.join(sorted(unknown))}（可用 --list-sources 查看全部）", file=sys.stderr)
        return None

    selected = [s for s in SOURCES if not args.source or s.id in args.source]
    run_at = now or _now_iso()
    data_dir = Path(args.data_dir)
    session = requests.Session()
    if args.proxy:
        session.proxies = {"http": args.proxy, "https": args.proxy}

    sources_report: list[dict] = []
    for index, src in enumerate(selected):
        entry = {
            "id": src.id,
            "name": src.name,
            "level": src.level,
            "url": src.url,
            "status": "ok",
            "records_found": 0,
            "changes": {"added": [], "updated": [], "vanished": []},
            "error": "",
        }
        try:
            html = fetch.fetch_html(session, src.url, timeout=args.timeout, retries=args.retries)
            records = extract.extract_records(html, src.url, src.keywords)
            new_by_id = {r.identity: r for r in records}
            old = snapshot.load_snapshot(_snapshot_path(data_dir, src.id))
            result = diff.diff_records(old, new_by_id)
            merged = snapshot.merge_with_first_seen(old, new_by_id, run_at)
            snapshot.save_snapshot(_snapshot_path(data_dir, src.id), merged)
            entry["records_found"] = len(records)
            entry["changes"] = _changes_dict(result)
        except Exception as exc:  # 单信源失败不影响其他信源（FR-15 定向监测需整体可用）
            entry["status"] = "error"
            entry["error"] = f"{type(exc).__name__}: {exc}"
        sources_report.append(entry)
        if index < len(selected) - 1:
            time.sleep(args.politeness_delay)

    report = {"run_at": run_at, "summary": _summarize(sources_report), "sources": sources_report}
    _write_report(data_dir, report)
    _print_summary(report)
    return report


def _report_path(data_dir: Path, run_at: str) -> Path:
    stamp = run_at.replace("T", "-").replace(":", "-")[:19]
    return data_dir / "reports" / f"变更清单-{stamp}.json"


def _write_report(data_dir: Path, report: dict) -> None:
    path = _report_path(data_dir, report["run_at"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告已写入：{path}")


def _print_summary(report: dict) -> None:
    s = report["summary"]
    print(f"运行时间：{report['run_at']}")
    print(f"信源：{s['sources_total']} 个，成功 {s['sources_ok']}，失败 {s['sources_failed']}")
    print(f"命中记录：{s['records_found']} 条；新增 {s['added']}，更新 {s['updated']}，消失 {s['vanished']}")
    for entry in report["sources"]:
        if entry["status"] == "error":
            print(f"  [失败] {entry['name']}（{entry['id']}）：{entry['error']}")
            continue
        for rec in entry["changes"]["added"]:
            print(f"  [新增] {entry['name']}｜{rec['title']}｜{rec['url']}")
        for item in entry["changes"]["updated"]:
            print(f"  [更新] {entry['name']}｜{item['old']['title']} → {item['new']['title']}｜{item['new']['url']}")
        for rec in entry["changes"]["vanished"]:
            print(f"  [消失] {entry['name']}｜{rec['title']}｜{rec['url']}（未出现在本次列表中，可能下架或分页截断，请人工确认）")
