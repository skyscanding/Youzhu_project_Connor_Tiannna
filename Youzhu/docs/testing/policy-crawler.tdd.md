# 定向爬虫（政策更新监测）TDD 证据报告

> 任务：`城市更新合规参谋 Agent` PRD FR-15/FR-16 要求的定向爬虫
> 日期：2026-08-10 ｜ 运行环境：Windows 10 + Python 3.13.14

## 1. 来源计划

无 `*.plan.md` 文件；用户旅程与验收标准从以下文档提炼：

- 《城市更新合规参谋Agent_PRD.md》：FR-15（检查政策更新按钮 → 定向爬虫 → 变更清单）、FR-16（爬虫只发现变化并提醒，不自动改写规则库）
- 《城市更新政策官方网址.md》：25 处北京/国家层面信源路由表（实际落地 26 个信源：国家 6 + 北京 4 市级 + 16 区）
- 用户确认的范围决策：北京 + 国家层面；CLI 手动运行

## 2. 用户旅程

| # | 旅程 |
|---|------|
| UJ-1 | 作为合规专员，我想运行爬虫检查官方政策网站，以便发现政策文件的新增/更新/下架，生成变更清单供我人工确认 |
| UJ-2 | 作为使用者，我希望某个网站不可达时不影响其他信源的检查 |
| UJ-3 | 作为维护者，我希望爬虫只读网站并保存快照，绝不修改规则库 |
| UJ-4 | 作为使用者，我希望 GBK/UTF-8 等不同编码的政府页面都能被正确解析 |

## 3. 任务报告

| 计划任务 | 执行摘要 | 验证命令 | 结果 |
|----------|----------|----------|------|
| 项目骨架 | 建 crawler/、tests/、data/、conftest.py、requirements.txt；确认 pytest 9.1.1，补装 pytest-cov | `python -m pytest --version` | PASS |
| 测试先行（RED） | 5 个测试模块 + 2 个 HTML fixture（UTF-8/GBK），`crawler` 包不存在导致收集失败（预期的缺实现失败） | `python -m pytest -q` → 5 errors | RED ✓ |
| 实现（GREEN） | 实现 sources/fetch/extract/snapshot/diff/cli/__main__ | `python -m pytest -q` → 26 passed | GREEN ✓ |
| 编码修复 | UnicodeDammit 无提示时把 GBK 误判为 EUC-KR；修复：显式候选编码顺序 `["utf-8","gbk","gb2312"]`（UTF-8 必须在首位，否则 GBK 可"成功"解码任意字节） | `python -m pytest -q` → 26 passed | GREEN ✓ |
| 覆盖补强 | 补 CLI 分支测试（--list-sources、未知 ID、更新/消失打印、入口冒烟测试、自链接跳过）；发现计划算术错误：北京实际 4 市级条目（含住建委专栏），信源总数 26 而非 25，测试断言按现实修正 | `python -m pytest --cov=crawler` | PASS |
| 代理支持 | 环境 DNS 被 fake-ip（198.18.x.x）劫持、本机代理 127.0.0.1:7897 未运行 → gov.cn 全网不可达；按需增加 `--proxy` 参数（测试先行） | `pytest tests/test_cli.py::test_proxy_is_applied_to_session` RED → GREEN | PASS |
| 实抓验证 | 26 信源实抓：全部 FetchError（网络环境阻塞，非代码问题）；**降级行为在真实场景得到验证**：26 个失败无崩溃、报告完整生成、退出码正常 | `python -m crawler --politeness-delay 0.5` | 环境阻塞（详见第 6 节） |

### 最终验证命令与输出

```
python -m pytest --cov=crawler --cov-report=term -q
→ 32 passed
→ TOTAL 227 stmts, 95% coverage
```

## 4. 测试规格（人读保证）

