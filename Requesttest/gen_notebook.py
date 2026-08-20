# -*- coding: utf-8 -*-
"""生成《城市更新政策爬虫.ipynb》：自包含，不依赖任何其他脚本。

信源配置以静态块内嵌（SOURCES_BLOCK），数据来源《城市更新政策官方网址.md》。
若同目录存在 crawler_standalone.py，运行时会做一次信源一致性核对并提示漂移
（仅告警，不影响生成）。
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent

# ---------- 信源配置（90 个，静态内嵌；数据来源：城市更新政策官方网址.md） ----------
SOURCES_BLOCK = """\
    Source("govcn", "国务院政策文件库", "national", "https://www.gov.cn/zhengce/zhengceku/"),
    Source("mohurd", "住房城乡建设部", "national", "https://www.mohurd.gov.cn"),
    Source("mnr", "自然资源部", "national", "https://www.mnr.gov.cn"),
    Source("mof", "财政部", "national", "https://www.mof.gov.cn"),
    Source("mof-bgt", "财政部办公厅", "national", "https://bgt.mof.gov.cn"),
    Source("ndrc", "国家发展改革委", "national", "https://www.ndrc.gov.cn"),
    Source("ndrc-tzxm", "国家投资项目在线审批监管平台", "national", "https://www.tzxm.gov.cn"),
    Source("scio", "国务院新闻办", "national", "https://www.scio.gov.cn"),
    Source("bj-portal", "首都之窗·北京城市更新专栏", "city", "https://www.beijing.gov.cn/fuwu/lqfw/ztzl/bjchshgx/index.html"),
    Source("bj-zjw", "市住房城乡建设委", "city", "https://zjw.beijing.gov.cn"),
    Source("bj-zjw-csgx", "市住建委·城市更新主题分类", "city", "https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/aztfl64/csgx/index.shtml"),
    Source("bj-ghzrzyw", "市规划自然资源委", "city", "https://ghzrzyw.beijing.gov.cn"),
    Source("bj-dc", "东城区人民政府", "district", "http://www.bjdch.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-xc", "西城区人民政府", "district", "http://www.bjxch.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-cy", "朝阳区人民政府", "district", "http://www.bjchy.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-hd", "海淀区人民政府", "district", "https://www.bjhd.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-ft", "丰台区人民政府", "district", "http://www.bjft.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-sjs", "石景山区人民政府", "district", "http://www.bjsjs.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-mtg", "门头沟区人民政府", "district", "http://www.bjmtg.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-fs", "房山区人民政府", "district", "http://www.bjfsh.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-tz", "通州区人民政府", "district", "http://www.bjtzh.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-sy", "顺义区人民政府", "district", "https://www.bjshy.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-cp", "昌平区人民政府", "district", "http://www.bjchp.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-dx", "大兴区人民政府", "district", "http://www.bjdx.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-hr", "怀柔区人民政府", "district", "http://www.bjhr.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-pg", "平谷区人民政府", "district", "http://www.bjpg.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-my", "密云区人民政府", "district", "http://www.bjmy.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("bj-yq", "延庆区人民政府", "district", "http://www.bjyq.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("tj-zjw", "天津市住房城乡建设委员会", "city", "http://zfcxjs.tj.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("he-zjw", "河北省住房和城乡建设厅", "provincial", "http://zfcxjst.hebei.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("ts-zjw", "唐山市住房和城乡建设局", "city", "https://zhujianju.tangshan.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("sx-zjw", "山西省住房和城乡建设厅", "provincial", "http://zjt.shanxi.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("nm-zjw", "内蒙古自治区住房和城乡建设厅", "provincial", "http://zjt.nmg.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("hhht-zjw", "呼和浩特市住房和城乡建设局", "city", "http://zfcxjsj.huhhot.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("ln-zjw", "辽宁省住房和城乡建设厅", "provincial", "http://zjt.ln.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("sy-zjw", "沈阳市城乡建设局", "city", "https://jw.shenyang.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("jl-zjw", "吉林省住房和城乡建设厅", "provincial", "http://jst.jl.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("hlj-zjw", "黑龙江省住房和城乡建设厅", "provincial", "http://zfcxjst.hlj.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("sh-portal", "上海市人民政府", "city", "https://www.shanghai.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("sh-ghzyj", "市规划资源局", "city", "https://ghzyj.sh.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("js-zjw", "江苏省住房和城乡建设厅", "provincial", "http://jsszfhcxjst.jiangsu.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("nj-zjw", "南京市城乡建设委员会", "city", "http://sjw.nanjing.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("suz-zjw", "苏州市住房和城乡建设局", "city", "http://zfcjj.suzhou.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("zj-zjw", "浙江省住房和城乡建设厅", "provincial", "http://jst.zj.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("nb-zjw", "宁波市住房和城乡建设局", "city", "https://zjw.ningbo.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("hz-zjw", "杭州市城乡建设委员会", "city", "http://cxjw.hangzhou.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("ah-zjw", "安徽省住房和城乡建设厅", "provincial", "http://dohurd.ah.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("cz-zjw", "滁州市住房和城乡建设局", "city", "https://zfcxjsj.chuzhou.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("tl-zjw", "铜陵市住房和城乡建设局", "city", "https://zfcxjsj.tl.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("fj-zjw", "福建省住房和城乡建设厅", "provincial", "http://zjt.fujian.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("xm-zjw", "厦门市住房和建设局", "city", "https://szjj.xm.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("jx-zjw", "江西省住房和城乡建设厅", "provincial", "http://zjt.jiangxi.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("nc-zjw", "南昌市住房和城乡建设局", "city", "https://zjj.nc.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("nc-zjw-csgx", "南昌市住建局·城市更新专栏", "city", "https://zjj.nc.gov.cn/nczfbzglj/csgx"),
    Source("jdz-zjw", "景德镇市住房和城乡建设局", "city", "http://zjj.jdz.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("sd-zjw", "山东省住房和城乡建设厅", "provincial", "http://zjt.shandong.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("yt-zjw", "烟台市住房和城乡建设局", "city", "https://zjj.yantai.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("wf-zjw", "潍坊市住房和城乡建设局", "city", "https://jsj.weifang.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("hn-zjw", "河南省住房和城乡建设厅", "provincial", "https://hnjs.henan.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("hb-zjw", "湖北省住房和城乡建设厅", "provincial", "http://zjt.hubei.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("hs-zjw", "黄石市住房和城市更新局", "city", "http://zjj.huangshi.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("hun-zjw", "湖南省住房和城乡建设厅", "provincial", "http://zjt.hunan.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("cs-zjw", "长沙市住房和城乡建设局", "city", "https://szjw.changsha.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("gd-zjw", "广东省住房和城乡建设厅", "provincial", "http://zfcxjst.gd.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("gz-zjw", "广州市住房和城乡建设局", "city", "https://zfcj.gz.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("gz-zjw-csgx", "广州市住建局·城市更新专栏", "city", "https://zfcj.gz.gov.cn/zjyw/csgx"),
    Source("sz-zjj", "深圳市住房和建设局", "city", "https://zjj.sz.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("sz-pnr", "深圳市规划和自然资源局", "city", "https://pnr.sz.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("sz-portal", "深圳市人民政府", "city", "https://www.sz.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("gx-zjw", "广西壮族自治区住房和城乡建设厅", "provincial", "http://zjt.gxzf.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("hai-zjw", "海南省住房和城乡建设厅", "provincial", "http://zjt.hainan.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("cq-zjw", "重庆市住房和城乡建设委员会", "city", "https://zfcxjw.cq.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("cq-yz", "渝中区人民政府", "district", "https://www.cqyz.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("cq-jlp", "九龙坡区人民政府", "district", "https://www.cqjlp.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("sc-zjw", "四川省住房和城乡建设厅", "provincial", "http://jst.sc.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("cd-zjw", "成都市住房和城乡建设局", "city", "http://cdzj.chengdu.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("gz-zfcxjst", "贵州省住房和城乡建设厅", "provincial", "http://zfcxjst.guizhou.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("yn-zjw", "云南省住房和城乡建设厅", "provincial", "https://zfcxjst.yn.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("xz-zjw", "西藏自治区住房和城乡建设厅", "provincial", "http://zjt.xizang.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("shx-zjw", "陕西省住房和城乡建设厅", "provincial", "http://js.shaanxi.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("xa-zjw", "西安市住房和城乡建设局", "city", "https://zjj.xa.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("gs-zjw", "甘肃省住房和城乡建设厅", "provincial", "https://zjt.gansu.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("qh-zjw", "青海省住房和城乡建设厅", "provincial", "http://zjt.qinghai.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("nx-zjw", "宁夏回族自治区住房和城乡建设厅", "provincial", "http://jst.nx.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("yc-zjw", "银川市住房和城乡建设局", "city", "https://zjj.yinchuan.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("xj-zjw", "新疆维吾尔自治区住房和城乡建设厅", "provincial", "https://zjt.xinjiang.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("xjbt-zjw", "新疆生产建设兵团住房和城乡建设局", "provincial", "http://jshbj.xjbt.gov.cn", ("城市更新", "老旧小区", "城中村", "棚户区")),
    Source("cdb", "国家开发银行", "finance", "https://www.cdb.cn", ("城市更新", "城中村", "保障性住房")),
    Source("cpppc", "财政部政府和社会资本合作中心", "finance", "https://www.cpppc.org", ("城市更新",)),
    Source("adbc", "中国农业发展银行", "finance", "https://www.adbc.com.cn", ("城市更新", "城中村", "保障性住房")),
"""


def _source_signatures(block_text: str) -> set:
    """提取 Source(...) 的 (id, 名称, 层级, URL) 签名（兼容单行/多行定义，忽略关键词写法差异）。"""
    pattern = re.compile(r'Source\(\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"')
    return set(pattern.findall(block_text))


def check_sources_consistency() -> None:
    """若同目录存在 crawler_standalone.py，核对内嵌信源是否与其一致（仅告警）。"""
    standalone = BASE / "crawler_standalone.py"
    if not standalone.exists():
        return
    # 独立脚本的信源分散在 _NATIONAL/_BEIJING/_PROVINCES/_FINANCE 块中，全文件扫描 Source( 行
    theirs_sig = _source_signatures(standalone.read_text(encoding="utf-8"))
    ours = _source_signatures(SOURCES_BLOCK)
    if ours != theirs_sig:
        print("[警告] 内嵌信源与 crawler_standalone.py 不一致，请同步（以 MD 为准）")


def fmt_source(s):
    kw = f", {tuple(s.keywords)}" if s.keywords != ("城市更新",) else ""
    return f'    Source("{s.id}", "{s.name}", "{s.level}", "{s.url}"{kw}),'

cells = []


def md(src):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": src})


def code(src):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src})


# ================= Cell 0: 使用说明 =================
md(r"""# 城市更新政策定向爬虫（单文件版）

抓取官方信源列表页 → 提取政策记录 → 与本地快照对比 → 输出变更清单。**打开后直接 Run All 即可**。

## 三步用法

1. **改参数**（下面第一个代码格）：默认是"探测模式"（`MODE="probe"`），只抓不写快照，几秒出结果；
2. **Run All**（菜单 Cell → Run All）；
3. **看结果**：下方输出抓取记录；正式抓取（`MODE="run"`）会把快照写到本文件同目录 `data/snapshot/`，变更报告写到 `data/reports/`。

## 模式说明

| 模式 | 用途 | 副作用 |
|------|------|--------|
| `probe`（默认） | 单个/多个信源连通性与解析质量测试 | 无（不写快照） |
| `run` | 正式抓取 + 快照对比 + 变更清单 | 写入 `data/snapshot/`、`data/reports/` |

## 常见问题

- **代理**：在香港/海外访问 gov.cn 系站点会 403/超时，若需代理把 `PROXY` 改为 `"http://127.0.0.1:7897"`（建议大陆节点）；
- **依赖**：缺包时运行第 2 个代码格安装 `requests`、`beautifulsoup4`；
- **全量 90 信源**：`MODE="run"` 且 `SOURCE_IDS=[]`，不可达信源自动标记失败、不影响其他。
""")

# ================= Cell 1: 参数配置 =================
code(r'''# ============ 参数配置（只改这里） ============

MODE = "probe"          # "probe"=探测（推荐先跑这个） | "run"=正式抓取+快照对比
SOURCE_IDS = ["bj-zjw-csgx"]   # 要抓的信源 id 列表；[] = 全部 90 个（仅 run 模式支持全量）
PROXY = None            # 代理地址，如 "http://127.0.0.1:7897"；None = 直连
LIMIT = 5               # probe 模式最多打印的记录条数
TIMEOUT = 8.0           # 单次请求超时（秒）
RETRIES = 1             # 失败重试次数
POLITENESS_DELAY = 0.5  # 信源之间的礼貌延时（秒），全量跑时可调小

# 常用信源 id 速查：
#   国家: govcn(国务院政策库) mohurd(住建部) mnr(自然资源部) mof(财政部) ndrc(发改委) scio(国新办)
#   北京: bj-portal(首都之窗专栏) bj-zjw(市住建委) bj-zjw-csgx(住建委城市更新专栏) bj-ghzrzyw(规自委)
#   其他: 各省住建厅 = 省拼音缩写-zjw（如 he-zjw 河北、gd-zjw 广东）；试点城市见下方信源列表
# ================================================
''')

# ================= Cell 2: 依赖 =================
code(r'''# 依赖检查（缺少时取消下面一行的注释安装）
# %pip install requests beautifulsoup4
import requests
from bs4 import BeautifulSoup, UnicodeDammit
print("依赖 OK：requests", requests.__version__)
''')

# ================= Cell 3: 信源配置 =================
cell3_head = r'''# ============ 信源配置（90 个官方信源） ============
# 数据来源：《城市更新政策官方网址.md》（85 条表格信源 + 5 个正文内嵌网址）
# keywords = 标题关键词过滤器：标题命中任意一个关键词的记录才会被收录
from dataclasses import dataclass
from datetime import datetime
import json, re, time
from pathlib import Path
from urllib.parse import urljoin

@dataclass(frozen=True)
class Source:
    id: str
    name: str
    level: str  # national/provincial/city/district/finance
    url: str
    keywords: tuple = ("城市更新",)

# 省/市/区级主页默认宽关键词（主页噪声较多，靠快照 diff 收敛）
_WIDE_KEYWORDS = ("城市更新", "老旧小区", "城中村", "棚户区")
# 政策性银行关键词（覆盖"三大工程"：保障性住房、城中村改造、"平急两用"）
_FINANCE_KEYWORDS = ("城市更新", "城中村", "保障性住房")

# 国家层面（8）+ 北京（20）+ 省市区（59）+ 融资平台（3）= 90
SOURCES = [
__SOURCES_HERE__
]
SOURCES_BY_ID = {s.id: s for s in SOURCES}
print(f"已加载信源: {len(SOURCES)} 个")
'''
code(cell3_head.replace("__SOURCES_HERE__", SOURCES_BLOCK))

# ================= Cell 4: 抓取层 =================
code(r'''# ============ 抓取层：HTTP 请求、编码识别、重试 ============

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 policy-monitor/0.1")

class FetchError(Exception):
    """抓取失败（网络不可达、超时、HTTP 错误等）。"""

def decode_html(data: bytes) -> str:
    """按页面实际编码解码（政府站点常见 GBK/GB2312/UTF-8）。

    UTF-8 必须排在首位（GBK 能"成功"解码任意字节，顺序反了会把
    UTF-8 页面解成乱码）；无提示时 UnicodeDammit 会把 GBK 误判为
    EUC-KR，因此显式给出候选编码。
    """
    return UnicodeDammit(data, ["utf-8", "gbk", "gb2312"]).unicode_markup

def fetch_html(session, url: str, timeout: float = 8, retries: int = 1) -> str:
    """GET 并返回解码后的 HTML；失败重试 retries 次后抛 FetchError。"""
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, timeout=timeout, headers={"User-Agent": UA})
            resp.raise_for_status()
            return decode_html(resp.content)
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.5)
    raise FetchError(f"GET {url} 失败（尝试 {retries + 1} 次）：{last_error}")

def make_session(proxy):
    """创建会话；proxy 形如 http://127.0.0.1:7897，None 表示直连。"""
    session = requests.Session()
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    return session
''')

# ================= Cell 5: 解析层 =================
code(r'''# ============ 解析层：列表页 HTML → 政策记录 ============

# 发文号：如 国发〔2026〕12号 / 自然资发〔2025〕226号
_DOC_RE = re.compile(r"([\u4e00-\u9fff]{0,8}[〔\[(（]?\d{4}[〕\])）]?\s*\d+号)")
# 日期：2026-07-01 / 2026年7月1日 / 2026/07/01
_DATE_RE = re.compile(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})日?")
# URL 日期兜底（政府站 URL 常见模式，列表页无日期时启用）：
#   /2026/7/29/          → 2026-07-29
#   /20260729/           → 2026-07-29
#   t20240614_xxx.shtml  → 2024-06-14
#   /202607/             → 2026-07（仅年月，未知日）
_URL_DATE_FULL = re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})/")
_URL_DATE_COMPACT = re.compile(r"/(\d{4})(\d{2})(\d{2})/")
_URL_DATE_STAMP = re.compile(r"t(\d{4})(\d{2})(\d{2})_")
_URL_DATE_YM = re.compile(r"/(\d{4})(\d{2})/")
_SKIP_HREF = re.compile(r"^(javascript|mailto|tel|#|$)", re.IGNORECASE)

