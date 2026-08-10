# 城市更新合规参谋 Agent — 数据层工具集

对应《城市更新合规参谋 Agent》PRD 数据层，当前包含三个可独立运行的模块：

| 模块 | 对应 PRD | 职责 |
|------|----------|------|
| `crawler/`（定向爬虫） | FR-15/FR-16 | 抓取官方信源列表页，对比快照输出**变更清单**（新增/更新/消失），只读、不修改规则库 |
| `sourcelib/`（信源库） | FR-01/FR-03/FR-04 | 渠道表 + 政策文档记录的**结构化元数据**与关键词检索，返回原始记录、不生成内容 |
| `compliance/`（合规校验） | FR-06~FR-12 | 规则库 + 规则引擎：片区—地块两级校验、总量预警、多层级冲突从严建议、条款可溯源 |

---

## 〇、合规校验（compliance）

### 快速开始

```bash
# 初始化空规则库（数值与条款由专业人员录入）
python -m compliance --init

# 校验规则库（含与信源库的引用契约）
python -m compliance --validate

# 程序内使用：规则 → 引擎
python - <<'EOF'
from compliance.engine import applicable_rules, check_plot, check_total_area, find_conflicts
from compliance.models import Rule, District, Plot
from compliance.store import load_rules
from sourcelib.store import load_library

library = load_library(Path("data/sourcelib/library.json"))
rules = load_rules(Path("data/rules/rules.json"), library)

attrs = {"更新类型": "老旧小区改造", "实施方式": "政府主导"}
district = District("d-001", "示范片区", 100.0, attrs)
plot = Plot("p-001", "d-001", "地块A", 30.0, {"容积率": 3.5})

result = check_plot(plot, rules, attrs)      # allowed / not_allowed / unknown
conflicts = find_conflicts(rules, attrs)     # 同指标多层级差异 + 从严建议
total = check_total_area([plot], district)   # 总量预警
EOF
```

### 数据原则

- **数值判定全部由程序完成**（PRD 人机协作边界）：大模型只做参数抽取与报告转述，不参与任何判定
- 规则库 `data/rules/rules.json`（schema v1.0）为**契约边界**：规则的来源文件必须解析到信源库（FR-11 可溯源），save/load 双侧拦截
- 规则字段：`indicator`（纯指标名，如"容积率"）+ `comparison`（le/ge/eq）+ `value`（限值；None=未标定须注明）
- **从严原则**（FR-10）：≤上限类取小值，≥下限类取大值；比较方向不一致提示人工核对
- **诚实拒答**：地块未录入适用指标 → `unknown`，不误判合规
- 效力边界：FR-07 大模型参数抽取（自然语言→结构化回填确认）属编排层，待接入

### 产物

| 路径 | 说明 |
|------|------|
| `data/rules/rules.json` | 规则库（空库已初始化，待专业人员录入） |
| `docs/testing/compliance.tdd.md` | 模块2 TDD 证据报告 |

---

## 一、信源库（sourcelib）

### 快速开始

```bash
# 由种子数据重新生成信源库 JSON（26 渠道 + 19 文档）
python -m sourcelib

# 程序内使用
python - <<'EOF'
from pathlib import Path
from sourcelib.store import load_library
from sourcelib.search import search_documents

lib = load_library(Path("data/sourcelib/library.json"))
hits = search_documents(lib.documents, "北京容积率上限", channels=lib.channels)
for d in hits:
    print(d.title, d.doc_number or "发文号待核验", d.status)
EOF
```

### 产物与数据原则

| 路径 | 说明 |
|------|------|
| `data/sourcelib/library.json` | 信源库：26 渠道 + 19 政策文档记录 |
| `sourcelib/seed.py` | 种子数据（唯一数据源，全部来自《城市更新政策官方网址.md》） |

**数据红线**（由测试强制约束）：
- 只收录官方渠道明确点名的政策文件；发文号/日期/链接未知一律留空，note 标注"待人工核验"
- **不虚构**任何发文号、日期或链接
- 信源库损坏/非法时显式报错（区别于爬虫快照的静默容忍）

**检索语义**（FR-01）：查询按空白切分为词条，全部词条命中才算命中（AND）；无空格查询（如"北京容积率上限"）按库内关键词子串切分，切出的关键词全部要求命中，切不出的残留片段不参与要求。

