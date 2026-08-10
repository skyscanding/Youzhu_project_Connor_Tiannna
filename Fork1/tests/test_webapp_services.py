"""webapp.services 测试：Streamlit 无关的服务/编排层（政策查询 / 规模预警 / 合规校验）。

服务层只做「加载数据 + 调用既有引擎 + 归一化为可渲染 dict」，不含任何 UI；
Streamlit 视图层（app.py）仅渲染这些 dict，逻辑保证落在本测试。
"""
import pytest

from webapp import services

ATTRS = {"更新类型": "老旧小区改造"}


def _district(limit=100.0):
    return {"id": "d1", "name": "示范片区", "total_area_limit": limit, "attributes": ATTRS}


class TestSearchPolicies:
    def test_hit_returns_raw_records(self):
        r = services.search_policies("城市更新")
        assert r["count"] >= 3
        assert r["message"] is None
        first = r["results"][0]
        for key in ("title", "doc_number", "status", "official_url", "channel_id", "channel_name", "keywords"):
            assert key in first

    def test_beijing_hit_has_title_and_channel(self):
        r = services.search_policies("北京")
        assert r["count"] >= 1
        assert any("北京" in d["title"] for d in r["results"])
        # 命中记录附带渠道名（信源路由），非模型生成
        assert any(d["channel_name"] for d in r["results"])

    def test_miss_returns_honest_message(self):
        r = services.search_policies("abcxyz123")
        assert r["count"] == 0
        assert r["results"] == []
        assert "暂未收录" in r["message"]

    def test_blank_query_prompts(self):
        r = services.search_policies("   ")
        assert r["count"] == 0
        assert r["message"] is not None


class TestAssessScale:
    def test_plot_danger_and_district_safe(self):
        district = {"id": "d1", "name": "示范片区", "total_area_limit": 100.0}
        plots = [
            {"id": "p1", "area": 30.0, "far": 3.2},
            {"id": "p2", "area": 40.0, "far": 2.0},
        ]
        r = services.assess_scale(district, plots)
        assert r["summary"]["max_level"] == "danger"      # far 3.2 → danger
        assert r["summary"]["total"] == 3                 # 2 plots + 1 district
        district_w = next(w for w in r["warnings"] if w.get("district_id") == "d1")
        assert district_w["level"] == "safe"              # 70/100 未达 80%

    def test_thresholds_echoed(self):
        r = services.assess_scale({"id": "d", "name": "x", "total_area_limit": 10.0}, [])
        assert "thresholds" in r and "plot_far_warn" in r["thresholds"]


class TestCheckCompliance:
    def test_not_allowed_and_conflict(self):
        plots = [{"id": "p1", "district_id": "d1", "name": "A", "area": 30.0,
                  "indicators": {"容积率": 3.6, "绿地率": 0.28, "建筑密度": 0.25}}]
        r = services.check_compliance(_district(), plots, use_sample=True)
        assert r["is_sample"] is True
        assert r["rule_count"] == 4
        assert r["plots"][0]["status"] == "not_allowed"
        assert any(c["indicator"] == "容积率" for c in r["conflicts"])
        # 每条 check 带溯源依据（FR-11）
        assert all(chk["basis"] for chk in r["plots"][0]["checks"])

    def test_allowed_plot(self):
        plots = [{"id": "p1", "district_id": "d1", "name": "A", "area": 10.0,
                  "indicators": {"容积率": 2.8, "绿地率": 0.35, "建筑密度": 0.25}}]
        r = services.check_compliance(_district(), plots, use_sample=True)
        assert r["plots"][0]["status"] == "allowed"

    def test_total_area_exceeded(self):
        plots = [
            {"id": "p1", "district_id": "d1", "name": "A", "area": 60.0, "indicators": {}},
            {"id": "p2", "district_id": "d1", "name": "B", "area": 50.0, "indicators": {}},
        ]
        r = services.check_compliance(_district(limit=100.0), plots, use_sample=True)
        assert r["total"]["exceeded"] is True
        assert r["total"]["excess"] == pytest.approx(10.0)

    def test_canonical_empty_yields_unknown(self):
        plots = [{"id": "p1", "district_id": "d1", "name": "A", "area": 10.0,
                  "indicators": {"容积率": 2.8}}]
        r = services.check_compliance(_district(), plots, use_sample=False)
        assert r["is_sample"] is False
        assert r["rule_count"] == 0
        assert r["plots"][0]["status"] == "unknown"
