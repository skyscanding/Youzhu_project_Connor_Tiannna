# TDD 证据报告 — scale 模块修复 + CLI UTF-8 加固

> 日期：2026-08-11　｜　工作目录：`D:\HKU\SEM3\AgentCompetition1\Fork1`
> 范围：修复 scale 模块 2 个失败用例 + 使 3 个 CLI 子进程用例在 cp1252 控制台下通过。
> 未纳入本次：规则库数据录入（明日部分可用）、API 接口（明日开发）。

## 1. 来源

本轮无 `*.plan.md`；任务与验收口径由用户在会话中给出，journey 于本次派生。

## 2. 用户旅程（派生）

- **J1**：作为规划人员，我录入地块绿地率，系统按“低于 danger 阈值→DANGER、低于 min→WARN、达标→SAFE”正确分级。
- **J2**：作为工具使用者，我信任 `normalize_area` 的面积换算与真实物理换算一致（1 平方千米 = 100 公顷）。
- **J3**：作为 Windows 中文环境用户，我在默认代码页（cp1252/cp936）控制台运行 `python -m crawler/sourcelib/compliance` 时，中文输出不崩溃。

## 3. 任务报告（RED → GREEN）

### 任务 A：绿地率 danger 阈值被错误接线（生产缺陷）

- 现象：`assess_plot_intensity(green_rate=0.25)` 返回 `DANGER`，应为 `WARN`。
- 根因：`scale/warning.py` 绿地率分级把 `plot_green_rate_min` 同时传入 warn 与 danger 两个参数，`plot_green_rate_danger`(0.20) 从未生效。
- RED：`tests/test_scale_warning.py::test_green_rate_warning` 失败（0.25 被判 DANGER）。
- 修复：danger 位改为 `thresholds.plot_green_rate_danger`。
- 追加回归：新增 `test_green_rate_danger`（0.15 → DANGER）锁定修复。
- GREEN：见 §4。

### 任务 B：平方千米换算断言与物理换算不符（测试缺陷）

- 现象：`test_square_kilometer` 断言 `normalize_area(0.01, "平方千米")==10.0`。
- 判定：代码系数 100 正确（1 km²=100 公顷，故 0.01 km²=1 公顷）。**测试期望值错误**，非代码错误。
- 修复：更正测试为 `0.1 平方千米 == 10.0` 并补 `0.01 平方千米 == 1.0` 防呆断言；生产代码未改。
- GREEN：见 §4。

### 任务 D：绿地率下限边界口径（0.30 应为合规）

- 用户确认：绿地率恰好达到下限 0.30 属**合规**（“不得低于该值”→ 等于视为达标）。
- 修复：`_level_for_value` 下限型（`higher_is_worse=False`，仅绿地率使用）分支由 `<=` 改为 `<`；上限型（容积率/密度/总量占比）保持 `>=`（从严不变）。
- 结果：0.30 → SAFE、0.25 → WARN、0.15 → DANGER。
- 追加回归：`test_green_rate_safe_at_min`（0.30 → SAFE）。

### 任务 C：CLI 在 cp1252 控制台输出中文崩溃（生产加固）

- 现象：`python -m crawler/sourcelib/compliance` 子进程 `print(中文)` 触发 `UnicodeEncodeError`（stdout=cp1252），returncode≠0。
- 修复（生产）：在 3 个入口 `__main__`（仅子进程执行路径，避免影响 in-process `capsys` 用例）调用 `_force_utf8_stdio()`，将 stdout/stderr `reconfigure(encoding="utf-8")`。
- 修复（测试）：3 个子进程用例的 `subprocess.run` 增加 `encoding="utf-8"`，parent 侧按 UTF-8 解码，不再依赖控制台 locale。
- 追加回归：`test_cli_entry_point_survives_non_utf8_console` 用 `PYTHONIOENCODING=cp1252, PYTHONUTF8=0` 强制复现非 UTF-8 控制台，使该保证在任意机器上确定成立。
- GREEN：见 §4。

## 4. 测试规格（人类可读保证）

| # | 保证内容 | 用例 | 类型 | 结果 | 证据命令 |
|---|----------|------|------|------|----------|
| 1 | 绿地率 0.25 → WARN（min 与 danger 之间） | `test_scale_warning.py::test_green_rate_warning` | unit | PASS | `python -m pytest tests/test_scale_warning.py` |
| 2 | 绿地率 0.15 → DANGER（低于 danger 0.20） | `test_scale_warning.py::test_green_rate_danger` | unit | PASS | 同上 |
| 3 | 0.1 平方千米=10 公顷；0.01=1 公顷 | `test_scale_extract.py::test_square_kilometer` | unit | PASS | `python -m pytest tests/test_scale_extract.py` |
| 3b | 绿地率恰为下限 0.30 → SAFE（合规） | `test_scale_warning.py::test_green_rate_safe_at_min` | unit | PASS | `python -m pytest tests/test_scale_warning.py` |
| 4 | `python -m crawler --list-sources` 子进程 returncode 0 且含 govcn/bj-yq | `test_cli.py::test_cli_entry_point_list_sources` | integration | PASS | `python -m pytest tests/test_cli.py` |
| 5 | cp1252 强制控制台下 CLI 不崩溃、中文经 UTF-8 往返完好 | `test_cli.py::test_cli_entry_point_survives_non_utf8_console` | integration | PASS | 同上 |
| 6 | `python -m sourcelib` 子进程生成 library.json | `test_sourcelib_store.py::test_cli_entry_point_generates_library` | integration | PASS | `python -m pytest tests/test_sourcelib_store.py` |
| 7 | `python -m compliance --init/--validate` 子进程通过 | `test_compliance_store.py::test_cli_init_and_validate` | integration | PASS | `python -m pytest tests/test_compliance_store.py` |

## 5. 全量结果与覆盖率

- Fork1 默认 cp1252 shell（此前 5 失败）：`python -m pytest` → **185 passed**。
- Fork1 UTF-8 模式（`PYTHONUTF8=1`）：**185 passed**（双向环境无关）。
- **V1 回灌（`Youzhu/`）**：UTF-8 加固 + cp1252 回归测试已回灌，默认 cp1252 shell `python -m pytest tests/` → **152 passed**。
- 覆盖率（Fork1）：`--cov=crawler --cov=sourcelib --cov=compliance --cov=scale` → **TOTAL 87%**（scale.warning 86%、scale.extract 91%）。

### 已知缺口（如实声明）

1. 三个 `__main__.py`（含 `_force_utf8_stdio`）in-process 覆盖率为 0%——其代码仅在子进程执行，coverage 不追踪子进程；用例 5/6/7 为其功能保证。
2. ~~绿地率 min 边界~~ **已解决（任务 D）**：下限型改为严格 `<`，0.30 视为达标（SAFE）。
3. ~~V1 未回灌~~ **已解决**：UTF-8 加固 + cp1252 回归测试已回灌 `Youzhu/`（V1），cp1252 下 152 passed。

## 6. 提交证据

已按用户要求提交（分支 `feat/scale-and-utf8`）：
- `feat(scale): 规模传导 extract+warning，修复绿地率阈值/边界与平方千米换算，CLI 强制 UTF-8`（新增 `Fork1/`）
- `fix(cli): 回灌 V1（Youzhu）入口 UTF-8 加固，兼容 cp1252/cp936 控制台`
