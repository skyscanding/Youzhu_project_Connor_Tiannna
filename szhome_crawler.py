#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深圳市城市更新网 (csgx.szhome.com) 批量抓取脚本
运行环境：你本地联网机器（本机需能打开该网站）
用法：
    pip install requests beautifulsoup4
    python szhome_crawler.py
输出：
    szhome_data/articles.jsonl   每行一条记录
    szhome_data/articles.csv     同内容表格
说明：
    - 默认只抓「标题+日期+链接+摘要」，不抓全文（规避版权风险）
    - 如需正文，把 FETCH_FULL_TEXT 改为 True
    - DELAY 为每篇请求间隔（秒），请保持 >=1
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
DELAY = 1.0            # 请求间隔（秒）
FETCH_FULL_TEXT = False  # True=抓正文全文；False=只抓摘要/索引
MAX_PAGES = 0          # 0=不限；设 N 则每频道最多抓 N 页（调试用）

# 要抓的频道：名称 -> 列表页起始URL
CHANNELS = {
    "公示公告": "https://csgx.szhome.com/news/index.html",
    "行业新闻": "http://news.szhome.com/chengshigengxin.html",
    # 需要更多频道可在此追加，例如：
    # "园区专题": "http://news.szhome.com/author/3188822.html",
    # "意愿征集": "https://csgx.szhome.com/news/index.html",  # 同列表不同筛选，按需调整
}

OUT_DIR = Path("szhome_data")
OUT_DIR.mkdir(exist_ok=True)

ART_RE = re.compile(r"(/news/detail/\d+\.html|news\.szhome\.com/\d+\.html)")
DATE_RE = re.compile(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})")


def fetch(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.encoding = r.apparent_encoding or "utf-8"
            if r.status_code == 200:
                return r.text
        except Exception as e:
            print(f"  [warn] 请求失败 {url}: {e}")
        time.sleep(2)
    return ""


def abs_url(href, base):
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        # 用 base 的 scheme+host
        m = re.match(r"(https?://[^/]+)", base)
        return m.group(1) + href if m else href
    return base.rsplit("/", 1)[0] + "/" + href


def parse_list(html, base):
    """返回 (文章链接集合, 分页链接列表)"""
    soup = BeautifulSoup(html, "html.parser")
    arts, pages = set(), []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        txt = a.get_text(strip=True)
        if ART_RE.search(h):
            arts.add(abs_url(h, base))
        # 分页：文本为纯数字 或 含「下一页」
        if (txt.isdigit() or txt in ("下一页", "下页", ">")) and h not in ("", "#"):
            pages.append(abs_url(h, base))
    return arts, pages


def parse_detail(html, url):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("h1")
    if not title:
        title = soup.find("title")
    title = title.get_text(strip=True) if title else ""

    date_m = DATE_RE.search(html)
    date = date_m.group(1).replace("年", "-").replace("月", "-") if date_m else ""

    summary, content = "", ""
    # 摘要：优先 meta description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        summary = meta["content"].strip()

    if FETCH_FULL_TEXT:
        node = (soup.find(class_=re.compile(r"content|article|text"))
                or soup.find("article"))
        if node:
            content = node.get_text("\n", strip=True)

    return {
        "频道": "",  # 由调用方填充
        "标题": title,
        "日期": date,
        "URL": url,
        "摘要": summary,
        "正文": content,
    }


def crawl_channel(name, start_url):
    print(f"\n=== 频道：{name} ({start_url}) ===")
    visited_pages, seen_arts = set(), set()
    queue = [start_url]
    records = []
    page_no = 0

    while queue:
        if MAX_PAGES and page_no >= MAX_PAGES:
            break
        url = queue.pop(0)
        if url in visited_pages:
            continue
        visited_pages.add(url)
        page_no += 1
        print(f"  列表页 {page_no}: {url}")
        html = fetch(url)
        if not html:
            continue
        arts, pages = parse_list(html, url)
        for a in arts:
            if a in seen_arts:
                continue
            seen_arts.add(a)
            d = parse_detail(fetch(a), a)
            d["频道"] = name
            if d["标题"]:
                records.append(d)
                print(f"    + [{d['日期']}] {d['标题'][:40]}")
            time.sleep(DELAY)
        for p in pages:
            if p not in visited_pages:
                queue.append(p)

    return records


def main():
    all_records = []
    for name, url in CHANNELS.items():
        all_records.extend(crawl_channel(name, url))

    jsonl = OUT_DIR / "articles.jsonl"
    csvf = OUT_DIR / "articles.csv"
    with jsonl.open("w", encoding="utf-8") as fj, \
         csvf.open("w", encoding="utf-8-sig", newline="") as fc:
        writer = csv.DictWriter(fc, fieldnames=["频道", "标题", "日期", "URL", "摘要", "正文"])
        writer.writeheader()
        for r in all_records:
            fj.write(json.dumps(r, ensure_ascii=False) + "\n")
            writer.writerow(r)

    print(f"\n完成：共抓取 {len(all_records)} 条，保存至 {OUT_DIR}/")


if __name__ == "__main__":
    main()