@dataclass
class Record:
    """一条政策文件元信息记录（不含正文）。"""
    title: str
    url: str
    date: str = ""
    doc_number: str = ""
    first_seen: str = ""
    last_seen: str = ""

    @property
    def identity(self) -> str:
        """记录唯一标识：URL 优先，无 URL 时用 标题+日期。"""
        return self.url if self.url else f"{self.title}|{self.date}"

    def signature(self) -> tuple:
        """内容指纹：任一字段变化视为「更新」。"""
        return (self.title, self.date, self.doc_number)

    def to_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "date": self.date,
                "doc_number": self.doc_number, "first_seen": self.first_seen,
                "last_seen": self.last_seen}

    @classmethod
    def from_dict(cls, data: dict) -> "Record":
        return cls(**{f: data.get(f, "") for f in
                      ("title", "url", "date", "doc_number", "first_seen", "last_seen")})

def find_date(text: str) -> str | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"

def find_date_from_url(url: str) -> str:
    """从 URL 提取日期兜底：完整日期优先，其次年月（未知日）。"""
    match = (_URL_DATE_FULL.search(url) or _URL_DATE_COMPACT.search(url)
             or _URL_DATE_STAMP.search(url))
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    match = _URL_DATE_YM.search(url)
    if match:
        year, month = match.groups()
        return f"{year}-{month}"
    return ""

