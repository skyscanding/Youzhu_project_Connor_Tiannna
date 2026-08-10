"""信源库存储测试：JSON 读写、损坏数据显式报错（信源库为人工维护数据）。"""
import pytest

from sourcelib.models import Channel, PolicyDocument
from sourcelib.store import Library, load_library, save_library


@pytest.fixture
def library():
    channel = Channel(
        id="govcn", org="国务院", site_name="中国政府网",
        url="https://www.gov.cn/zhengce/zhengceku/", level="national",
        pilot=False, description="政策库",
    )
    doc = PolicyDocument(
        id="n-155-guihua", title="《城市更新“十五五”规划》",
        doc_number="国发〔2026〕12号", effective_date="", status="待核验",
        official_url="", channel_id="govcn", keywords=("城市更新",), note="",
    )
    return Library(channels=[channel], documents=[doc])


def test_save_and_load_roundtrip(tmp_path, library):
    path = tmp_path / "sourcelib.json"
    save_library(path, library)

    loaded = load_library(path)

    assert loaded.channels == library.channels
    assert loaded.documents == library.documents


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_library(tmp_path / "nope.json")


def test_corrupt_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_library(path)


def test_load_rejects_invalid_record(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(
        '{"channels": [{"id": "", "org": "x"}], "documents": []}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_library(path)


def test_load_rejects_document_with_unknown_channel(tmp_path):
    path = tmp_path / "dangling.json"
    path.write_text(
        '{"channels": [], "documents": [{"id": "d1", "title": "t", "status": "待核验",'
        ' "channel_id": "ghost-channel", "keywords": []}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_library(path)


def test_duplicate_ids_rejected(tmp_path):
    channel = Channel(
        id="dup", org="机构A", site_name="站A",
        url="https://a.gov.cn", level="national", pilot=False, description="",
    )
    library = Library(channels=[channel, channel], documents=[])
    with pytest.raises(ValueError):
        save_library(tmp_path / "dup.json", library)


def test_duplicate_document_ids_rejected(tmp_path):
    doc = PolicyDocument(
        id="dup-doc", title="标题", status="待核验", keywords=(),
    )
    library = Library(channels=[], documents=[doc, doc])
    with pytest.raises(ValueError):
        save_library(tmp_path / "dup-doc.json", library)


def test_cli_entry_point_generates_library(tmp_path):
    """python -m sourcelib 生成信源库 JSON（真实子进程冒烟测试）。"""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "-m", "sourcelib", "--out-dir", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", cwd=root, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    library = load_library(tmp_path / "library.json")
    assert len(library.channels) >= 20
    assert len(library.documents) >= 15
