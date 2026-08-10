# 模块2 合规校验（片区—地块两级）TDD 证据报告

> 任务：PRD 模块二 合规校验——规则库、规则引擎、片区—地块校验
> 日期：2026-08-10 ｜ 运行环境：Windows 10 + Python 3.13.14 ｜ 位置：Youzhu/compliance/

## 1. 来源计划

无 `*.plan.md`；需求来源：
- PRD FR-06~FR-12（适用性判断、参数抽取留待 LLM 层、地块校验、总量校验、冲突从严、条款核验、双输入）
- PRD 11.1 验收：录入超出限值的容积率 → Not Allowed；多地块之和超片区上限 → 预警；同指标多层级不同值 → 显式提示差异
- PRD 核心设计理念：数值判定全部由程序与规则库完成（大模型不参与判断）
- 评审材料 5.1：规则引擎 自实现（Python）

## 2. 设计假设（已与用户确认方向的声明）

1. 契约边界：`data/rules/rules.json` 的 schema 是规则库的权威契约（contract-first），消费方 = 校验引擎 + 未来管理后台/报告层
2. 指标命名：`Rule.indicator` 用纯指标名（如"容积率"），约束方向由 `comparison`（le/ge/eq）+ `value` 表达——测试期间发现并修正了"容积率上限 vs 容积率"命名不一致问题
3. 规则数值由专业人员录入；本模块提供 schema/校验/空库初始化 CLI；测试 fixture 明确标注"测试样例，非真实条款"
4. 条款核验（FR-11）语义：规则必须携带 来源文件→条款号→原文片段，且文件 id 必须解析到信源库（跨模块契约测试）；数值与原文语义一致性由人工录入保证
5. 从严原则（FR-10）：le 类取小值，ge 类取大值；比较方向不一致 → 提示人工核对
6. 未录入指标 → "无法判断"（unknown），不误判合规（诚实拒答）

## 3. 任务报告

| 计划任务 | 执行摘要 | 验证命令 | 结果 |
|----------|----------|----------|------|
| 测试先行（RED） | 3 个测试模块（models/engine/store），compliance 包不存在导致收集失败 | `pytest tests/test_compliance_*` → 3 errors | RED ✓ |
| 实现（GREEN） | 实现 models（Rule/District/Plot+校验）、engine（适用性/地块/总量/冲突）、store（JSON+契约）、__main__（--init/--validate） | `pytest tests/test_compliance_*` | GREEN ✓ |
| 测试自身缺陷修正（3 轮） | ① `value=None` 合法用例断言写反；② tuple vs list 比较；③ `_plot` 的 `or` 回退吞掉空字典导致"缺失指标"用例拿到默认值；④ 指标命名统一 | 逐轮 `pytest` | GREEN ✓ |
| 便利属性补充 | `IndicatorCheck.rule_value` 属性（报告层直接取限值） | 测试驱动 | PASS |
| 覆盖补强 | District/Plot 序列化往返、load 侧契约拦截 | `pytest --cov` | PASS |
| 契约工具 | `python -m compliance --init` 初始化空规则库（data/rules/rules.json） | 手动演示 | PASS |
| 验收演示 | FR-08 超出限值 → not_allowed（带条款依据）；FR-10 冲突 → 从严 3.0；FR-09 总量 | 手动演示 | PASS |

### 最终验证命令与输出

```
python -m pytest --cov=crawler --cov=sourcelib --cov=compliance --cov-report=term -q
→ 139 passed
→ TOTAL 641 stmts, 90% coverage（compliance/engine.py 100%，models.py 100%）
```

PRD 验收场景实测（测试样例规则）：

```
适用规则: ['r-natl', 'r-city']          # FR-06
冲突: [('容积率', (3.0, 4.0), 3.0)]     # FR-10 从严取小值
地块A: not_allowed | 依据: [n-tudi-zhidao-2023] 测试条款-国：【样例】容积率≤4.0   # FR-08 + FR-11
总量: TotalAreaResult(total=30.0, limit=100.0, exceeded=False, excess=0.0)      # FR-09
```

## 4. 测试规格（人读保证）

| # | 保证内容 | 测试 | 类型 | 结果 | 证据 |
|---|----------|------|------|------|------|
| 1 | 规则必填字段/层级/比较方向/负值/未标定须注明/适用条件校验 | `test_compliance_models.py` | 单元 | PASS | `pytest tests/test_compliance_models.py` |
| 2 | 片区/地块校验（负面积、负指标、必填字段） | 同上 | 单元 | PASS | 同上 |
| 3 | District/Plot 序列化往返（录入层数据契约） | `test_district_and_plot_serialization_roundtrip` | 单元 | PASS | 同上 |
| 4 | FR-06 适用性：条件子集匹配/不匹配/空条件全适用 | `test_compliance_engine.py` | 单元 | PASS | `pytest tests/test_compliance_engine.py` |
| 5 | **FR-08 验收：超出限值 → not_allowed，带依据条款** | `test_plot_exceeding_limit_is_not_allowed` | 单元 | PASS | 同上 |
| 6 | le/ge/eq 三种比较方向；任一违规即失败 | 同上 | 单元 | PASS | 同上 |
| 7 | 缺失指标 → unknown + missing 列表（诚实拒答） | `test_missing_indicator_marks_unknown` | 单元 | PASS | 同上 |
| 8 | 未标定规则（value=None）被跳过，不误判 | `test_unstipulated_value_rule_is_skipped` | 单元 | PASS | 同上 |
| 9 | FR-09 总量：未超/等于上限/超出含超额量/空地块 | `test_total_area_*` | 单元 | PASS | 同上 |
| 10 | FR-10 冲突：同指标多值检测、le 从严取小、ge 从严取大、方向不一致提示人工核对、仅适用规则参与 | `test_conflict_*` | 单元 | PASS | 同上 |
| 11 | 规则库 JSON 往返；缺失/损坏/重复 id 显式报错 | `test_compliance_store.py` | 单元 | PASS | `pytest tests/test_compliance_store.py` |
| 12 | **FR-11 契约：规则来源文件必须在信源库中（save 与 load 双侧拦截）** | `test_rule_with_unknown_source_doc_rejected` / `test_load_rejects_rule_with_unknown_doc` | 集成 | PASS | 同上 |
| 13 | `python -m compliance --init/--validate` 子进程冒烟 | `test_cli_init_and_validate` | 集成 | PASS | 同上 |

## 5. 覆盖率与已知缺口

```
compliance/engine.py  100%  ｜  compliance/models.py  100%  ｜  compliance/store.py  97%
compliance/__main__.py 0%（入口 shim，行为由子进程测试验证）
TOTAL 90%（目标 ≥80%）
```

**有意的缺口**：
- FR-07/FR-12 的大模型参数抽取与回填确认不在本模块（需 LLM API，属编排层）；`Plot.indicators` 的 dict 结构即为表单/LLM 回填的契约
- 规则库初始为空（`data/rules/rules.json`，schema v1.0），数值与条款由专业人员录入——本模块未编造任何真实政策数值
- 条款"数值 vs 原文"的语义一致性依赖人工录入复核（程序无法做语义核对）；程序保证的是结构完整性与来源可解析

## 6. 数据诚实性声明

- 测试 fixture 条款全部标注"【测试样例，非真实条款】"
- 种子规则库为空；`--init` 输出明确提示"待专业人员录入"
- 规则引用信源库真实文档 id（如 bj-jianzhu-guimo），但数值不代表任何真实政策规定

## 7. 合并证据

非 git 仓库，无 checkpoint commit；本报告为唯一证据载体。