def find_doc_number(text: str) -> str | None:
    match = _DOC_RE.search(text)
    return match.group(1).strip() if match else None

def extract_records(html: str, base_url: str, keywords=()) -> list[Record]:
    """从列表页提取政策记录：遍历所有 <a>，按关键词过滤，按 URL 去重。"""
    soup = BeautifulSoup(html, "html.parser")
    records, seen = [], set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if _SKIP_HREF.match(href):
            continue
        title = anchor.get_text(" ", strip=True)
        if not title or len(title) < 4:
            continue
        if keywords and not any(k in title for k in keywords):
            continue
        url = urljoin(base_url, href)
        if url in seen or url.rstrip("#") == base_url.rstrip("#"):
            continue
        seen.add(url)
        # 日期取自链接所在 <li> 的整行文本；无日期时从 URL 兜底；发文号从标题正则提取
        parent = anchor.find_parent("li")
        context = parent.get_text(" ", strip=True) if parent else title
        records.append(Record(title=title, url=url,
                              date=find_date(context) or find_date_from_url(url) or "",
                              doc_number=find_doc_number(title) or ""))
    return records
''')

# ================= Cell 6: 快照 + 对比 + 编排 =================
code(r'''# ============ 快照层 + 变更检测 + 编排（探测/正式抓取） ============

