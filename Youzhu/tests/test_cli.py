"""CLI 集成测试：mock 抓取函数，验证 抓取→快照→对比→报告 全流程。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from crawler import fetch
from crawler.cli import main

NOW = "2026-08-10T12:00:00"
ROOT = Path(__file__).resolve().parent.parent


def _ok_html(title="城市更新新政策通知", date="2026-08-01"):
    return (
        "<ul><li><a href='/a/1.htm'>"
        + title
        + "</a><span>"
        + date
        + "</span></li></ul>"
    )


def _fake_fetch(session, url, **kwargs):
    if "scio.gov.cn" in url:
        raise fetch.FetchError(f"GET {url} failed: network unreachable")
    return _ok_html()


@pytest.fixture
def cli_args(tmp_path):
    return ["--data-dir", str(tmp_path), "--politeness-delay", "0"]


def test_first_run_reports_all_added_and_writes_snapshot(tmp_path, cli_args, monkeypatch):
    monkeypatch.setattr("crawler.cli.fetch.fetch_html", _fake_fetch)

    report = main([*cli_args, "--source", "govcn"], now=NOW)

    source = report["sources"][0]
    assert source["status"] == "ok"
    assert source["records_found"] == 1
    assert len(source["changes"]["added"]) == 1
    assert source["changes"]["added"][0]["title"] == "城市更新新政策通知"

    snapshot = json.loads((tmp_path / "snapshot" / "govcn.json").read_text(encoding="utf-8"))
    assert snapshot[0]["first_seen"] == NOW

    report_file = tmp_path / "reports" / f"变更清单-{NOW.replace('T', '-').replace(':', '-')}.json"
    assert report_file.exists()
    assert json.loads(report_file.read_text(encoding="utf-8"))["run_at"] == NOW


def test_second_run_with_no_change_reports_empty(tmp_path, cli_args, monkeypatch):
    monkeypatch.setattr("crawler.cli.fetch.fetch_html", _fake_fetch)

    main([*cli_args, "--source", "govcn"], now=NOW)
    report = main([*cli_args, "--source", "govcn"], now="2026-08-11T12:00:00")

    source = report["sources"][0]
    assert source["changes"] == {"added": [], "updated": [], "vanished": []}


def test_source_failure_does_not_affect_others(tmp_path, cli_args, monkeypatch):
    monkeypatch.setattr("crawler.cli.fetch.fetch_html", _fake_fetch)

    report = main([*cli_args, "--source", "govcn", "--source", "scio"], now=NOW)

    by_id = {s["id"]: s for s in report["sources"]}
    assert by_id["govcn"]["status"] == "ok"
    assert by_id["scio"]["status"] == "error"
    assert "network unreachable" in by_id["scio"]["error"]

    summary = report["summary"]
    assert summary["sources_total"] == 2
    assert summary["sources_ok"] == 1
    assert summary["sources_failed"] == 1
    # 失败信源不写快照，但成功信源正常写
    assert (tmp_path / "snapshot" / "govcn.json").exists()
    assert not (tmp_path / "snapshot" / "scio.json").exists()


def test_second_run_reports_update_and_vanished(tmp_path, cli_args, monkeypatch):
    """第二次运行：一条更新（标题变化）、一条消失（不在列表中）、一条新增。"""
    calls = {"n": 0}

    def fake_fetch(session, url, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return (
                "<ul>"
                "<li><a href='/a/1.htm'>城市更新政策一</a><span>2026-08-01</span></li>"
                "<li><a href='/a/2.htm'>城市更新政策二</a><span>2026-08-01</span></li>"
                "</ul>"
            )
        return (
            "<ul>"
            "<li><a href='/a/1.htm'>城市更新政策一（修订版）</a><span>2026-08-01</span></li>"
            "<li><a href='/a/3.htm'>城市更新政策三</a><span>2026-08-02</span></li>"
            "</ul>"
        )

    monkeypatch.setattr("crawler.cli.fetch.fetch_html", fake_fetch)
    main([*cli_args, "--source", "govcn"], now=NOW)
    report = main([*cli_args, "--source", "govcn"], now="2026-08-11T12:00:00")

    changes = report["sources"][0]["changes"]
    assert [r["title"] for r in changes["added"]] == ["城市更新政策三"]
    assert len(changes["updated"]) == 1
    assert changes["updated"][0]["old"]["title"] == "城市更新政策一"
    assert changes["updated"][0]["new"]["title"] == "城市更新政策一（修订版）"
    assert [r["title"] for r in changes["vanished"]] == ["城市更新政策二"]


def test_proxy_is_applied_to_session(tmp_path, cli_args, monkeypatch):
    """--proxy 指定的代理地址应配置到 HTTP 会话上（本机访问 gov.cn 常需本地代理）。"""
    seen = {}

    def fake_fetch(session, url, **kwargs):
        seen["proxies"] = dict(session.proxies)
        return _ok_html()

    monkeypatch.setattr("crawler.cli.fetch.fetch_html", fake_fetch)
    main([*cli_args, "--source", "govcn", "--proxy", "http://127.0.0.1:7897"], now=NOW)

    assert seen["proxies"] == {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}


def test_list_sources(capsys):
    report = main(["--list-sources"])
    assert report == {}
    out = capsys.readouterr().out
    assert "govcn" in out and "bj-yq" in out
    # 90 个信源 = MD 85 条表格信源 + 5 个正文内嵌网址
    # （住建委城市更新专栏、南昌专栏、广州专栏、发改委在线平台、财政部办公厅；
    #   政策库 URL 与 govcn 主 URL 相同，不重复计）
    assert len([line for line in out.splitlines() if line]) == 90


def test_unknown_source_returns_none(capsys):
    assert main(["--source", "bogus"]) is None
    assert "未知信源 ID" in capsys.readouterr().err


def test_cli_entry_point_list_sources():
    """python -m crawler 入口冒烟测试（真实子进程）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "crawler", "--list-sources"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    assert proc.returncode == 0
    assert "govcn" in proc.stdout
    assert "bj-yq" in proc.stdout
