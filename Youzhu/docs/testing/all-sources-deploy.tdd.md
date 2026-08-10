# 全量信源部署（MD 90 网址全覆盖）TDD 证据报告

> 任务：根据《城市更新政策官方网址.md》将爬虫信源配置从 26 个扩展至 90 个，所有网址部署爬虫
> 日期：2026-08-10 ｜ 运行环境：Windows 10 + Python 3.13.14 ｜ 仓库：非 Git（无 checkpoint 提交，以命令输出为证据）

## 1. 来源计划

无 `*.plan.md` 文件；范围来自用户指令"请根据 MD 更新，所有网址都要部署爬虫"。
用户旅程与验收标准从《城市更新政策官方网址.md》（信源路由表，85 条表格信源 + 正文内嵌网址）提炼。

关键范围决策（沿用既有约定）：
- MD 表格 85 条信源 + 正文内嵌 5 个网址（住建委城市更新主题分类、南昌城市更新专栏、广州城市更新专栏、发改委投资项目在线平台、财政部办公厅）全部部署 = **90 个信源**
- `https://www.gov.cn` 主站根域不单独部署（政策库 URL 即 govcn 信源主 URL，根域与政策库内容重复），在测试中登记为 `_ROOT_ALIASES` 别名豁免
- 新增两个层级：`provincial`（省住建厅 28）、`finance`（融资平台 3）；市级 33（北京 4 + 其他 29）、区级 18（北京 16 + 渝中/九龙坡 2）
- 关键词策略：专栏页面窄关键词 `("城市更新",)`；省/市/区主页宽关键词 `("城市更新","老旧小区","城中村","棚户区")`；政策性银行 `("城市更新","城中村","保障性住房")`
- `bgt.mof.gov.cn` 在 MD 中为裸域名（无协议前缀），按 https 部署并保留原样（不加 www）

## 2. 用户旅程

| # | 旅程 |
|---|------|
| UJ-1 | 作为合规专员，我想让 MD 中的**每一个**官方网址都有爬虫信源，以便不遗漏任何政策发布渠道 |
| UJ-2 | 作为维护者，我想在 MD 增删信源时测试能立即暴露配置漂移，以便三处配置（crawler/sources.py、sourcelib/seed.py、Requesttest 独立脚本）保持同步 |
| UJ-3 | 作为使用者，我想用独立测试脚本（不依赖 pipeline 包）验证任意新信源的抓取与解析质量 |

## 3. 任务报告（RED → GREEN 证据）

| 任务 | 执行摘要 | 验证命令 | 结果 |
|------|----------|----------|------|
| 统计信源 | 解析 MD：85 表格 + 5 内嵌 = 90 个待部署网址（含 gov.cn 根域别名 1 个，MD 共出现 91 个 URL） | Python 正则统计 | PASS |
| 测试先行（RED） | 新增 `tests/test_sources.py`（10 个用例：MD 全覆盖/反查/计数/完整性/standalone 同步），`test_cli.py` 计数断言 26→90 | `python -m pytest tests/test_sources.py tests/test_cli.py` → **5 failed** | RED ✓ |
| 解析器修复 | MD URL 正则修正两处：排除 `](` 与 `)` 字符（markdown `[url](url)` 写法会吞进重复 URL）；纯文本 URL（"政策库 https://.../ "）与裸域名（bgt.mof.gov.cn）都要提取 | 同上 → 失败收敛为仅"配置未扩展" | RED ✓（4 failed，均为预期原因） |
| 实现（GREEN） | ① `crawler/sources.py` 26→90（新增 provincial/finance 层级、`SOURCES_BY_ID`）；② `sourcelib/models.py` `VALID_LEVELS` 增加 provincial/finance；③ `sourcelib/seed.py` CHANNELS 26→90（id/url/level 与爬虫对齐，试点标记按 MD 附列 22 个试点单位）；④ 脚本生成方式同步 `Requesttest/crawler_standalone.py`（从 sources.py 提取配置块替换，避免手抄漂移） | `python -m pytest -q` → **149 passed** | GREEN ✓ |
| 遗留修复 | ① mof-bgt URL 误加 `www.`，改回 MD 原样 `https://bgt.mof.gov.cn`；② 测试豁免逻辑漏计 `_ROOT_ALIASES` 的 key（gov.cn 根域） | `python -m pytest -q` → 149 passed | GREEN ✓ |