DATA_DIR = Path.cwd() / "data"   # 快照与报告输出目录（notebook 同目录下 data/）
run_at = datetime.now().astimezone().isoformat(timespec="seconds")

def load_snapshot(path: Path) -> dict:
    """读取快照；文件缺失或损坏时返回空字典（相当于首次运行）。"""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {r.identity: r for r in (Record.from_dict(item) for item in data)}

def save_snapshot(path: Path, records: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([r.to_dict() for r in records.values()],
                               ensure_ascii=False, indent=2), encoding="utf-8")

def merge_with_first_seen(old: dict, new: dict) -> dict:
    """新记录并入快照：老记录保留 first_seen，所有记录刷新 last_seen。"""
    merged = {}
    for key, rec in new.items():
        prev = old.get(key)
        merged[key] = Record(title=rec.title, url=rec.url, date=rec.date,
                             doc_number=rec.doc_number,
                             first_seen=prev.first_seen if prev else run_at,
                             last_seen=run_at)
    return merged

def diff_records(old: dict, new: dict):
    """与上次快照对比：返回 (新增, 更新, 消失) 三份列表。"""
    added = [rec for key, rec in new.items() if key not in old]
    updated, vanished = [], []
    for key, prev in old.items():
        if key not in new:
            vanished.append(prev)
        elif prev.signature() != new[key].signature():
            updated.append((prev, new[key]))
    return added, updated, vanished

