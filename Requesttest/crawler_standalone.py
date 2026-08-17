"""城市更新政策定向爬虫 —— 独立测试版（单文件，可脱离全套 pipeline 运行）。

本文件将完整 pipeline（sources → fetch → extract → snapshot → diff → 报告）
合并为单个自包含 .py，逻辑与 Youzhu/crawler/ 保持一致，无对 crawler 包的依赖。

数据来源：《城市更新政策官方网址.md》（2026-07-31 人工核实），
信源配置与 crawler/sources.py 完全一致（国家层面 6 + 北京市 19 个）。
快照与报告默认写入本文件所在目录的 data/ 下，不影响主 pipeline 的 data/。

────────────────────────────────────────────────────────────
命令行用法（爬虫测试）：
    python crawler_standalone.py --list-sources            # 列出全部信源
    python crawler_standalone.py --probe govcn             # 单源探测：只抓+解析，不写快照
    python crawler_standalone.py --source govcn --proxy http://127.0.0.1:7897
                                                           # 定向检查单个信源（更新快照）
    python crawler_standalone.py --proxy http://127.0.0.1:7897
                                                           # 全部信源一轮抓取（首次=建基线）

Jupyter / ipynb 用法（%run 或 import 均可）：
    %run crawler_standalone.py --probe bj-zjw-csgx --proxy http://127.0.0.1:7897

    import crawler_standalone as cw
    info = cw.probe("govcn", proxy="http://127.0.0.1:7897")   # 探测，不写快照
    cw.records_to_dataframe(info["records"])                 # 记录 → DataFrame
    report = cw.run(["bj-zjw-csgx"], proxy="http://127.0.0.1:7897")  # 一轮抓取+快照对比
    cw.report_to_dataframe(report)                           # 每信源汇总 → DataFrame
────────────────────────────────────────────────────────────────────────────
"""
import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, UnicodeDammit

# ══════════════════════════════════════════════════════════════════
# 1. 信源配置（与 crawler/sources.py 一致，源自《城市更新政策官方网址.md》）
# ══════════════════════════════════════════════════════════════════
# keywords 为标题关键词过滤器：命中任意一个关键词的记录才会被收录。
# 专栏页面（列出的 URL 已限定主题）用窄关键词；区级站点只有主页，
# 用宽关键词扫描链接（噪声较多，后续可为具体站点定制专栏 URL）。


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    level: str  # national / city / district
    url: str
    keywords: tuple = ("城市更新",)


# 省/市/区级主页默认宽关键词（主页噪声较多，靠快照 diff 收敛）
_WIDE_KEYWORDS = ("城市更新", "老旧小区", "城中村", "棚户区")
# 政策性银行关键词（覆盖"三大工程"：保障性住房、城中村改造、"平急两用"）
_FINANCE_KEYWORDS = ("城市更新", "城中村", "保障性住房")

# 国家层面（8）：6 个主站 + 财政部办公厅 + 发改委投资项目在线平台（MD 正文内嵌）
_NATIONAL = [
    Source("govcn", "国务院政策文件库", "national", "https://www.gov.cn/zhengce/zhengceku/"),
    Source("mohurd", "住房城乡建设部", "national", "https://www.mohurd.gov.cn"),
    Source("mnr", "自然资源部", "national", "https://www.mnr.gov.cn"),
    Source("mof", "财政部", "national", "https://www.mof.gov.cn"),
    Source("mof-bgt", "财政部办公厅", "national", "https://bgt.mof.gov.cn"),
    Source("ndrc", "国家发展改革委", "national", "https://www.ndrc.gov.cn"),
    Source("ndrc-tzxm", "国家投资项目在线审批监管平台", "national", "https://www.tzxm.gov.cn"),
    Source("scio", "国务院新闻办", "national", "https://www.scio.gov.cn"),
]

# 北京市（20）：市级专栏/主页 4 + 区政府站 16（含 MD 正文内嵌的住建委城市更新主题分类）
_DISTRICT_KEYWORDS = ("城市更新", "老旧小区", "城中村", "棚户区")

