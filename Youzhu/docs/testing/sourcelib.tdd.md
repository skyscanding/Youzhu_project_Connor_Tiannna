# 信源库结构化 TDD 证据报告

> 任务：PRD 数据层「信源库」——渠道表 + 政策文档记录的结构化与检索
> 日期：2026-08-10 ｜ 运行环境：Windows 10 + Python 3.13.14

## 1. 来源计划

无 `*.plan.md`；需求来源：
- PRD FR-01/FR-03/FR-04（检索返回原始记录、未命中拒答、效力状态标签）
- PRD 11.1 验收：输入"北京容积率上限"应返回北京相关政策文件信息
- PRD 11.3 交付物：政策信源清单不少于 20 份
- 《城市更新政策官方网址.md》：全部数据来源（人工核实）

## 2. 用户旅程

| # | 旅程 |
|---|------|
| UJ-1 | 作为用户，我想用自然语言关键词检索政策文件，系统返回库中原始记录（文件名/发文号/状态），不生成内容 |
| UJ-2 | 作为用户，我想查询不存在的政策时得到"暂未收录"（空结果由界面层转文案） |
| UJ-3 | 作为维护者，我希望信源库数据损坏/非法时显式报错，而不是静默吞掉（区别于爬虫快照） |
| UJ-4 | 作为维护者，我希望信源库与爬虫信源配置保持一致，防止两处定义漂移 |

## 3. 任务报告

| 计划任务 | 执行摘要 | 验证命令 | 结果 |
|----------|----------|----------|------|
| 测试先行（RED） | 4 个测试模块（models/store/search/seed），sourcelib 包不存在导致收集失败 | `pytest tests/test_sourcelib_*` → 4 errors | RED ✓ |
| 实现（GREEN） | 实现 models（Channel/PolicyDocument/校验）、store（Library 读写+全库校验）、search（AND 检索）、seed（26 渠道+19 文档） | `pytest -q` | GREEN ✓ |
| Library 类型一致性修复 | frozen dataclass 用 list 构造时 `list != tuple` 导致往返测试失败；`__post_init__` 统一为 tuple | `pytest tests/test_sourcelib_store.py` | GREEN ✓ |
| PRD 验收盲区（回归测试价值案例） | 按验收标准"北京容积率上限"（无空格）测试发现单 token 无法命中；实现库内关键词子串切分（切出的关键词全部要求命中，残留片段不参与） | 先 RED（2 failed）→ 实现 → GREEN | GREEN ✓ |
| 覆盖补强 | 补 文档 id 重复分支、`python -m sourcelib` 子进程冒烟 | `pytest --cov=crawler --cov=sourcelib` | PASS |
| 产物生成 | `python -m sourcelib` 生成 `data/sourcelib/library.json`（26 渠道+19 文档），PRD 验收查询实测命中 2 条北京容积率政策 | 手动演示 | PASS |

### 最终验证命令与输出

```
python -m pytest --cov=crawler --cov=sourcelib --cov-report=term -q
→ 86 passed
→ TOTAL 387 stmts, 93% coverage
```

PRD 11.1 验收实测：

```
查询[北京容积率上限] → 关于印发《北京市城市更新政策激励工具箱（1.0版）》的通知；
                      深化建筑规模管理激励城市更新的管理规定
查询[国发〔2026〕12号] → 《城市更新“十五五”规划》（国发〔2026〕12号）
查询[不存在的政策] → 暂未收录
```

## 4. 测试规格（人读保证）

| # | 保证内容 | 测试 | 类型 | 结果 | 证据 |
|---|----------|------|------|------|------|
| 1 | 渠道必填字段/URL/层级校验；合法 http/https 通过 | `test_sourcelib_models.py` | 单元 | PASS | `pytest tests/test_sourcelib_models.py` |
| 2 | 文档必填字段/状态枚举/日期格式/链接校验；未知字段允许留空（不虚构） | 同上 | 单元 | PASS | 同上 |
| 3 | 效力状态集合 = {现行有效,已修改,已废止,待核验}（FR-04） | 同上 | 单元 | PASS | 同上 |
| 4 | 存储往返一致；缺失文件/损坏 JSON/非法记录/悬空渠道引用/重复 id 全部显式报错（UJ-3） | `test_sourcelib_store.py` | 单元 | PASS | `pytest tests/test_sourcelib_store.py` |
| 5 | 空查询→空；单词命中标题/关键词/发文号；多词 AND（UJ-2） | `test_sourcelib_search.py` | 单元 | PASS | `pytest tests/test_sourcelib_search.py` |
| 6 | **PRD 验收：无空格查询"北京容积率上限"命中北京容积率政策**（回归：单 token 切分） | `test_prd_acceptance_query_without_spaces` | 单元 | PASS | 同上 |
| 7 | 切不出的词条保持 AND；渠道名扩展匹配范围 | 同上 | 单元 | PASS | 同上 |
| 8 | 种子数据：26 渠道/19 文档全校验通过、引用完整、关键词非空（UJ-1） | `test_sourcelib_seed.py` | 集成 | PASS | `pytest tests/test_sourcelib_seed.py` |
| 9 | **信源库与 crawler/sources.py 的 id/URL/层级完全一致**（UJ-4，防两处漂移） | `test_channels_align_with_crawler_sources` | 集成 | PASS | 同上 |
| 10 | 不虚构红线：发文号必须符合〔〕号格式否则留空；日期必须 ISO 否则留空 | `test_no_invented_doc_numbers` / `test_dates_are_iso_or_empty` | 集成 | PASS | 同上 |
| 11 | 交付物数量：渠道 ≥20、文档 ≥15（PRD 11.3） | `test_channel_count_meets_deliverable` | 集成 | PASS | 同上 |
| 12 | `python -m sourcelib` 子进程生成可加载的信源库 JSON | `test_cli_entry_point_generates_library` | 集成 | PASS | `pytest tests/test_sourcelib_store.py` |

## 5. 覆盖率与已知缺口

```
sourcelib: models 100% / store 100% / search 100% / seed 100%
crawler:   diff 100% / fetch 100% / snapshot 100% / sources 100% / extract 98% / cli 99%
sourcelib\__main__.py 0%（入口 shim，行为由子进程冒烟测试验证，pytest-cov 不追踪子进程）
crawler\__main__.py   0%（同上）
TOTAL 93%（目标 ≥80%）
```

**有意的缺口**：两个 `__main__.py` 入口 shim（共 26 行）不在行覆盖内，其行为均经真实子进程测试验证。检索的"关键词子串切分"为轻量方案（无 jieba 依赖），长词优先、切出词全命中；`_library_keywords` 中渠道名参与切分词典，种子数据未启用渠道名扩展的测试场景已覆盖逻辑。

## 6. 数据诚实性声明

种子数据（`sourcelib/seed.py`）只收录《城市更新政策官方网址.md》**明确点名**的文件：
- 19 条文档中 4 条带发文号（国发〔2026〕12号 / 建办科函〔2021〕443号 / 自然资发〔2025〕226号 / 财办建〔2026〕14号），全部来自 MD 原文
- 1 条带日期（工具箱 1.0 版，2026-01-01，MD 原文标注）
- 其余发文号/日期/链接未知的字段全部留空，note 标注"待人工核验"——由 `test_no_invented_doc_numbers` 等测试强制约束

## 7. 合并证据

非 git 仓库，无 checkpoint commit；本报告为唯一证据载体。