def probe(source_id: str, limit: int = 10) -> dict:
    """单源探测：抓取+解析，不写快照（测试连通性与解析质量）。"""
    src = SOURCES_BY_ID.get(source_id)
    if src is None:
        return {"ok": False, "error": f"未知信源 id：{source_id}"}
    try:
        html = fetch_html(make_session(PROXY), src.url, timeout=TIMEOUT, retries=RETRIES)
        records = extract_records(html, src.url, src.keywords)
        return {"ok": True, "html_len": len(html), "records": records[:limit],
                "total": len(records), "source": src}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "source": src}

def run(source_ids=None) -> dict:
    """正式抓取一轮：逐信源抓取→对比快照→写回→输出变更清单。source_ids=[] 表示全部。"""
    selected = [s for s in SOURCES if not source_ids or s.id in source_ids]
    report = {"run_at": run_at, "sources": []}
    session = make_session(PROXY)
    for index, src in enumerate(selected):
        entry = {"id": src.id, "name": src.name, "status": "ok",
                 "records_found": 0, "added": [], "updated": [], "vanished": [], "error": ""}
        try:
            html = fetch_html(session, src.url, timeout=TIMEOUT, retries=RETRIES)
            records = extract_records(html, src.url, src.keywords)
            new_by_id = {r.identity: r for r in records}
            snap_path = DATA_DIR / "snapshot" / f"{src.id}.json"
            old = load_snapshot(snap_path)
            added, updated, vanished = diff_records(old, new_by_id)
            save_snapshot(snap_path, merge_with_first_seen(old, new_by_id))
            entry.update(records_found=len(records),
                         added=[r.to_dict() for r in added],
                         updated=[{"old": o.to_dict(), "new": n.to_dict()} for o, n in updated],
                         vanished=[r.to_dict() for r in vanished])
        except Exception as exc:  # 单信源失败不影响其他信源
            entry.update(status="error", error=f"{type(exc).__name__}: {exc}")
        report["sources"].append(entry)
        if index < len(selected) - 1:
            time.sleep(POLITENESS_DELAY)
    return report
