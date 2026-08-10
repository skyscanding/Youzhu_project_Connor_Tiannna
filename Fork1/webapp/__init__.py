"""webapp：城市更新合规参谋 Agent 的交互层（Streamlit）+ 服务编排层。

- services.py：Streamlit 无关的编排（加载数据 → 调用既有引擎 → 归一化为 dict），可独立测试。
- app.py：Streamlit 视图，仅渲染 services 返回的 dict。
"""