_BEIJING = [
    Source("bj-portal", "首都之窗·北京城市更新专栏", "city", "https://www.beijing.gov.cn/fuwu/lqfw/ztzl/bjchshgx/index.html"),
    Source("bj-zjw", "市住房城乡建设委", "city", "https://zjw.beijing.gov.cn"),
    Source(
        "bj-zjw-csgx",
        "市住建委·城市更新主题分类",
        "city",
        "https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/aztfl64/csgx/index.shtml",
    ),
    Source("bj-ghzrzyw", "市规划自然资源委", "city", "https://ghzrzyw.beijing.gov.cn"),
    Source("bj-dc", "东城区人民政府", "district", "http://www.bjdch.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-xc", "西城区人民政府", "district", "http://www.bjxch.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-cy", "朝阳区人民政府", "district", "http://www.bjchy.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-hd", "海淀区人民政府", "district", "https://www.bjhd.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-ft", "丰台区人民政府", "district", "http://www.bjft.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-sjs", "石景山区人民政府", "district", "http://www.bjsjs.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-mtg", "门头沟区人民政府", "district", "http://www.bjmtg.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-fs", "房山区人民政府", "district", "http://www.bjfsh.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-tz", "通州区人民政府", "district", "http://www.bjtzh.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-sy", "顺义区人民政府", "district", "https://www.bjshy.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-cp", "昌平区人民政府", "district", "http://www.bjchp.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-dx", "大兴区人民政府", "district", "http://www.bjdx.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-hr", "怀柔区人民政府", "district", "http://www.bjhr.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-pg", "平谷区人民政府", "district", "http://www.bjpg.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-my", "密云区人民政府", "district", "http://www.bjmy.gov.cn", _DISTRICT_KEYWORDS),
    Source("bj-yq", "延庆区人民政府", "district", "http://www.bjyq.gov.cn", _DISTRICT_KEYWORDS),
]