''')

# ================= Cell 7: 执行 =================
code(r'''# ============ 执行（按上方参数运行） ============

if MODE == "probe":
    # 探测模式：只抓不写快照
    for sid in SOURCE_IDS:
        info = probe(sid, limit=LIMIT)
        src = info.get("source")
        print(f"=== 探测 {src.name}（{src.id}）===")
        print(f"URL：{src.url}；关键词：{'、'.join(src.keywords)}；代理：{PROXY or '直连'}")
        if not info["ok"]:
            print(f"[失败] {info['error']}")
            continue
        print(f"HTML {info['html_len']} 字节；命中 {info['total']} 条（未写快照）")
        for i, rec in enumerate(info["records"], 1):
            print(f"  {i:>3}. {rec.title}")
            print(f"      日期：{rec.date or '-'}｜发文号：{rec.doc_number or '-'}")
            print(f"      {rec.url}")

elif MODE == "run":
    # 正式模式：抓取 + 快照对比 + 变更清单
    report = run(source_ids=SOURCE_IDS or None)
    ok = [e for e in report["sources"] if e["status"] == "ok"]
    print(f"运行时间：{report['run_at']}")
    print(f"信源：{len(report['sources'])} 个，成功 {len(ok)}，失败 {len(report['sources']) - len(ok)}")
    print(f"命中记录：{sum(e['records_found'] for e in ok)} 条；"
          f"新增 {sum(len(e['added']) for e in ok)}，"
          f"更新 {sum(len(e['updated']) for e in ok)}，"
          f"消失 {sum(len(e['vanished']) for e in ok)}")
    for e in report["sources"]:
        if e["status"] == "error":
            print(f"  [失败] {e['name']}（{e['id']}）：{e['error']}")
            continue
        for rec in e["added"]:
            print(f"  [新增] {e['name']}｜{rec['title']}｜{rec['url']}")
        for item in e["updated"]:
            print(f"  [更新] {e['name']}｜{item['old']['title']} → {item['new']['title']}")
        for rec in e["vanished"]:
            print(f"  [消失] {e['name']}｜{rec['title']}｜{rec['url']}")
    print(f"快照目录：{DATA_DIR / 'snapshot'}")

else:
    raise ValueError(f"MODE 取值非法：{MODE!r}（应为 'probe' 或 'run'）")
''')

# ================= Cell 8: 收尾说明 =================
md(r"""## 结果说明

- **probe 模式**：上方输出即测试结果（连通性 + 解析质量），不影响任何文件；
- **run 模式**：每个信源的快照保存在 `data/snapshot/{信源id}.json`（首次运行=建立基线；再次运行会输出"新增/更新/消失"变更清单）；
- **导出 Excel**：抓取数据可参考同目录 `export_excel.py` 汇总导出；
- **信源不可达**：香港/海外网络下 gov.cn 系站点（govcn/mohurd/scio 等）常 403/超时，属正常；改用大陆出口 IP 后重跑即可增量补充。
""")

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.13"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
out = BASE / "城市更新政策爬虫.ipynb"
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
n_sources = len([line for line in SOURCES_BLOCK.strip().splitlines() if line.strip()])
check_sources_consistency()
print(f"已生成 {out.name}：{len(cells)} 个 cell（含 {n_sources} 个信源配置，自包含无外部依赖）")
