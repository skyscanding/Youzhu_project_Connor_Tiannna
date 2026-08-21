"""Minimal HTTP API for the city-renewal policy and case research agent.

Run: python agent_api.py --database cityrenewal_agent_v2.db
POST /search with {"query":"更新", "district":"丰台区"}
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _fts_query(query: str) -> str:
    return query.replace('"', ' ').replace('*', ' ').strip()


def _fallback_terms(query: str) -> list[str]:
    """Produce forgiving terms for short queries and natural-language questions."""
    compact = "".join(query.split())
    terms = [part for part in query.replace("，", " ").replace("。", " ").split() if len(part) >= 2]
    if len(compact) >= 2:
        terms.insert(0, compact)
    # A trigram index cannot answer a two-character query.  Bigrams also give
    # a useful fallback when a user types a full question rather than a title.
    if len(compact) > 4:
        terms.extend(compact[index : index + 2] for index in range(len(compact) - 1))
    return list(dict.fromkeys(term for term in terms if len(term) >= 2))[:12]


def _fallback_excerpt(query: str, *texts: str) -> str:
    """Return a nearby source fragment and preserve the same <mark> contract as FTS."""
    terms = _fallback_terms(query)
    source = "\n".join(str(text or "") for text in texts)
    matched = next((term for term in terms if term in source), "")
    if not matched:
        return source[:220]
    position = source.find(matched)
    start = max(0, position - 88)
    end = min(len(source), position + len(matched) + 132)
    fragment = source[start:end].strip()
    if start:
        fragment = "… " + fragment
    if end < len(source):
        fragment += " …"
    return fragment.replace(matched, f"<mark>{matched}</mark>")


def _public_record(item: dict) -> dict:
    """Never expose import/provenance labels as a policy's issuing authority."""
    authority = item.get("issuing_authority", "")
    if any(token in authority for token in ("用户喂送", "本地文件", "本地导入", "上传文件")):
        item["issuing_authority"] = ""
    return item


def _fallback_documents(con: sqlite3.Connection, query: str, limit: int) -> list[sqlite3.Row]:
    terms = _fallback_terms(query)
    if not terms:
        return []
    predicates = " OR ".join("d.title LIKE ? OR d.abstract LIKE ? OR d.content LIKE ?" for _ in terms)
    patterns = [f"%{term}%" for term in terms for _ in range(3)]
    return con.execute(
        f"""SELECT d.id,d.title,d.document_type,d.evidence_tier,d.jurisdiction_level,d.jurisdiction_name,
                    d.issuing_authority,d.document_number,d.published_date,d.effective_date,
                    d.validity_status,d.official_url,
                    d.abstract AS fallback_abstract,d.content AS fallback_content
             FROM documents d WHERE {predicates}
             ORDER BY CASE WHEN d.title LIKE ? THEN 0 ELSE 1 END, d.published_date DESC LIMIT ?""",
        (*patterns, f"%{terms[0]}%", limit * 3),
    ).fetchall()


def _fallback_web(con: sqlite3.Connection, query: str, limit: int) -> list[sqlite3.Row]:
    terms = _fallback_terms(query)
    if not terms:
        return []
    predicates = " OR ".join("w.title LIKE ? OR w.content LIKE ?" for _ in terms)
    patterns = [f"%{term}%" for term in terms for _ in range(2)]
    return con.execute(
        f"""SELECT w.id,w.title,w.jurisdiction_name,w.record_type,w.evidence_tier,w.published_date,w.url,
                    w.content AS fallback_content
             FROM web_records w WHERE {predicates} ORDER BY w.published_date DESC LIMIT ?""",
        (*patterns, limit),
    ).fetchall()


def _group_for(level: str, jurisdiction: str, tier: str, district: str) -> str:
    if tier != "direct_basis":
        return "待核验线索" if tier == "needs_verification" else "案例与经验参考"
    if level == "national":
        return "国家级依据"
    if jurisdiction == "北京市":
        return "北京市级依据"
    # The user may enter "丰台区", while records use "北京市丰台区".
    # Treat either representation as the same target district.
    if district and (jurisdiction == district or jurisdiction.endswith(district)):
        return "目标区依据"
    if jurisdiction.startswith("北京市"):
        return "北京其他区参考"
    return "外地政策参考"


def detail(database: Path, kind: str, record_id: str) -> dict | None:
    """Read full public policy text only when a user explicitly requests it."""
    con = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    if kind == "document":
        row = con.execute(
            """SELECT id,title,jurisdiction_name,issuing_authority,document_number,published_date,
                       effective_date,validity_status,evidence_tier,official_url,content
                FROM documents WHERE id=?""",
            (record_id,),
        ).fetchone()
    elif kind == "web":
        row = con.execute(
            """SELECT id,title,jurisdiction_name,record_type,evidence_tier,published_date,url,content
                FROM web_records WHERE id=?""",
            (record_id,),
        ).fetchone()
    else:
        row = None
    con.close()
    return _public_record(dict(row)) if row else None