# 其他省市区（57）：省级住建厅 28 + 地市/直辖市 27 + 市辖区 2（渝中、九龙坡）
_PROVINCES = [
    # 天津市
    Source("tj-zjw", "天津市住房城乡建设委员会", "city", "http://zfcxjs.tj.gov.cn", _WIDE_KEYWORDS),
    # 河北省
    Source("he-zjw", "河北省住房和城乡建设厅", "provincial", "http://zfcxjst.hebei.gov.cn", _WIDE_KEYWORDS),
    Source("ts-zjw", "唐山市住房和城乡建设局", "city", "https://zhujianju.tangshan.gov.cn", _WIDE_KEYWORDS),
    # 山西省
    Source("sx-zjw", "山西省住房和城乡建设厅", "provincial", "http://zjt.shanxi.gov.cn", _WIDE_KEYWORDS),
    # 内蒙古自治区
    Source("nm-zjw", "内蒙古自治区住房和城乡建设厅", "provincial", "http://zjt.nmg.gov.cn", _WIDE_KEYWORDS),
    Source("hhht-zjw", "呼和浩特市住房和城乡建设局", "city", "http://zfcxjsj.huhhot.gov.cn", _WIDE_KEYWORDS),
    # 辽宁省
    Source("ln-zjw", "辽宁省住房和城乡建设厅", "provincial", "http://zjt.ln.gov.cn", _WIDE_KEYWORDS),
    Source("sy-zjw", "沈阳市城乡建设局", "city", "https://jw.shenyang.gov.cn", _WIDE_KEYWORDS),
    # 吉林省
    Source("jl-zjw", "吉林省住房和城乡建设厅", "provincial", "http://jst.jl.gov.cn", _WIDE_KEYWORDS),
    # 黑龙江省
    Source("hlj-zjw", "黑龙江省住房和城乡建设厅", "provincial", "http://zfcxjst.hlj.gov.cn", _WIDE_KEYWORDS),
    # 上海市
    Source("sh-portal", "上海市人民政府", "city", "https://www.shanghai.gov.cn", _WIDE_KEYWORDS),
    Source("sh-ghzyj", "市规划资源局", "city", "https://ghzyj.sh.gov.cn", _WIDE_KEYWORDS),
    # 江苏省
    Source("js-zjw", "江苏省住房和城乡建设厅", "provincial", "http://jsszfhcxjst.jiangsu.gov.cn", _WIDE_KEYWORDS),
    Source("nj-zjw", "南京市城乡建设委员会", "city", "http://sjw.nanjing.gov.cn", _WIDE_KEYWORDS),
    Source("suz-zjw", "苏州市住房和城乡建设局", "city", "http://zfcjj.suzhou.gov.cn", _WIDE_KEYWORDS),
    # 浙江省
    Source("zj-zjw", "浙江省住房和城乡建设厅", "provincial", "http://jst.zj.gov.cn", _WIDE_KEYWORDS),
    Source("nb-zjw", "宁波市住房和城乡建设局", "city", "https://zjw.ningbo.gov.cn", _WIDE_KEYWORDS),
    Source("hz-zjw", "杭州市城乡建设委员会", "city", "http://cxjw.hangzhou.gov.cn", _WIDE_KEYWORDS),
    # 安徽省
    Source("ah-zjw", "安徽省住房和城乡建设厅", "provincial", "http://dohurd.ah.gov.cn", _WIDE_KEYWORDS),
    Source("cz-zjw", "滁州市住房和城乡建设局", "city", "https://zfcxjsj.chuzhou.gov.cn", _WIDE_KEYWORDS),
    Source("tl-zjw", "铜陵市住房和城乡建设局", "city", "https://zfcxjsj.tl.gov.cn", _WIDE_KEYWORDS),
    # 福建省
    Source("fj-zjw", "福建省住房和城乡建设厅", "provincial", "http://zjt.fujian.gov.cn", _WIDE_KEYWORDS),
    Source("xm-zjw", "厦门市住房和建设局", "city", "https://szjj.xm.gov.cn", _WIDE_KEYWORDS),
    # 江西省（含 MD 正文内嵌的城市更新专栏）
    Source("jx-zjw", "江西省住房和城乡建设厅", "provincial", "http://zjt.jiangxi.gov.cn", _WIDE_KEYWORDS),
    Source("nc-zjw", "南昌市住房和城乡建设局", "city", "https://zjj.nc.gov.cn", _WIDE_KEYWORDS),
    Source("nc-zjw-csgx", "南昌市住建局·城市更新专栏", "city", "https://zjj.nc.gov.cn/nczfbzglj/csgx"),
    Source("jdz-zjw", "景德镇市住房和城乡建设局", "city", "http://zjj.jdz.gov.cn", _WIDE_KEYWORDS),
    # 山东省
    Source("sd-zjw", "山东省住房和城乡建设厅", "provincial", "http://zjt.shandong.gov.cn", _WIDE_KEYWORDS),
    Source("yt-zjw", "烟台市住房和城乡建设局", "city", "https://zjj.yantai.gov.cn", _WIDE_KEYWORDS),
    Source("wf-zjw", "潍坊市住房和城乡建设局", "city", "https://jsj.weifang.gov.cn", _WIDE_KEYWORDS),
    # 河南省
    Source("hn-zjw", "河南省住房和城乡建设厅", "provincial", "https://hnjs.henan.gov.cn", _WIDE_KEYWORDS),
    # 湖北省
    Source("hb-zjw", "湖北省住房和城乡建设厅", "provincial", "http://zjt.hubei.gov.cn", _WIDE_KEYWORDS),
    Source("hs-zjw", "黄石市住房和城市更新局", "city", "http://zjj.huangshi.gov.cn", _WIDE_KEYWORDS),
    # 湖南省
    Source("hun-zjw", "湖南省住房和城乡建设厅", "provincial", "http://zjt.hunan.gov.cn", _WIDE_KEYWORDS),
    Source("cs-zjw", "长沙市住房和城乡建设局", "city", "https://szjw.changsha.gov.cn", _WIDE_KEYWORDS),
    # 广东省（含 MD 正文内嵌的城市更新专栏；深圳三部门）
    Source("gd-zjw", "广东省住房和城乡建设厅", "provincial", "http://zfcxjst.gd.gov.cn", _WIDE_KEYWORDS),
    Source("gz-zjw", "广州市住房和城乡建设局", "city", "https://zfcj.gz.gov.cn", _WIDE_KEYWORDS),
    Source("gz-zjw-csgx", "广州市住建局·城市更新专栏", "city", "https://zfcj.gz.gov.cn/zjyw/csgx"),
    Source("sz-zjj", "深圳市住房和建设局", "city", "https://zjj.sz.gov.cn", _WIDE_KEYWORDS),
    Source("sz-pnr", "深圳市规划和自然资源局", "city", "https://pnr.sz.gov.cn", _WIDE_KEYWORDS),
    Source("sz-portal", "深圳市人民政府", "city", "https://www.sz.gov.cn", _WIDE_KEYWORDS),
    # 广西壮族自治区
    Source("gx-zjw", "广西壮族自治区住房和城乡建设厅", "provincial", "http://zjt.gxzf.gov.cn", _WIDE_KEYWORDS),
    # 海南省
    Source("hai-zjw", "海南省住房和城乡建设厅", "provincial", "http://zjt.hainan.gov.cn", _WIDE_KEYWORDS),
    # 重庆市（第一批试点范围仅渝中区、九龙坡区）
    Source("cq-zjw", "重庆市住房和城乡建设委员会", "city", "https://zfcxjw.cq.gov.cn", _WIDE_KEYWORDS),
    Source("cq-yz", "渝中区人民政府", "district", "https://www.cqyz.gov.cn", _WIDE_KEYWORDS),
    Source("cq-jlp", "九龙坡区人民政府", "district", "https://www.cqjlp.gov.cn", _WIDE_KEYWORDS),
    # 四川省
    Source("sc-zjw", "四川省住房和城乡建设厅", "provincial", "http://jst.sc.gov.cn", _WIDE_KEYWORDS),
    Source("cd-zjw", "成都市住房和城乡建设局", "city", "http://cdzj.chengdu.gov.cn", _WIDE_KEYWORDS),
    # 贵州省
    Source("gz-zfcxjst", "贵州省住房和城乡建设厅", "provincial", "http://zfcxjst.guizhou.gov.cn", _WIDE_KEYWORDS),
    # 云南省
    Source("yn-zjw", "云南省住房和城乡建设厅", "provincial", "https://zfcxjst.yn.gov.cn", _WIDE_KEYWORDS),
    # 西藏自治区
    Source("xz-zjw", "西藏自治区住房和城乡建设厅", "provincial", "http://zjt.xizang.gov.cn", _WIDE_KEYWORDS),
    # 陕西省
    Source("shx-zjw", "陕西省住房和城乡建设厅", "provincial", "http://js.shaanxi.gov.cn", _WIDE_KEYWORDS),
    Source("xa-zjw", "西安市住房和城乡建设局", "city", "https://zjj.xa.gov.cn", _WIDE_KEYWORDS),
    # 甘肃省
    Source("gs-zjw", "甘肃省住房和城乡建设厅", "provincial", "https://zjt.gansu.gov.cn", _WIDE_KEYWORDS),
    # 青海省
    Source("qh-zjw", "青海省住房和城乡建设厅", "provincial", "http://zjt.qinghai.gov.cn", _WIDE_KEYWORDS),
    # 宁夏回族自治区
    Source("nx-zjw", "宁夏回族自治区住房和城乡建设厅", "provincial", "http://jst.nx.gov.cn", _WIDE_KEYWORDS),
    Source("yc-zjw", "银川市住房和城乡建设局", "city", "https://zjj.yinchuan.gov.cn", _WIDE_KEYWORDS),
    # 新疆维吾尔自治区
    Source("xj-zjw", "新疆维吾尔自治区住房和城乡建设厅", "provincial", "https://zjt.xinjiang.gov.cn", _WIDE_KEYWORDS),
    # 新疆生产建设兵团
    Source("xjbt-zjw", "新疆生产建设兵团住房和城乡建设局", "provincial", "http://jshbj.xjbt.gov.cn", _WIDE_KEYWORDS),
]

