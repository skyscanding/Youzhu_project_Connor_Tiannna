"""信源库数据模型与校验规则。"""
import re
from dataclasses import asdict, dataclass

# FR-04：效力状态标签
VALID_STATUSES = ("现行有效", "已修改", "已废止", "待核验")
# 信源层级：国家 / 省级（省住建厅）/ 市级（直辖市与地级市）/ 区级 / 融资平台
VALID_LEVELS = ("national", "provincial", "city", "district", "finance")

_URL_RE = re.compile(r"^https?://\S+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """信源库数据校验失败（人工维护数据，非法必须显式暴露）。"""


@dataclass(frozen=True)
class Channel:
    """官方发布渠道（信源路由表中的一条）。"""

    id: str
    org: str          # 机构
    site_name: str    # 网站名称
    url: str
    level: str        # national / provincial / city / district / finance
    pilot: bool       # 是否第一批试点城市/区（建办科函〔2021〕443号）
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Channel":
        return cls(
            id=data.get("id", ""),
            org=data.get("org", ""),
            site_name=data.get("site_name", ""),
            url=data.get("url", ""),
            level=data.get("level", ""),
            pilot=data.get("pilot") is True,
            description=data.get("description", ""),
        )


@dataclass(frozen=True)
class PolicyDocument:
    """一条政策文件元信息记录（FR-01 检索返回的原始记录）。"""

    id: str
    title: str
    doc_number: str = ""       # 发文号，如 国发〔2026〕12号；未知留空
    effective_date: str = ""   # 生效日期 YYYY-MM-DD；未知留空
    status: str = "待核验"      # 现行有效/已修改/已废止/待核验
    official_url: str = ""     # 官方原文链接；未知留空
    channel_id: str = ""       # 关联渠道；未知留空
    keywords: tuple = ()       # 检索关键词
    note: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["keywords"] = list(self.keywords)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "PolicyDocument":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            doc_number=data.get("doc_number", ""),
            effective_date=data.get("effective_date", ""),
            status=data.get("status", "待核验"),
            official_url=data.get("official_url", ""),
            channel_id=data.get("channel_id", ""),
            keywords=tuple(data.get("keywords") or ()),
            note=data.get("note", ""),
        )


def validate_channel(channel: Channel) -> list[str]:
    """返回校验错误列表；空列表表示通过。"""
    errors = []
    if not channel.id:
        errors.append("渠道 id 为空")
    if not channel.org:
        errors.append(f"[{channel.id}] 机构为空")
    if not channel.site_name:
        errors.append(f"[{channel.id}] 网站名称为空")
    if not _URL_RE.match(channel.url):
        errors.append(f"[{channel.id}] URL 非法：{channel.url!r}")
    if channel.level not in VALID_LEVELS:
        errors.append(f"[{channel.id}] 层级非法：{channel.level!r}")
    return errors


def validate_document(doc: PolicyDocument, strict: bool = False) -> list[str]:
    """返回校验错误列表；strict=True 时直接抛 ValidationError。"""
    errors = []
    if not doc.id:
        errors.append("文档 id 为空")
    if not doc.title:
        errors.append(f"[{doc.id}] 标题为空")
    if doc.status not in VALID_STATUSES:
        errors.append(f"[{doc.id}] 效力状态非法：{doc.status!r}")
    if doc.effective_date and not _DATE_RE.match(doc.effective_date):
        errors.append(f"[{doc.id}] 日期格式非法：{doc.effective_date!r}")
    if doc.official_url and not _URL_RE.match(doc.official_url):
        errors.append(f"[{doc.id}] 官方链接非法：{doc.official_url!r}")
    if strict and errors:
        raise ValidationError("；".join(errors))
    return errors
