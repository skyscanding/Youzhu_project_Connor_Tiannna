"""快照层：本地 JSON 快照（data/snapshot/{信源id}.json）。"""
import json
from pathlib import Path

from crawler.extract import Record


def load_snapshot(path: Path) -> dict[str, Record]:
    """读取快照；文件缺失或损坏时返回空字典（相当于首次运行）。"""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {r.identity: r for r in (Record.from_dict(item) for item in data)}


def save_snapshot(path: Path, records: dict[str, Record]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.to_dict() for r in records.values()]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_with_first_seen(old: dict[str, Record], new: dict[str, Record], run_time: str) -> dict[str, Record]:
    """新记录并入快照：老记录保留 first_seen，所有记录刷新 last_seen。"""
    merged: dict[str, Record] = {}
    for key, rec in new.items():
        prev = old.get(key)
        merged[key] = Record(
            title=rec.title,
            url=rec.url,
            date=rec.date,
            doc_number=rec.doc_number,
            first_seen=prev.first_seen if prev else run_time,
            last_seen=run_time,
        )
    return merged