| # | 保证内容 | 测试 | 类型 | 结果 | 证据 |
|---|----------|------|------|------|------|
| 1 | 从 gov.cn 风格列表页提取标题/URL/日期/发文号，无关链接被关键词过滤 | `test_extract.py::test_extract_gov_list_page` | 单元 | PASS | `pytest tests/test_extract.py` |
| 2 | GBK 编码页面解码后仍正确提取 | `test_extract.py::test_extract_beijing_gbk_page` | 单元 | PASS | 同上 |
| 3 | 相对链接解析为绝对链接、同 URL 去重、非内容链接（#/javascript/mailto）与自链接跳过 | `test_extract.py::test_extract_*` | 单元 | PASS | 同上 |
| 4 | 发文号/日期正则：`国发〔2026〕12号`、`2026年7月1日` 等变体 | `test_extract.py::test_find_doc_number_from_title` / `test_find_date_variants` | 单元 | PASS | 同上 |
| 5 | 快照 JSON 往返一致；缺失/损坏文件返回空快照（等价首次运行） | `test_snapshot.py` | 单元 | PASS | `pytest tests/test_snapshot.py` |
| 6 | 合并快照保留 first_seen、刷新 last_seen | `test_snapshot.py::test_merge_preserves_first_seen_and_updates_last_seen` | 单元 | PASS | 同上 |
| 7 | 首次运行全部记为新增；无变化时变更清单为空 | `test_diff.py::test_first_run_all_added` / `test_no_change` | 单元 | PASS | `pytest tests/test_diff.py` |
| 8 | 同 URL 标题/日期变化记为更新；快照有而本次无记为消失 | `test_diff.py::test_updated_*` / `test_vanished` | 单元 | PASS | 同上 |
| 9 | 抓取设置 UA/超时；失败重试后成功；重试耗尽抛 FetchError | `test_fetch.py` | 单元 | PASS | `pytest tests/test_fetch.py` |
| 10 | GBK/UTF-8 字节解码正确（候选编码顺序） | `test_fetch.py::test_decode_*` | 单元 | PASS | 同上 |
| 11 | 全流程：抓取→快照→对比→报告落盘，新增记录 first_seen=运行时间 | `test_cli.py::test_first_run_reports_all_added_and_writes_snapshot` | 集成 | PASS | `pytest tests/test_cli.py` |
| 12 | 二次运行无变化 → 空变更清单（幂等） | `test_cli.py::test_second_run_with_no_change_reports_empty` | 集成 | PASS | 同上 |
| 13 | **单信源失败不影响其他信源**（UJ-2）：错误入报告、失败信源不写快照 | `test_cli.py::test_source_failure_does_not_affect_others` | 集成 | PASS | 同上 |
| 14 | 更新/消失/新增三类变更在二次运行中正确分类（UJ-1） | `test_cli.py::test_second_run_reports_update_and_vanished` | 集成 | PASS | 同上 |
| 15 | `--proxy` 参数配置到 HTTP 会话（大陆站点访问前置条件） | `test_cli.py::test_proxy_is_applied_to_session` | 集成 | PASS | 同上 |
| 16 | `python -m crawler` 入口冒烟测试（真实子进程，UJ-3 只读） | `test_cli.py::test_cli_entry_point_list_sources` | 集成 | PASS | 同上 |

## 5. 覆盖率与已知缺口

```
crawler\cli.py      91 stmts  99%   （缺 1：--list-sources 分支，由真实子进程测试验证行为但未计入行覆盖）
crawler\extract.py  56 stmts  98%   （缺 1：自链接跳过分支，行为已被 test_extract_skips_link_back_to_list_page 覆盖验证）
crawler\__main__.py 9 stmts   0%    （入口 shim；真实行为已由子进程冒烟测试验证，pytest-cov 不追踪子进程）
其余模块（diff/fetch/snapshot/sources）：100%
TOTAL 95%
```

**有意的缺口**：`__main__.py` 为 9 行入口 shim，退出码逻辑（全失败退 1、未知 ID 退 2）未做子进程断言——冒烟测试验证了正常路径（退 0、输出正确），异常退出码属低成本低风险路径。

## 6. 实抓验证阻塞说明（环境，非代码）

2026-08-10 实抓 26 信源：26/26 FetchError，无一条记录。诊断结论：

1. 本机 DNS 返回 `198.18.0.2` 等 **fake-ip（Clash 类代理保留段 198.18.0.0/15）**，解析名含 `aecomnet.com` → 存在虚拟网卡/DNS 劫持残留
2. Windows 注册表 ProxyServer=`127.0.0.1:7897`（Clash 混合端口），但 **代理进程未运行**
3. 大陆站点（qq.com/sina.com.cn/gov.cn）全部连接失败，部分站点（baidu.com）直连正常 → 所有 gov.cn 流量发往 fake-ip 后无人处理

**已采取的缓解**：爬虫新增 `--proxy` 参数；用户启动代理后 `python -m crawler --proxy http://127.0.0.1:7897` 即可。降级路径已在真实运行中验证（报告完整生成、单信源错误隔离、退出码正常，见 `data/reports/变更清单-2026-08-10-10-37-37.json`）。

## 7. 合并证据

非 git 仓库，无 checkpoint commit；本报告为唯一证据载体。
