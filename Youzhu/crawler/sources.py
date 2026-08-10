"""信源配置：90 个官方信源（国家 8 + 省级 28 + 市级 33 + 区级 18 + 融资平台 3）。

数据来源：《城市更新政策官方网址.md》（2026-07-31 人工核实，85 条表格信源 + 5 个正文内嵌网址）。
keywords 为标题关键词过滤器：命中任意一个关键词的记录才会被收录。
专栏页面（列出的 URL 已限定主题）用窄关键词；省/市/区级站点只有主页，
用宽关键词扫描链接（噪声较多，后续可为具体站点定制专栏 URL）。
与 tests/test_sources.py 的 MD 全覆盖测试保持同步：MD 增删信源必须同步本文件。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    level: str  # national / provincial / city / district / finance
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
SOURCES_BY_ID: dict[str, Source] = {s.id: s for s in SOURCES}
