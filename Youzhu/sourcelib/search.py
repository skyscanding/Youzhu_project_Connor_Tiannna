"""信源库检索（FR-01）。

语义：查询按空白切分为词条，全部词条都命中才算命中（AND）；
命中范围 = 标题 + 发文号 + 检索关键词 + （可选）关联渠道的机构/网站名。
无空格的连续查询（如 PRD 验收场景"北京容积率上限"）先尝试按库内
关键词做子串切分：切出的关键词**全部**必须命中（查询里明确提到的
词都要求），切不出的残留片段（如"上限"）不参与要求。
只返回库中原始记录，不生成任何内容。
"""
from sourcelib.models import Channel, PolicyDocument


def _token_hits(token: str, doc: PolicyDocument, channel: Channel | None) -> bool:
    haystack = [doc.title, doc.doc_number, *doc.keywords]
    if channel:
        haystack += [channel.org, channel.site_name]
    return any(token in text for text in haystack if text)


def _expand_token(token: str, keywords: list[str]) -> list[str]:
    """词条展开：直接可命中的词条原样返回；否则切分为库内关键词（长词优先）。"""
    found = [k for k in keywords if k in token]
    return found or [token]


def _library_keywords(documents, channels) -> list[str]:
    keys = set()
    for doc in documents:
        keys.update(doc.keywords)
    for channel in channels or ():
        keys.update((channel.org, channel.site_name))
    return sorted(keys, key=len, reverse=True)


def search_documents(
    documents: list[PolicyDocument],
    query: str,
    channels: list[Channel] | None = None,
) -> list[PolicyDocument]:
    raw_tokens = [t.strip().lower() for t in query.split() if t.strip()]
    if not raw_tokens:
        return []
    keywords = _library_keywords(documents, channels)
    expanded = [_expand_token(t, keywords) for t in raw_tokens]
    channel_by_id = {c.id: c for c in (channels or ())}
    results = []
    for doc in documents:
        channel = channel_by_id.get(doc.channel_id)
        if all(all(_token_hits(form, doc, channel) for form in forms) for forms in expanded):
            results.append(doc)
    return results
