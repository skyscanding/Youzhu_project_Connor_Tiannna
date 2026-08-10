"""变更检测：与上次快照对比，区分 新增 / 更新 / 消失。"""
from dataclasses import dataclass

from crawler.extract import Record


@dataclass
class DiffResult:
    added: list[Record]
    updated: list[tuple[Record, Record]]  # (旧记录, 新记录)
    vanished: list[Record]


def diff_records(old: dict[str, Record], new: dict[str, Record]) -> DiffResult:
    added = [rec for key, rec in new.items() if key not in old]
    updated: list[tuple[Record, Record]] = []
    vanished: list[Record] = []
    for key, prev in old.items():
        if key not in new:
            vanished.append(prev)
            continue
        curr = new[key]
        if prev.signature() != curr.signature():
            updated.append((prev, curr))
    return DiffResult(added=added, updated=updated, vanished=vanished)
