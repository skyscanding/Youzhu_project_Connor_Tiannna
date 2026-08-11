"""Streamlit 视图层：城市更新合规参谋 Agent 数据层演示。

运行：streamlit run webapp/app.py
仅渲染 webapp.services 返回的 dict；逻辑与判定全部在 services / 引擎层（已被单测覆盖）。
"""
import sys
from pathlib import Path

# streamlit run 会把脚本所在目录(webapp/)加入 sys.path，需补入项目根以导入 sourcelib 等包
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from webapp import services

st.set_page_config(page_title="城市更新合规参谋 Agent", page_icon="🏙️", layout="wide")


def _inject_claude_theme() -> None:
    """注入 Claude 风格样式：暖纸背景、珊瑚强调色、衬线标题、圆角卡片。"""
    st.markdown(
        """
        <style>
        /* 纯系统字体栈：不拉取外网字体，避免本机经代理访问 googleapis 阻塞首屏渲染 */
        .stApp { background:#FAF9F5; }
        .block-container { max-width:1080px; padding-top:2.4rem; }
        html, body, [class*="css"], .stMarkdown, input, textarea, button {
            font-family:-apple-system,"Segoe UI","Helvetica Neue",Arial,sans-serif;
        }
        h1, h2, h3 { font-family:Georgia,"Times New Roman","Songti SC",serif; color:#1F1E1D; letter-spacing:-0.01em; }
        h1 { font-weight:600; }
        h1::before { content:"✳ "; color:#D97757; font-family:sans-serif; }
        /* 主按钮：珊瑚 */
        .stButton button, [data-testid="stBaseButton-primary"] {
            background:#D97757 !important; color:#fff !important; border:none !important;
            border-radius:10px !important; padding:0.5rem 1.15rem !important; font-weight:600 !important;
            box-shadow:0 1px 2px rgba(0,0,0,0.06); transition:background .15s ease;
        }
        .stButton button:hover, [data-testid="stBaseButton-primary"]:hover { background:#C15F3C !important; }
        /* 圆角卡片 */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border:1px solid #E7E3D8 !important; border-radius:14px !important;
            background:#FFFFFF; box-shadow:0 1px 3px rgba(30,30,29,0.04);
        }
        [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
            border-radius:10px; border:1px solid #E2DED2; background:#FFFDF8;
        }
        /* 页签强调色 */
        .stTabs [data-baseweb="tab-list"] { gap:0.4rem; border-bottom:1px solid #EBE7DC; }
        .stTabs [aria-selected="true"] { color:#C15F3C !important; }
        .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { background:#D97757 !important; }
        [data-testid="stAlert"] { border-radius:12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_claude_theme()

LEVEL_UI = {"safe": ("✅ 安全", st.success), "warn": ("⚠️ 警示", st.warning), "danger": ("⛔ 危险", st.error)}
STATUS_UI = {"allowed": ("✅ 合规", st.success), "not_allowed": ("⛔ 不合规", st.error), "unknown": ("❓ 无法判断", st.info)}
_OP = {"le": "≤", "ge": "≥", "eq": "="}


def _num_or_none(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clean_scale_plot(row: dict) -> dict:
    plot = {"id": str(row.get("id")), "area": _num_or_none(row.get("area")) or 0.0}
    for key in ("far", "density", "green_rate"):
        val = _num_or_none(row.get(key))
        if val is not None:
            plot[key] = val
    return plot


def _clean_comp_plot(row: dict) -> dict:
    indicators = {}
    for key in ("容积率", "绿地率", "建筑密度"):
        val = _num_or_none(row.get(key))
        if val is not None:
            indicators[key] = val
    return {
        "id": str(row.get("id")),
        "name": row.get("name") or "",
        "area": _num_or_none(row.get("area")) or 0.0,
        "indicators": indicators,
    }


st.title("城市更新合规参谋 Agent · 数据层演示")
st.caption(
    "规则由人工标定、判定全部由程序完成；大模型（本演示未接入）仅做参数抽取与报告转述，不参与任何数值判断。"
)

tab_query, tab_scale, tab_comp = st.tabs(["🔎 政策查询", "📐 规模预警", "🧮 合规校验"])

# ── 政策查询 ─────────────────────────────────────────────────────────────────
with tab_query:
    st.subheader("政策文件查询")
    st.caption("只返回信源库原始记录（发文号 / 效力状态 / 官方链接），未命中如实提示，不生成幻觉答案。")
    query = st.text_input("关键词查询", placeholder="如：北京 容积率、城市更新、老旧小区改造", key="q_input")
    if st.button("查询", key="q_btn", type="primary") or query:
        try:
            res = services.search_policies(query)
        except Exception as exc:  # 信源库损坏等
            st.error(f"检索失败：{exc}")
        else:
            if res["message"]:
                st.info(res["message"])
            if res["count"]:
                st.success(f"命中 {res['count']} 条记录（信源库原始记录，未经模型改写）")
                for doc in res["results"]:
                    with st.container(border=True):
                        st.markdown(f"**{doc['title']}**　`{doc['status']}`")
                        st.caption(
                            f"发文号：{doc['doc_number'] or '待核验'}　｜　"
                            f"生效：{doc['effective_date'] or '待核验'}　｜　"
                            f"渠道：{doc['channel_name'] or '—'}"
                        )
                        if doc["official_url"]:
                            st.markdown(f"[官方原文链接]({doc['official_url']})")
                        else:
                            st.caption("官方链接：待人工核验")
                        if doc["keywords"]:
                            st.caption("关键词：" + "、".join(doc["keywords"]))

# ── 规模预警 ─────────────────────────────────────────────────────────────────
with tab_scale:
    st.subheader("规模预警（片区总量 + 地块强度）")
    st.caption("只到规模为止，不涉及任何货币化计算（造价/售价/租金）。面积单位：公顷。")
    col1, col2 = st.columns(2)
    d_name = col1.text_input("片区名称", "示范片区", key="s_name")
    d_limit = col2.number_input("片区总规模上限（公顷）", min_value=0.0, value=100.0, step=5.0, key="s_limit")
    st.markdown("**地块列表**（容积率 far / 建筑密度 density / 绿地率 green_rate 可留空表示不评估该项）")
    scale_seed = [
        {"id": "P1", "area": 30.0, "far": 2.0, "density": 0.20, "green_rate": 0.35},
        {"id": "P2", "area": 45.0, "far": 2.7, "density": 0.22, "green_rate": 0.28},
    ]
    scale_rows = st.data_editor(scale_seed, num_rows="dynamic", key="s_plots", width="stretch")
    if st.button("评估规模", key="s_btn", type="primary"):
        district = {"id": "d1", "name": d_name, "total_area_limit": d_limit}
        plots = [_clean_scale_plot(r) for r in scale_rows if r.get("id")]
        result = services.assess_scale(district, plots)
        summary = result["summary"]
        label, render = LEVEL_UI[summary["max_level"]]
        render(
            f"最高风险等级：{label}　（安全 {summary['safe']} / 警示 {summary['warn']} / 危险 {summary['danger']}）"
        )
        for warn in result["warnings"]:
            _, wrender = LEVEL_UI[warn["level"]]
            tag = f"片区总量 · {warn['district_name']}" if warn.get("district_id") else f"地块 {warn['plot_id']}"
            wrender(f"{tag}：{warn['reason']}")

# ── 合规校验 ─────────────────────────────────────────────────────────────────
with tab_comp:
    st.subheader("合规校验（片区—地块两级）")
    use_sample = st.toggle("使用测试样例规则库（rules.sample.json）", value=True, key="c_sample")
    if use_sample:
        st.warning("当前为 **测试样例规则**（clause_text 标注“非真实条款”，仅供演示）；真实规则库待专业人员录入。")
    else:
        st.info("使用权威规则库 data/rules/rules.json（当前为空 → 所有地块判定为“无法判断”，直至录入真实规则）。")

    col1, col2, col3 = st.columns(3)
    upd_type = col1.selectbox("更新类型", ["老旧小区改造", "其他"], key="c_type")
    impl = col2.text_input("实施方式（可选）", "", key="c_impl")
    limit = col3.number_input("片区总规模上限（公顷）", min_value=0.0, value=100.0, step=5.0, key="c_limit")

    st.markdown("**地块指标**（容积率 / 绿地率 / 建筑密度；留空即不校验该指标）")
    comp_seed = [
        {"id": "P1", "name": "地块A", "area": 30.0, "容积率": 3.6, "绿地率": 0.28, "建筑密度": 0.25},
        {"id": "P2", "name": "地块B", "area": 25.0, "容积率": 2.8, "绿地率": 0.35, "建筑密度": 0.22},
    ]
    comp_rows = st.data_editor(comp_seed, num_rows="dynamic", key="c_plots", width="stretch")

    if st.button("校验合规", key="c_btn", type="primary"):
        attributes = {"更新类型": upd_type}
        if impl.strip():
            attributes["实施方式"] = impl.strip()
        district = {"id": "d1", "name": "示范片区", "total_area_limit": limit, "attributes": attributes}
        plots = [_clean_comp_plot(r) for r in comp_rows if r.get("id")]
        try:
            result = services.check_compliance(district, plots, use_sample=use_sample)
        except Exception as exc:  # 规则库/信源库契约错误
            st.error(f"校验失败：{exc}")
        else:
            src = "测试样例" if result["is_sample"] else "权威库"
            st.caption(f"载入规则：{result['rule_count']} 条（{src}）；适用条件：{result['attributes']}")

            for plot in result["plots"]:
                label, render = STATUS_UI[plot["status"]]
                render(f"{plot.get('name') or plot['plot_id']}　→　{label}")
                for chk in plot["checks"]:
                    mark = "✅" if chk["allowed"] else "⛔"
                    op = _OP.get(chk["comparison"], chk["comparison"])
                    st.write(f"{mark} {chk['indicator']}：{chk['plot_value']}（限值 {op} {chk['rule_value']}）")
                    with st.expander(f"依据条款 · {chk['indicator']}"):
                        st.caption(chk["basis"])
                if plot["missing"]:
                    st.caption("有适用规则但未录入、无法判断的指标：" + "、".join(plot["missing"]))

            if result["conflicts"]:
                st.markdown("**多层级冲突（从严建议）**")
                for conf in result["conflicts"]:
                    st.warning(f"{conf['indicator']}：出现取值 {tuple(conf['values'])} → {conf['note']}")

            total = result["total"]
            if total["exceeded"]:
                st.error(
                    f"片区总量预警：各期合计 {total['total']} 公顷，超上限 {total['limit']}，超出 {total['excess']}"
                )
            else:
                st.success(f"片区总量：{total['total']} / 上限 {total['limit']} 公顷（未超）")