RED 阶段失败明细（4 个，原因均为"配置未扩展"，无测试代码缺陷）：
```
FAILED tests/test_sources.py::test_md_every_url_has_crawler_source  # 90 MD 网址仅 26 覆盖
FAILED tests/test_sources.py::test_md_source_count_is_as_declared   # MD 91 = 配置 26 + 豁免 1 不成立
FAILED tests/test_sources.py::test_levels_present_for_each_category # 缺 provincial/finance
FAILED tests/test_cli.py::test_list_sources                         # 26 != 90
```

## 4. 测试规格（新增 10 个用例）

| # | 保证 | 用例 | 类型 | 结果 |
|---|------|------|------|------|
| 1 | MD 每个网址都有爬虫信源（含别名豁免） | `test_md_every_url_has_crawler_source` | 回归(数据同步) | PASS |
| 2 | 配置每个网址都能在 MD 找到出处 | `test_every_source_url_appears_in_md` | 回归(数据同步) | PASS |
| 3 | 信源总数 = MD 网址数 - 别名豁免数 | `test_md_source_count_is_as_declared` | 回归(数据同步) | PASS |
| 4 | 信源 id 唯一 | `test_source_ids_unique` | 单元 | PASS |
| 5 | 信源 URL 唯一 | `test_source_urls_unique` | 单元 | PASS |
| 6 | 层级 ∈ {national,provincial,city,district,finance} | `test_source_levels_valid` | 单元 | PASS |
| 7 | 每个信源有关键词 | `test_source_keywords_nonempty` | 单元 | PASS |
| 8 | URL scheme 仅 http/https | `test_source_url_schemes_valid` | 单元 | PASS |
| 9 | 五个层级类别全部有信源 | `test_levels_present_for_each_category` | 单元 | PASS |
| 10 | Requesttest 独立脚本与 crawler 配置完全一致（id/name/level/url/keywords） | `test_standalone_config_synced_with_crawler` | 回归(双配置) | PASS |

既有防线（保持通过）：`test_sourcelib_seed.py::test_channels_align_with_crawler_sources` 强制 crawler/sources.py 与 sourcelib/seed.py 的 id/url/level 对齐（信源路由表的两个消费方）；`test_sourcelib_seed.py::test_district_channels_marked_correctly` 验证试点标记。

## 5. 覆盖率与已知缺口

- `python -m pytest --cov=crawler --cov=sourcelib` → **93%**（149 passed；未覆盖项仅为 `__main__.py` CLI 入口 0%——入口由子进程冒烟测试覆盖，不在单元覆盖目标内）
- 已知缺口（网络条件限制，非代码缺陷）：
  1. **未做实网抓取**：本地 Clash 代理可通 example.com 但对 gov.cn 全部 TLS 握手失败（fake-ip DNS 劫持 + TUN 未启用，历史已知问题）。90 个信源的真实可达性与解析质量待网络修复后用 `python -m crawler --proxy http://127.0.0.1:7897` 验证
  2. `bgt.mof.gov.cn`、`tzm.gov.cn`、`cpppc.org` 等域名协议/路径未经实网核验（MD 裸域名或正文提及），实网第一轮抓取后需人工抽查
  3. 省/市/区主页用宽关键词扫描，噪声较高（设计如此，靠快照 diff 收敛；后续可为高频噪声站点定制专栏 URL）

## 6. 合并证据

非 Git 仓库，无 checkpoint 提交；RED/GREEN 证据以上述命令输出为准。若后续引入 Git，建议合入信息：
`feat: 信源配置扩展至 90 个（MD 全量覆盖）— RED: test_sources 5 failed → GREEN: 149 passed, 93% coverage`