# 城市更新融资支持平台（3）
_FINANCE = [
    Source("cdb", "国家开发银行", "finance", "https://www.cdb.cn", _FINANCE_KEYWORDS),
    Source("cpppc", "财政部政府和社会资本合作中心", "finance", "https://www.cpppc.org", ("城市更新",)),
    Source("adbc", "中国农业发展银行", "finance", "https://www.adbc.com.cn", _FINANCE_KEYWORDS),
]

SOURCES: list[Source] = _NATIONAL + _BEIJING + _PROVINCES + _FINANCE
SOURCES_BY_ID = {s.id: s for s in SOURCES}


# ══════════════════════════════════════════════════════════════════
# 2. 抓取层（同 fetch.py）
# ══════════════════════════════════════════════════════════════════

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 policy-monitor/0.1"
)


class FetchError(Exception):
    """抓取失败（网络不可达、超时、HTTP 错误等）。"""


def decode_html(data: bytes) -> str:
    """按页面实际编码解码（政府站点常见 GBK/GB2312/UTF-8）。

    UTF-8 必须排在首位（GBK 能"成功"解码任意字节，顺序反了会把
    UTF-8 页面解成乱码）；无提示时 UnicodeDammit 会把 GBK 误判为
    EUC-KR，因此显式给出候选编码。
    """
    return UnicodeDammit(data, ["utf-8", "gbk", "gb2312"]).unicode_markup


