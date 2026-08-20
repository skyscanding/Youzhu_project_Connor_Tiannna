"""Minimal HTTP API for the city-renewal policy and case research agent.

Run: python agent_api.py --database cityrenewal_agent_v2.db
POST /search with {"query":"联合审查", "district":"北京市丰台区"}
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _fts_query(query: str) -> str:
    return query.replace('"', ' ').replace('*', ' ').strip()


def _group_for(level: str, jurisdiction: str, tier: str, district: str) -> str:
    if tier != "direct_basis":
        return "待核验线索" if tier == "needs_verification" else "案例与经验参考"
    if level == "national":
        return "国家级依据"
    if jurisdiction == "北京市":
        return "北京市级依据"
    if district and jurisdiction == district:
        return "目标区依据"
    if jurisdiction.startswith("北京市"):
        return "北京其他区参考"
    return "外地政策参考"


def search(database: Path, query: str, district: str = "", limit: int = 8) -> dict:
    if not query.strip():
        return {"query": query, "district": district, "groups": {}, "message": "请输入政策问题或关键词。"}
    con = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    term = _fts_query(query)
    try:
        documents = con.execute(
            """SELECT d.title,d.document_type,d.evidence_tier,d.jurisdiction_level,d.jurisdiction_name,
                       d.issuing_authority,d.document_number,d.published_date,d.effective_date,
                       d.validity_status,d.official_url,d.original_path,
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
        return {"query": query, "district": district, "groups": {}, "message": f"无法解析检索词：{exc}"}
    groups: dict[str, list[dict]] = {}
    for row in documents:
        item = dict(row)
        group = _group_for(item.pop("jurisdiction_level"), item["jurisdiction_name"], item["evidence_tier"], district)
        groups.setdefault(group, []).append(item)

    web = con.execute(
        """SELECT w.title,w.jurisdiction_name,w.record_type,w.evidence_tier,w.published_date,w.url,
                       snippet(web_records_fts,1,'<mark>','</mark>',' … ',24) excerpt
                FROM web_records_fts JOIN web_records w ON w.id=web_records_fts.rowid
                WHERE web_records_fts MATCH ? ORDER BY bm25(web_records_fts) LIMIT ?""",
        (term, limit),
    ).fetchall()
    if web:
        groups["动态与案例线索"] = [dict(row) for row in web]
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

    def _json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json({"status": "ok", "database": self.database.name})
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path("cityrenewal_agent_v2.db"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    Handler.database = args.database
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Agent API: http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

