"""信源库存储：JSON 读写 + 全库校验。

信源库为人工维护的数据，文件缺失/损坏/非法必须显式报错
（区别于爬虫快照的静默容忍——那里是临时监测数据，这里是事实基准）。
"""
import json
from dataclasses import dataclass
from pathlib import Path

from sourcelib.models import (
    Channel,
    PolicyDocument,
    ValidationError,
    validate_channel,
    validate_document,
)


@dataclass(frozen=True)
class Library:
    channels: tuple
    documents: tuple

    def __post_init__(self):
        # 统一为 tuple，保证 list/tuple 两种构造方式的相等性一致
        object.__setattr__(self, "channels", tuple(self.channels))
        object.__setattr__(self, "documents", tuple(self.documents))


def validate_library(library: Library) -> list[str]:
    """全库校验：单条规则 + 唯一性 + 文档对渠道的引用完整性。"""
    errors = []
    for channel in library.channels:
        errors.extend(validate_channel(channel))
    for doc in library.documents:
        errors.extend(validate_document(doc))

    channel_ids = [c.id for c in library.channels]
    if len(channel_ids) != len(set(channel_ids)):
        errors.append("渠道 id 重复")
    doc_ids = [d.id for d in library.documents]
    if len(doc_ids) != len(set(doc_ids)):
        errors.append("文档 id 重复")

    known = set(channel_ids)
    for doc in library.documents:
        if doc.channel_id and doc.channel_id not in known:
            errors.append(f"文档 {doc.id} 引用了不存在的渠道 {doc.channel_id}")
    return errors


def load_library(path: Path) -> Library:
    """读取并校验信源库；文件缺失、JSON 损坏或数据非法均抛异常。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    library = Library(
        channels=tuple(Channel.from_dict(c) for c in raw.get("channels", [])),
        documents=tuple(PolicyDocument.from_dict(d) for d in raw.get("documents", [])),
    )
    errors = validate_library(library)
    if errors:
        raise ValidationError("信源库数据非法：\n- " + "\n- ".join(errors))
    return library


def save_library(path: Path, library: Library) -> None:
    """校验后写入信源库 JSON。"""
    errors = validate_library(library)
    if errors:
        raise ValidationError("信源库数据非法：\n- " + "\n- ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "channels": [c.to_dict() for c in library.channels],
        "documents": [d.to_dict() for d in library.documents],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