def fetch_html(session, url: str, timeout: float = 8, retries: int = 1, retry_delay: float = 0.5) -> str:
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
                time.sleep(retry_delay)
    raise FetchError(f"GET {url} 失败（尝试 {retries + 1} 次）：{last_error}")


# ══════════════════════════════════════════════════════════════════
# 3. 解析层（同 extract.py）
# ══════════════════════════════════════════════════════════════════

# 发文号：如 国发〔2026〕12号 / 自然资发〔2025〕226号 / (2026)12号
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
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Record":
        fields = ("title", "url", "date", "doc_number", "first_seen", "last_seen")
        return cls(**{f: data.get(f, "") for f in fields})


def find_doc_number(text: str) -> str | None:
    match = _DOC_RE.search(text)
    return match.group(1).strip() if match else None


def find_date(text: str) -> str | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def find_date_from_url(url: str) -> str:
    """从 URL 提取日期兜底：完整日期优先，其次年月（未知日）。"""
    match = _URL_DATE_FULL.search(url) or _URL_DATE_COMPACT.search(url) or _URL_DATE_STAMP.search(url)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    match = _URL_DATE_YM.search(url)
    if match:
        year, month = match.groups()
        return f"{year}-{month}"
    return ""


def extract_records(html: str, base_url: str, keywords=()) -> list[Record]:
    """从列表页提取政策记录，按 URL 去重。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[Record] = []
    seen: set[str] = set()
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
        parent = anchor.find_parent("li")
        context = parent.get_text(" ", strip=True) if parent else title
        records.append(
            Record(
                title=title,
                url=url,
                date=find_date(context) or find_date_from_url(url) or "",
                doc_number=find_doc_number(title) or "",
            )
        )
    return records


# ══════════════════════════════════════════════════════════════════
# 4. 快照层（同 snapshot.py）
# ══════════════════════════════════════════════════════════════════


def load_snapshot(path: Path) -> dict[str, Record]:
    """读取快照；文件缺失或损坏时返回空字典（相当于首次运行）。"""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {r.identity: r for r in (Record.from_dict(item) for item in data)}


def save_snapshot(path: Path, records: dict[str, Record]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.to_dict() for r in records.values()]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_with_first_seen(old: dict[str, Record], new: dict[str, Record], run_time: str) -> dict[str, Record]:
    """新记录并入快照：老记录保留 first_seen，所有记录刷新 last_seen。"""
    merged: dict[str, Record] = {}
    for key, rec in new.items():
        prev = old.get(key)
        merged[key] = Record(
            title=rec.title,
            url=rec.url,
            date=rec.date,
            doc_number=rec.doc_number,
            first_seen=prev.first_seen if prev else run_time,
            last_seen=run_time,
        )
    return merged


# ══════════════════════════════════════════════════════════════════
# 5. 变更检测（同 diff.py）
# ══════════════════════════════════════════════════════════════════


@dataclass
class DiffResult:
    added: list[Record]
    updated: list[tuple[Record, Record]]  # (旧记录, 新记录)
    vanished: list[Record]


def diff_records(old: dict[str, Record], new: dict[str, Record]) -> DiffResult:
    added = [rec for key, rec in new.items() if key not in old]
    updated: list[tuple[Record, Record]] = []
    vanished: list[Record] = []
    for key, prev in old.items():
        if key not in new:
            vanished.append(prev)
            continue
        curr = new[key]
        if prev.signature() != curr.signature():
            updated.append((prev, curr))
    return DiffResult(added=added, updated=updated, vanished=vanished)


# ══════════════════════════════════════════════════════════════════
# 6. 编排：单源探测 / 一轮抓取
# ══════════════════════════════════════════════════════════════════

DEFAULT_DATA_DIR = str(Path(__file__).resolve().parent / "data")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _make_session(proxy: str | None) -> requests.Session:
    session = requests.Session()
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    return session


def _snapshot_path(data_dir: Path, source_id: str) -> Path:
    return data_dir / "snapshot" / f"{source_id}.json"


def _report_path(data_dir: Path, run_at: str) -> Path:
    stamp = run_at.replace("T", "-").replace(":", "-")[:19]
    return data_dir / "reports" / f"变更清单-{stamp}.json"


def _changes_dict(result: DiffResult) -> dict:
    return {
        "added": [r.to_dict() for r in result.added],
        "updated": [{"old": old.to_dict(), "new": new.to_dict()} for old, new in result.updated],
        "vanished": [r.to_dict() for r in result.vanished],
    }


def probe(
    source_id: str,
    proxy: str | None = None,
    timeout: float = 8,
    retries: int = 1,
    limit: int | None = 10,
) -> dict:
    """单源探测：抓取+解析，不读写快照（适合测试解析质量）。

    返回 dict：{"source": {...}, "ok": bool, "html_len", "records": [...], "error": ""}
    """
    src = SOURCES_BY_ID.get(source_id)
    if src is None:
        return {"source_id": source_id, "ok": False, "error": f"未知信源 ID：{source_id}（可用 --list-sources 查看）"}
    session = _make_session(proxy)
    try:
        html = fetch_html(session, src.url, timeout=timeout, retries=retries)
        records = extract_records(html, src.url, src.keywords)
        if limit is not None:
            records = records[:limit]
        return {
            "source": {"id": src.id, "name": src.name, "level": src.level, "url": src.url, "keywords": src.keywords},
            "ok": True,
            "html_len": len(html),
            "records": records,
            "error": "",
        }
    except Exception as exc:
        return {"source": {"id": src.id, "name": src.name, "url": src.url}, "ok": False, "html_len": 0, "records": [], "error": f"{type(exc).__name__}: {exc}"}


def run(
    source_ids: list[str] | None = None,
    proxy: str | None = None,
    data_dir: str | Path | None = None,
    timeout: float = 8.0,
    retries: int = 1,
    politeness_delay: float = 1.0,
    now: str | None = None,
    verbose: bool = True,
) -> dict:
    """一轮抓取与快照对比，返回报告字典（结构与主 pipeline 的 cli.main 一致）。

    source_ids=None 时抓取全部信源；首次运行对每个信源建立基线快照。
    """
    selected = [s for s in SOURCES if not source_ids or s.id in source_ids]
    run_at = now or _now_iso()
    data_dir = Path(data_dir or DEFAULT_DATA_DIR)
    session = _make_session(proxy)

    sources_report: list[dict] = []
    for index, src in enumerate(selected):
        entry = {
            "id": src.id,
            "name": src.name,
            "level": src.level,
            "url": src.url,
            "status": "ok",
            "records_found": 0,
            "changes": {"added": [], "updated": [], "vanished": []},
            "error": "",
        }
        try:
            html = fetch_html(session, src.url, timeout=timeout, retries=retries)
            records = extract_records(html, src.url, src.keywords)
            new_by_id = {r.identity: r for r in records}
            old = load_snapshot(_snapshot_path(data_dir, src.id))
            result = diff_records(old, new_by_id)
            merged = merge_with_first_seen(old, new_by_id, run_at)
            save_snapshot(_snapshot_path(data_dir, src.id), merged)
            entry["records_found"] = len(records)
            entry["changes"] = _changes_dict(result)
        except Exception as exc:  # 单信源失败不影响其他信源
            entry["status"] = "error"
            entry["error"] = f"{type(exc).__name__}: {exc}"
        sources_report.append(entry)
        if index < len(selected) - 1:
            time.sleep(politeness_delay)

    report = {"run_at": run_at, "summary": _summarize(sources_report), "sources": sources_report}
    _write_report(data_dir, report, verbose=verbose)
    if verbose:
        _print_summary(report)
    return report


def _summarize(sources_report: list[dict]) -> dict:
    ok = [s for s in sources_report if s["status"] == "ok"]
    return {
        "sources_total": len(sources_report),
        "sources_ok": len(ok),
        "sources_failed": len(sources_report) - len(ok),
        "records_found": sum(s["records_found"] for s in ok),
        "added": sum(len(s["changes"]["added"]) for s in ok),
        "updated": sum(len(s["changes"]["updated"]) for s in ok),
        "vanished": sum(len(s["changes"]["vanished"]) for s in ok),
    }


def _write_report(data_dir: Path, report: dict, verbose: bool = True) -> None:
    path = _report_path(data_dir, report["run_at"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if verbose:
        print(f"报告已写入：{path}")


def _print_summary(report: dict) -> None:
    s = report["summary"]
    print(f"运行时间：{report['run_at']}")
    print(f"信源：{s['sources_total']} 个，成功 {s['sources_ok']}，失败 {s['sources_failed']}")
    print(f"命中记录：{s['records_found']} 条；新增 {s['added']}，更新 {s['updated']}，消失 {s['vanished']}")
    for entry in report["sources"]:
        if entry["status"] == "error":
            print(f"  [失败] {entry['name']}（{entry['id']}）：{entry['error']}")
            continue
        for rec in entry["changes"]["added"]:
            print(f"  [新增] {entry['name']}｜{rec['title']}｜{rec['url']}")
        for item in entry["changes"]["updated"]:
            print(f"  [更新] {entry['name']}｜{item['old']['title']} → {item['new']['title']}｜{item['new']['url']}")
        for rec in entry["changes"]["vanished"]:
            print(f"  [消失] {entry['name']}｜{rec['title']}｜{rec['url']}（未出现在本次列表中，可能下架或分页截断，请人工确认）")


# ══════════════════════════════════════════════════════════════════
# 7. 笔记本辅助（pandas 可选，仅转换时按需引入）
# ══════════════════════════════════════════════════════════════════


def records_to_dataframe(records: list[Record]):
    """记录列表 → pandas DataFrame（title/url/date/doc_number 等列）。"""
    import pandas as pd

    return pd.DataFrame([r.to_dict() for r in records])


def report_to_dataframe(report: dict):
    """一轮抓取的报告 → 每信源一行的汇总 DataFrame。"""
    import pandas as pd

    rows = []
    for entry in report["sources"]:
        rows.append(
            {
                "id": entry["id"],
                "name": entry["name"],
                "level": entry["level"],
                "status": entry["status"],
                "records_found": entry["records_found"],
                "added": len(entry["changes"]["added"]),
                "updated": len(entry["changes"]["updated"]),
                "vanished": len(entry["changes"]["vanished"]),
                "error": entry["error"],
            }
        )
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════
# 8. CLI
# ══════════════════════════════════════════════════════════════════


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="python crawler_standalone.py",
        description="城市更新政策定向爬虫（独立测试版）：抓取官方信源列表页，对比快照输出变更清单（只读，不修改规则库）。",
    )
    parser.add_argument("--source", action="append", metavar="ID", help="只检查指定信源（可多次指定）；缺省为全部信源")
    parser.add_argument("--probe", metavar="ID", help="单源探测模式：只抓取+解析并打印前 N 条记录，不读写快照（爬虫测试首选）")
    parser.add_argument("--limit", type=int, default=10, help="--probe 模式最多打印的记录条数（默认 10，0=全部）")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help=f"数据目录（默认 {DEFAULT_DATA_DIR}，独立于主 pipeline）")
    parser.add_argument("--timeout", type=float, default=8.0, help="单次请求超时秒数（默认 8）")
    parser.add_argument("--retries", type=int, default=1, help="失败重试次数（默认 1）")
    parser.add_argument("--politeness-delay", type=float, default=1.0, help="信源之间的礼貌延时秒数（默认 1）")
    parser.add_argument("--proxy", help="HTTP(S) 代理地址，如 http://127.0.0.1:7897；也可用 HTTPS_PROXY/HTTP_PROXY 环境变量")
    parser.add_argument("--list-sources", action="store_true", help="列出全部信源后退出")
    return parser.parse_args(argv)


def main(argv=None) -> dict | None:
    """CLI 入口；返回报告字典，未知信源 ID 时返回 None。"""
    args = _parse_args(argv)

    if args.list_sources:
        for src in SOURCES:
            print(f"{src.id}\t{src.level}\t{src.name}\t{src.url}")
        return {}

    if args.probe:
        src = SOURCES_BY_ID.get(args.probe)
        if src is None:
            print(f"未知信源 ID：{args.probe}（可用 --list-sources 查看全部）", file=sys.stderr)
            return None
        print(f"=== 探测 {src.name}（{src.id}）===")
        print(f"URL：{src.url}；关键词：{', '.join(src.keywords)}")
        print(f"代理：{args.proxy or '（未设置，政府站点建议 --proxy http://127.0.0.1:7897）'}")
        print("-" * 70)
        info = probe(args.probe, proxy=args.proxy, timeout=args.timeout, retries=args.retries, limit=args.limit)
        if not info["ok"]:
            print(f"[失败] {info['error']}")
            return info
        print(f"HTML 字节数：{info['html_len']}；命中记录：{len(info['records'])} 条（未写快照）")
        for i, rec in enumerate(info["records"], 1):
            print(f"  {i:>3}. {rec.title}")
            print(f"      日期：{rec.date or '-'}｜发文号：{rec.doc_number or '-'}")
            print(f"      {rec.url}")
        return info

    unknown = set(args.source or []) - {s.id for s in SOURCES}
    if unknown:
        print(f"未知信源 ID：{', '.join(sorted(unknown))}（可用 --list-sources 查看全部）", file=sys.stderr)
        return None

    return run(
        source_ids=args.source,
        proxy=args.proxy,
        data_dir=args.data_dir,
        timeout=args.timeout,
        retries=args.retries,
        politeness_delay=args.politeness_delay,
    )


if __name__ == "__main__":
    report = main()
    if report is None:
        sys.exit(2)
    summary = report.get("summary") or {} if report else {}
    if summary.get("sources_total") and not summary.get("sources_ok"):
        sys.exit(1)