def search(database: Path, query: str, district: str = "", limit: int = 8) -> dict:
    if not query.strip():
        return {"query": query, "district": district, "groups": {}, "message": "请输入政策问题或关键词。"}
    con = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    term = _fts_query(query)
    document_fallback = False
    try:
        documents = con.execute(
            """SELECT d.id,d.title,d.document_type,d.evidence_tier,d.jurisdiction_level,d.jurisdiction_name,
                       d.issuing_authority,d.document_number,d.published_date,d.effective_date,
                       d.validity_status,d.official_url,
                       snippet(documents_fts,2,'<mark>','</mark>',' … ',32) excerpt
                FROM documents_fts JOIN documents d ON d.rowid=documents_fts.rowid
                WHERE documents_fts MATCH ?
                ORDER BY CASE WHEN d.jurisdiction_name=? THEN 0
                              WHEN d.jurisdiction_level='national' THEN 1
                              WHEN d.jurisdiction_name='北京市' THEN 2
                              WHEN d.jurisdiction_name LIKE '北京市%' THEN 3 ELSE 4 END,
                         bm25(documents_fts)
                LIMIT ?""",
            (term, district or "__none__", limit * 3),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        documents = []
    if not documents:
        documents = _fallback_documents(con, query, limit)
        document_fallback = True
    groups: dict[str, list[dict]] = {}
    for row in documents:
        item = _public_record(dict(row))
        item["result_kind"] = "document"
        if document_fallback:
            item["excerpt"] = _fallback_excerpt(query, item.pop("fallback_abstract", ""), item.pop("fallback_content", ""))
        group = _group_for(item.pop("jurisdiction_level"), item["jurisdiction_name"], item["evidence_tier"], district)
        groups.setdefault(group, []).append(item)

    web_fallback = False
    try:
        web = con.execute(
            """SELECT w.id,w.title,w.jurisdiction_name,w.record_type,w.evidence_tier,w.published_date,w.url,
                           snippet(web_records_fts,1,'<mark>','</mark>',' … ',24) excerpt
                    FROM web_records_fts JOIN web_records w ON w.id=web_records_fts.rowid
                    WHERE web_records_fts MATCH ? ORDER BY bm25(web_records_fts) LIMIT ?""",
            (term, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        web = []
    if not web:
        web = _fallback_web(con, query, limit)
        web_fallback = True
    if web:
        web_items = []
        for row in web:
            item = _public_record(dict(row))
            item["result_kind"] = "web"
            if web_fallback:
                item["excerpt"] = _fallback_excerpt(query, item.pop("fallback_content", ""))
            web_items.append(item)
        groups["动态与案例线索"] = web_items
    con.close()
    return {
        "query": query,
        "district": district,
        "groups": groups,
        "message": None if groups else "当前库未命中；请补充关键词或从官方渠道继续核验。",
        "disclaimer": "结果按地域和证据等级分层呈现，不构成自动合规结论。",
    }


class Handler(BaseHTTPRequestHandler):
    database: Path
    frontend: Path

    def end_headers(self) -> None:
        # The prototype is opened directly with file://, so it needs permission
        # to call this local API at http://127.0.0.1:8765.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def _html(self) -> bytes:
        return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>城市更新政策检索</title>
<style>body{font:16px system-ui;max-width:920px;margin:40px auto;padding:0 20px;color:#222}input,button{font:inherit;padding:10px;margin:4px}input{width:38%}button{cursor:pointer}section{margin:20px 0;padding:16px;border:1px solid #ddd;border-radius:8px}h2{margin-top:0}a{word-break:break-all}small{color:#666}</style>
<h1>城市更新政策与案例检索</h1><p>输入问题和目标行政区；结果不构成自动合规结论。</p>
<input id="q" placeholder="例如：联合审查、老旧小区、房票制度"><input id="d" placeholder="例如：北京市丰台区"><button onclick="go()">搜索</button><div id="out"></div>
<script>async function go(){const out=document.getElementById('out');out.textContent='正在检索…';try{const r=await fetch('/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q.value,district:d.value})});const x=await r.json();if(!r.ok)throw Error(x.message||'请求失败');out.innerHTML='';if(x.message){out.innerHTML='<p>'+x.message+'</p>';return}for(const [name,items] of Object.entries(x.groups)){const s=document.createElement('section');s.innerHTML='<h2>'+name+'</h2>';for(const i of items){const p=document.createElement('div');p.innerHTML='<b>'+i.title+'</b><br><small>'+[i.jurisdiction_name,i.published_date,i.evidence_tier].filter(Boolean).join(' · ')+'</small><p>'+ (i.excerpt||'') +'</p>'+(i.official_url?'<a href="'+i.official_url+'" target="_blank">官方链接</a>':i.url?'<a href="'+i.url+'" target="_blank">原始网页</a>':'');s.appendChild(p)}out.appendChild(s)}}catch(e){out.innerHTML='<p>检索失败：'+e.message+'</p>'}}</script>'''.encode("utf-8")

    def _json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _frontend_file(self, filename: str) -> None:
        """Serve the bundled prototype from the same local address as the API."""
        file_path = self.frontend / filename
        if not file_path.is_file():
            self._json({"message": "前端文件未找到。"}, HTTPStatus.NOT_FOUND)
            return
        body = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        request = urlparse(self.path)
        if request.path == "/health":
            self._json({"status": "ok", "database": self.database.name})
        elif request.path == "/detail":
            params = parse_qs(request.query)
            record = detail(self.database, params.get("kind", [""])[0], params.get("id", [""])[0])
            if record:
                self._json(record)
            else:
                self._json({"message": "未找到对应的资料。"}, HTTPStatus.NOT_FOUND)
        elif request.path == "/":
            self._frontend_file("index.html")
        elif request.path == "/prototype":
            self._frontend_file("desktop-design-interaction-v2.html")
        else:
            self._json({"message": "Use GET /health or POST /search."}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/search":
            self._json({"message": "Not found."}, HTTPStatus.NOT_FOUND)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            self._json(search(self.database, str(payload.get("query", "")), str(payload.get("district", ""))))
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"message": f"Invalid JSON request: {exc}"}, HTTPStatus.BAD_REQUEST)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path("cityrenewal_agent_v2.db"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    Handler.database = args.database
    Handler.frontend = Path(__file__).resolve().parent / "frontend"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Agent API: http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
