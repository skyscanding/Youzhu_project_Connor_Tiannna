"""变更检测测试：新增 / 更新 / 消失 / 无变化。"""
from crawler.diff import diff_records
from crawler.extract import Record


def _rec(url: str, title: str = "政策标题", date: str = "2026-01-01", doc_number: str = ""):
    return Record(title=title, url=url, date=date, doc_number=doc_number)


def _by_identity(*records):
    return {r.identity: r for r in records}


def test_first_run_all_added():
    new = _by_identity(_rec("u1"), _rec("u2"))
    result = diff_records({}, new)

    assert [r.url for r in result.added] == ["u1", "u2"]
    assert not result.updated and not result.vanished


def test_no_change():
    old = _by_identity(_rec("u1"))
    result = diff_records(old, old)

    assert not result.added and not result.updated and not result.vanished


def test_updated_same_url_changed_title():
    old = _by_identity(_rec("u1", title="旧标题"))
    new = _by_identity(_rec("u1", title="新标题（征求意见稿）"))

    result = diff_records(old, new)

    assert len(result.updated) == 1
    old_rec, new_rec = result.updated[0]
    assert old_rec.title == "旧标题"
    assert new_rec.title == "新标题（征求意见稿）"


def test_updated_same_url_changed_date():
    old = _by_identity(_rec("u1", date="2026-01-01"))
    new = _by_identity(_rec("u1", date="2026-02-01"))

    result = diff_records(old, new)

    assert len(result.updated) == 1


def test_vanished():
    old = _by_identity(_rec("u1"), _rec("u2"))
    new = _by_identity(_rec("u1"))

    result = diff_records(old, new)

    assert [r.url for r in result.vanished] == ["u2"]


def test_mixed_scenario():
    old = _by_identity(_rec("u1", title="不变"), _rec("u2", title="被更新"), _rec("u3", title="消失"))
    new = _by_identity(_rec("u1", title="不变"), _rec("u2", title="新标题"), _rec("u4", title="新增"))

    result = diff_records(old, new)

    assert [r.url for r in result.added] == ["u4"]
    assert [r.url for r in result.vanished] == ["u3"]
    assert [new_rec.url for _, new_rec in result.updated] == ["u2"]
