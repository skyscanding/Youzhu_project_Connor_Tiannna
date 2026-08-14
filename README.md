# 城市更新合规参谋 Agent

面向城市更新项目的**本地政策研判工具原型**：把规则交给人工标定，把大模型关进受限的笼子里——所有数值判定由程序与规则库完成，大模型只做"自然语言 ↔ 结构化参数"的翻译，不参与任何判断（PRD 核心设计理念）。

对应《城市更新合规参谋Agent_PRD.md》：政策查询（模块一）、合规校验（模块二）、规模传导（模块三）、政策更新监测（模块四）、流程导航（模块五）。

> 💡 **Tiannna 的贡献指南**见 [CONTRIBUTING.md](CONTRIBUTING.md)——Fork + PR 流程、提交规范、测试要求都在里面，欢迎参与！

---

## 目录结构

```
├── Youzhu/           # V1 数据层工具集（crawler + sourcelib + compliance + 测试）
├── Fork1/            # 迭代开发版（新增 规模传导 scale/ + Streamlit WebApp webapp/ + 样例规则库）
├── Requesttest/      # 独立爬虫测试版（90 信源单文件脚本 + 自包含 notebook + Excel 导出）
├── 城市更新政策抓取结果1.xlsx   # 抓取结果交付物（2026-08-10 首轮）
├── 城市更新政策抓取结果2.xlsx   # 抓取结果交付物（日期兜底修复后，107 条记录）
├── LICENSE           # MIT
└── .gitignore
```

> 注：`Youzhu/` 与 `Fork1/` 为两条并行开发线（Fork1 含 Youzhu 全部内容 + 新模块），后续迭代建议以 Fork1 为主线合并推进。

---

## 模块说明

| 模块 | 对应 PRD | 职责 | 位置 |
|------|----------|------|------|
| **crawler**（定向爬虫） | FR-15/FR-16 | 抓取 90 个官方信源列表页，与本地快照对比输出**变更清单**（新增/更新/消失），只读、不修改规则库 | `Youzhu/crawler/`、`Fork1/crawler/` |
| **sourcelib**（信源库） | FR-01/03/04 | 90 渠道 + 19 政策文档记录的结构化元数据；关键词检索（AND 语义 + 无空格查询切分）；损坏数据显式报错 | `Youzhu/sourcelib/`、`Fork1/sourcelib/` |
| **compliance**（合规校验） | FR-06~12 | 规则库 + 规则引擎：片区—地块两级校验、片区总量预警、多层级冲突从严建议、条款可溯源（来源文件必须解析到信源库） | `Youzhu/compliance/`、`Fork1/compliance/` |
| **scale**（规模传导） | FR-13/FR-14 | 容积率奖励政策切换 → 可建规模差异对比（仅规模，不含金额计算） | `Fork1/scale/` |
| **webapp**（Streamlit 界面） | 模块一/二/三 | 政策查询、规模预警、合规校验三个切片的可视化界面 + 服务层 | `Fork1/webapp/` |
| **独立测试版** | FR-15 | 单文件爬虫（90 信源，逻辑与主 pipeline 对齐）+ 自包含 notebook + 三 Sheet Excel 导出 | `Requesttest/` |

### 快速开始

```bash
pip install -r requirements.txt   # 或 Fork1/requirements.txt（含 streamlit）

# ── 信源库：重新生成 JSON 产物 / 检索演示
cd Youzhu && python -m sourcelib
python - <<'EOF'
from pathlib import Path
from sourcelib.store import load_library
from sourcelib.search import search_documents
lib = load_library(Path("data/sourcelib/library.json"))
hits = search_documents(lib.documents, "北京容积率上限", channels=lib.channels)
EOF

# ── 合规校验：初始化规则库（数值待专业人员录入）/ 校验契约
python -m compliance --init
python -m compliance --validate

# ── 定向爬虫：首次运行建基线，之后输出变更清单（gov.cn 系站点需大陆出口）
python -m crawler --list-sources
python -m crawler --proxy http://127.0.0.1:7897

# ── WebApp（Fork1）
cd ../Fork1 && streamlit run webapp/app.py

# ── 独立测试版（Requesttest）
python crawler_standalone.py --probe bj-zjw-csgx     # 单源探测（不写快照）
python crawler_standalone.py --politeness-delay 0.3  # 全量 90 信源一轮
python export_excel.py                               # 生成抓取结果 Excel
python gen_notebook.py                               # 重新生成自包含 notebook
```

---

## 测试

| 套件 | 数量 | 说明 |
|------|------|------|
| `Youzhu/`（pytest） | 152 通过 | crawler + sourcelib + compliance + 信源同步防线 |
| `Fork1/`（pytest） | 198 通过 | 含 scale、webapp、样例规则库测试 |

```bash
cd Youzhu && python -m pytest --cov=crawler --cov=sourcelib --cov=compliance
cd Fork1  && python -m pytest -q
```

TDD 证据报告（`docs/testing/`）：

| 报告 | 内容 |
|------|------|
| `policy-crawler.tdd.md` | 定向爬虫（快照/变更检测/编码修复） |
| `sourcelib.tdd.md` | 信源库（结构/校验/检索，PRD 验收查询） |
| `compliance.tdd.md` | 合规校验引擎（适用性/地块/总量/冲突/条款） |
| `all-sources-deploy.tdd.md` | 90 信源全量部署与 MD 覆盖 |
| `scale-and-cli-utf8.tdd.md` | 规模传导模块 + CLI UTF-8 加固 |
| `webapp-slice.tdd.md` | Streamlit 界面切片 |

---

## 数据与原则

- **数据来源**：《城市更新政策官方网址.md》（2026-07-31 人工核实，85 条表格信源 + 正文内嵌网址 = 90 个信源路由）
- **数据红线**：只收录官方渠道明确点名的政策文件；发文号/日期/链接未知一律留空并标注"待人工核验"，**不虚构**（由测试强制约束）
- **诚实拒答**：检索未命中 → "暂未收录"；地块缺指标 → `unknown`，不误判合规
- **同步防线**：`tests/test_sources.py` 强制 MD 全量网址 ↔ crawler 配置 ↔ 独立脚本三方一致
- **已知限制**：gov.cn 系站点需大陆出口 IP；分页内容可能误报"消失"；区级主页宽关键词扫描噪声较多；湖北/广东/广州等站点日期需定制解析（45/107 条无日期）

---

## 版本历史

| 版本 | 日期 | 内容 |
|------|------|------|
| **v1.0.0** | 2026-08-10 | V1 数据层原型：信源库 + 定向爬虫（90 信源）+ 合规校验引擎；151/152 测试 |
| main（开发中） | 2026-08-10 | 规模传导模块（Fork1/scale）+ Streamlit WebApp（Fork1/webapp）+ 样例规则库 + CLI UTF-8 加固 |

---

## 需求文档

- 《城市更新合规参谋Agent_PRD.md》
- 《城市更新合规参谋Agent_设计研发评审.md》
- 《城市更新政策官方网址.md》
