# TDD 证据报告 — Streamlit 首个切片（政策查询 / 规模预警 / 合规校验）

> 日期：2026-08-11　｜　工作目录：`D:\HKU\SEM3\AgentCompetition1\Fork1`
> 范围：Streamlit 交互层 + 服务编排层，暴露三项能力，用现有爬取记录 + 测试样例规则库演示。

## 1. 用户旅程

- **J1 政策查询**：输入关键词 → 返回信源库原始记录（发文号/效力状态/官方链接），未命中如实提示「暂未收录」。
- **J2 规模预警**：录入片区上限 + 地块（面积/容积率/密度/绿地率）→ 两级风险 safe/warn/danger。
- **J3 合规校验**：录入片区属性 + 地块指标 → 逐块 Allowed/Not Allowed + 多层级从严冲突 + 总量预警，每条附条款溯源；测试样例规则显式横幅提示。

## 2. 架构

分层以保证可测试性：`webapp/services.py`（Streamlit 无关，加载数据→调既有引擎→归一化 dict）+ `webapp/app.py`（仅渲染）。判定逻辑全部落在 services/引擎层，由单测覆盖。

## 3. RED → GREEN

| 阶段 | 命令 | 结果 |
|------|------|------|
| RED（services 缺失）| `pytest tests/test_webapp_services.py` | `ModuleNotFoundError: webapp` |
| GREEN（services 实现）| 同上 | 10 passed |
| 视图冒烟（AppTest 进程内运行 app.py）| `pytest tests/test_webapp_app_smoke.py` | 3 passed |
| 全量 | `pytest`（默认 cp1252） | **198 passed** |

## 4. 测试规格

| # | 保证 | 用例 | 类型 | 结果 |
|---|------|------|------|------|
| 1 | 命中返回信源库原始记录（含 channel_name） | `test_webapp_services.py::TestSearchPolicies` | unit | PASS |
| 2 | 未命中 → 「暂未收录」，不虚构 | `::test_miss_returns_honest_message` | unit | PASS |
| 3 | 规模两级：地块 far 3.2→danger、片区 70/100→safe | `::TestAssessScale` | unit | PASS |
| 4 | 合规：容积率 3.6→not_allowed + 从严冲突(3.0/3.5) | `::test_not_allowed_and_conflict` | unit | PASS |
| 5 | 合规达标：2.8/0.35/0.25→allowed | `::test_allowed_plot` | unit | PASS |
| 6 | 总量超限预警 excess=10 | `::test_total_area_exceeded` | unit | PASS |
| 7 | 权威空库→unknown（不误判合规） | `::test_canonical_empty_yields_unknown` | unit | PASS |
| 8 | app 渲染无异常 + 三页签在位 | `test_webapp_app_smoke.py::test_app_renders_without_exception` | smoke | PASS |
| 9 | 政策查询贯通 services（“北京”→命中） | `::test_policy_query_wires_to_services` | smoke | PASS |

## 5. 已知问题（环境，非本切片代码）

`streamlit run webapp/app.py` 当前返回 **HTTP 500**：全局环境 **streamlit 1.61.0 与 starlette 1.4.0 不兼容**（gzip 中间件 `GZipResponder.__init__() missing 'thread_minimum_size'`），在脚本执行前的 web 服务层即报错。已用 `streamlit.testing.v1.AppTest`（进程内、不启 web 服务器）证明视图逻辑正确。修复属依赖治理：在隔离 venv 中固定兼容的 starlette 版本，或调整 streamlit 版本；不宜擅改全局站点包（本机多项目共用 `D:\Python`）。

## 6. 数据边界

合规校验默认载入 `data/rules/rules.sample.json`（4 条【测试样例，非真实条款】，来源链接指向真实爬取文档）；权威 `data/rules/rules.json` 保持空库，待明日真实规则数据。未接入大模型；未做任何货币化计算。
