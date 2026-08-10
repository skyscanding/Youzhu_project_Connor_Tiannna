"""Streamlit 视图冒烟测试：用 AppTest 在进程内运行 app.py（不启 web 服务器）。

只验证「渲染无异常 + 三个页签在位 + 政策查询能贯通到 services」；
业务逻辑由 test_webapp_services.py 覆盖，此处不重复。
"""
from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

_APP_PATH = str(Path(__file__).resolve().parent.parent / "webapp" / "app.py")


def _app():
    return AppTest.from_file(_APP_PATH, default_timeout=30)


def test_app_renders_without_exception():
    at = _app().run()
    assert not at.exception
    assert at.title[0].value.startswith("城市更新合规参谋")
    assert [t.label for t in at.tabs] == ["🔎 政策查询", "📐 规模预警", "🧮 合规校验"]


def test_policy_query_wires_to_services():
    at = _app().run()
    at.text_input(key="q_input").set_value("北京").run()
    assert not at.exception
    hit = any("命中" in (s.value or "") for s in at.success)
    assert hit  # 命中信源库记录 → 成功提示


def test_blank_query_shows_prompt():
    at = _app().run()
    # 默认无查询词、按钮未按下 → 不应报错
    assert not at.exception
