"""快照层测试：JSON 快照读写与 first_seen/last_seen 合并。"""
from crawler.extract import Record
from crawler.snapshot import load_snapshot, merge_with_first_seen, save_snapshot


def _records(*items):
    return {r.identity: r for r in items}


def test_roundtrip(tmp_path):
    path = tmp_path / "govcn.json"
    records = _records(
        Record(
            title="国务院关于印发《城市更新“十五五”规划》的通知",
            url="https://www.gov.cn/zhengce/content/2026-07/01/content_1.htm",
            date="2026-07-01",
            doc_number="国发〔2026〕12号",
            first_seen="2026-08-01T10:00:00",
            last_seen="2026-08-01T10:00:00",
        )
    )

    save_snapshot(path, records)
    loaded = load_snapshot(path)

    assert loaded == records


def test_load_missing_returns_empty(tmp_path):
    assert load_snapshot(tmp_path / "nope.json") == {}


def test_load_corrupt_json_returns_empty(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_snapshot(path) == {}


def test_merge_preserves_first_seen_and_updates_last_seen():
    old = _records(Record(title="旧标题", url="u1", first_seen="2026-07-01T00:00:00", last_seen="2026-07-01T00:00:00"))
    new = _records(Record(title="新标题", url="u1"), Record(title="新增", url="u2"))

    merged = merge_with_first_seen(old, new, "2026-08-10T12:00:00")

    # 老记录保留 first_seen，更新 last_seen
    assert merged["u1"].first_seen == "2026-07-01T00:00:00"
    assert merged["u1"].last_seen == "2026-08-10T12:00:00"
    assert merged["u1"].title == "新标题"
    # 新记录 first_seen = 本次运行时间
    assert merged["u2"].first_seen == "2026-08-10T12:00:00"