**效力状态**（FR-04）：`现行有效 / 已修改 / 已废止 / 待核验`（种子数据默认待核验，由人工确认后更新）。

---

## 二、定向爬虫（crawler）

### 快速开始

```bash
pip install -r requirements.txt

# 首次运行（建立基线快照，所有记录记为「新增」）
python -m crawler

# 之后每次运行输出变更清单
python -m crawler

# 只检查指定信源
python -m crawler --source govcn --source bj-zjw-csgx

# 列出全部 90 个信源
python -m crawler --list-sources
```

### 网络前置条件

本机访问大陆政府站点需要本地代理（如 Clash）。若连接失败：

```bash
# 启动代理后指定代理地址（默认端口 7897 常见于 Clash）
python -m crawler --proxy http://127.0.0.1:7897
```

也可通过 `HTTPS_PROXY`/`HTTP_PROXY` 环境变量设置。某个站点不可达只会记录在报告中，不影响其他信源。

### 产物

| 路径 | 说明 |
|------|------|
| `data/snapshot/{信源id}.json` | 各信源记录快照（含 first_seen/last_seen） |
| `data/reports/变更清单-{时间戳}.json` | 当次运行报告：汇总 + 每信源的新增/更新/消失明细 |

**变更语义**：记录以 URL 为唯一标识（无 URL 时用 标题+日期）；同 URL 标题/日期/发文号变化 → 更新；快照有而本次列表无 → 消失（标注"可能下架或分页截断，请人工确认"）。

### 信源清单（90 个，覆盖 MD 全部官方网址）

**国家（8）**：国务院政策文件库、住房城乡建设部、自然资源部、财政部（+办公厅）、国家发展改革委（+投资项目在线平台）、国务院新闻办

**北京市（20）**：首都之窗·北京城市更新专栏、市住建委（主页 + 城市更新专栏）、市规划自然资源委 + 16 区

**其他省市（59）**：28 个省级住建厅 + 试点/重点城市 29 个（含广州/南昌城市更新专栏、深圳三部门、重庆渝中/九龙坡区）+ 融资平台 3（国开行/财政部PPP中心/农发行）

> 信源库渠道表（`sourcelib/seed.py`）与爬虫信源配置（`crawler/sources.py`）由测试强制保持 id/URL/层级一致；`tests/test_sources.py` 另强制 MD 全量网址覆盖与 Requesttest 独立脚本同步，防止漂移。

### 独立测试版（Requesttest/）

| 文件 | 说明 |
|------|------|
| `crawler_standalone.py` | 单文件爬虫（90 信源，逻辑与 crawler/ 对齐，可独立运行） |
| `城市更新政策爬虫.ipynb` | 自包含 notebook 版（`gen_notebook.py` 生成，无外部依赖，含信源一致性核对） |
| `export_excel.py` | 抓取结果 → 三 Sheet Excel（总览/政策记录/信源状态） |
| `data/` | 独立快照与报告（不依赖主 pipeline 的 data/） |

### 已知限制（如实声明）

1. **分页**：只抓列表第一页，分页内容可能被误报「消失」——消失项需人工确认
2. **区级站点**：仅有主页无专栏 URL，用宽关键词扫描链接，噪声较多，后续可为具体站点配置专栏 URL
3. **站点结构依赖**：通用解析为 best-effort；政府站点改版可能导致提取失败，报告会如实记录错误
4. **发文号**：从标题正则提取（如 `国发〔2026〕12号`），未命中则留空
5. **实时性**：数据时效取决于各站点更新频率与运行频率，建议定期手动触发

---

## 测试

```bash
python -m pytest --cov=crawler --cov=sourcelib --cov=compliance   # 151 个测试，覆盖率 91%
```

TDD 证据报告：
- `docs/testing/policy-crawler.tdd.md`（爬虫）
- `docs/testing/sourcelib.tdd.md`（信源库）
- `docs/testing/compliance.tdd.md`（合规校验）

需求文档：《城市更新合规参谋Agent_PRD.md》、《城市更新合规参谋Agent_设计研发评审.md》、《城市更新政策官方网址.md》。
