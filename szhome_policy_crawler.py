#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深圳市城市更新网 - 政策法规库 (csgx.szhome.com/policy.html) 专项抓取
运行环境：你本地联网机器（本机需能打开该网站）
用法：
    pip install requests beautifulsoup4
    python szhome_policy_crawler.py
输出：
    szhome_policy_data/policies.csv      元数据：标题/日期/格式/下载次数/直链
    szhome_policy_data/policies.jsonl    同上（每行一条）
    szhome_policy_data/files/            （仅当 DOWNLOAD_FILES=True）下载的 PDF/DOC/DOCX
说明：
    - 默认只抓「标题+日期+格式+下载次数+直链」做索引（不下载文件，速度快、体积小）
    - 如需把政策原文(PDF/DOC)也下载到本地，把 DOWNLOAD_FILES 改为 True
    - 政策文件多为政府公开文件转载，下载原文风险相对较低，但仍请确认项目用途合规
    - DELAY 为每篇请求间隔（秒），请保持 >=1，避免给站点造成压力
    - MAX_PAGES=0 表示不限页数（自动翻完全部分页）；调试可设小数字
"""
import re
import time
import json
import csv
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
DELAY = 1.0             # 请求间隔（秒）
DOWNLOAD_FILES = False  # True=同时下载 PDF/DOC/DOCX 原文到 files/
MAX_PAGES = 0           # 0=不限；设 N 则最多抓 N 页（调试用）

# 起点列表：主政策法规库 + 各子栏目（带 child=N 的分区页，原爬虫爬不到）
# 深圳市城市更新网「城市各区规定」按区划分，罗湖区 = policy/5.html?child=1
START_URLS = [
    "https://csgx.szhome.com/policy.html",
    "https://csgx.szhome.com/policy/5.html?child=1",   # 城市各区规定 - 罗湖区
]
OUT_DIR = Path("szhome_policy_data")
OUT_DIR.mkdir(exist_ok=True)
FILES_DIR = OUT_DIR / "files"
FILES_DIR.mkdir(exist_ok=True)

# 匹配政策文件直链：uploadfiles/regulations/ 下的 pdf/doc/docx/wps
REG_RE = re.compile(r"uploadfiles/regulations/.*\.(pdf|docx?|wps)$", re.I)
# 分页链接候选：policy/5.html?child=2 / policy.html?page=2 / 文本为数字 等
PAGE_RE = re.compile(r"policy/(\d+)\.html(?:\?child=(\d+))?|policy\.html\?page=(\d+)", re.I)
DATE_RE = re.compile(r"发布时间[:：]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})")
DL_RE = re.compile(r"下载次数[:：]\s*(\d+)")


def fetch(url, retries=3, binary=False):
    last = ""
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.content if binary else (r.text or "")
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(2)
    print(f"  [warn] 请求失败 {url}: {last}")
    return b"" if binary else ""


def abs_url(href, base):
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        m = re.match(r"(https?:)", base)
        return (m.group(1) if m else "https:") + href
    if href.startswith("/"):
        m = re.match(r"(https?://[^/]+)", base)
        return (m.group(1) + href) if m else href
    if href.startswith("?"):   # 仅追加查询串，如 ?child=2
        return base.split("?", 1)[0] + href
    return base.rsplit("/", 1)[0] + "/" + href


def parse_policy_page(html, base):
    """返回 (政策条目列表, 分页链接列表)"""
    soup = BeautifulSoup(html, "html.parser")
    items, pages = [], set()
    seen = set()

    for a in soup.find_all("a", href=True):
        h = a["href"]
        if not REG_RE.search(h):
            continue
        url = abs_url(h, base)
        if url in seen:
            continue
        seen.add(url)

        # 在父块内提取标题/日期/下载次数（结构不固定，向上找 li/div/tr）
        parent = a.find_parent(["li", "div", "tr"]) or a
        block = parent.get_text(" ", strip=True)
        title = a.get_text(strip=True)
        if not title:
            continue
        fmt = h.rsplit(".", 1)[-1].lower()
        dm = DATE_RE.search(block)
        dlm = DL_RE.search(block)
        date = dm.group(1).replace("/", "-") if dm else ""
        dl = dlm.group(1) if dlm else ""

        items.append({
            "标题": title,
            "日期": date,
            "格式": fmt,
            "下载次数": dl,
            "文件URL": url,
        })

    # 分页探测
    for a in soup.find_all("a", href=True):
        t = a.get_text(strip=True)
        h = a["href"]
        m = PAGE_RE.search(h)
        if not m and (t.isdigit() or t in ("下一页", "下页", "›", ">")):
            # 文本是数字/下一页，但 href 没匹配正则（如 ?child=2 已在上一个分支覆盖）
            m = PAGE_RE.search(abs_url(h, base))
        if m:
            p = abs_url(h, base)
            if p and p != base:
                pages.add(p)

    return items, list(pages)


def main():
    print(f"=== 抓取政策法规库（{len(START_URLS)} 个起点）===")
    visited, all_items, queue = set(), [], list(START_URLS)
    page_no = 0

    while queue:
        if MAX_PAGES and page_no >= MAX_PAGES:
            break
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        page_no += 1
        print(f"\n列表页 {page_no}: {url}")
        html = fetch(url)
        if not html:
            continue
        items, pages = parse_policy_page(html, url)
        for it in items:
            all_items.append(it)
            print(f"  + [{it['日期']}] ({it['格式']}) {it['标题'][:46]}")
        for p in pages:
            if p not in visited:
                queue.append(p)
        time.sleep(DELAY)

    # 去重（按文件URL）
    uniq = {}
    for it in all_items:
        uniq.setdefault(it["文件URL"], it)
    records = list(uniq.values())

    # 写 CSV / JSONL
    csvf = OUT_DIR / "policies.csv"
    jsonl = OUT_DIR / "policies.jsonl"
    with csvf.open("w", encoding="utf-8-sig", newline="") as fc, \
         jsonl.open("w", encoding="utf-8") as fj:
        writer = csv.DictWriter(fc, fieldnames=["标题", "日期", "格式", "下载次数", "文件URL"])
        writer.writeheader()
        for r in records:
            writer.writerow(r)
            fj.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n完成：共抓取 {len(records)} 个政策文件，保存至 {OUT_DIR}/")

    # 可选：下载原文
    if DOWNLOAD_FILES:
        print("\n开始下载政策文件原文...")
        for i, r in enumerate(records, 1):
            data = fetch(r["文件URL"], binary=True)
            if data:
                # 文件名：序号_标题前20字.格式
                safe = re.sub(r"[\\/:*?\"<>|]", "_", r["标题"])[:20]
                fn = FILES_DIR / f"{i:03d}_{safe}.{r['格式']}"
                fn.write_bytes(data)
                print(f"  ↓ {fn.name}")
            time.sleep(DELAY)


if __name__ == "__main__":
    main()
