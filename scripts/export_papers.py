#!/usr/bin/env python3
"""从 Supabase 导出 arXiv 论文到 frontend/data/papers.json（增量合并）

用法：
    python scripts/export_papers.py
    python scripts/export_papers.py --dry-run
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import date

LOCAL = os.path.join(os.path.dirname(__file__), "..", "frontend", "data", "papers.json")
META = os.path.join(os.path.dirname(__file__), "..", "frontend", "data", "meta.json")
KEEP_FIELDS = ["id", "title", "abstract", "authors", "published", "year", "month",
               "pdf_url", "arxiv_url", "code", "has_code", "type", "_domains", "_tasks"]


def strip_prefix(raw_id: str) -> str:
    """把 'arxiv:2604.xxxxx' 统一成 '2604.xxxxx'"""
    for prefix in ("arxiv:", "s2:", "pubmed:"):
        if raw_id.startswith(prefix):
            return raw_id[len(prefix):]
    return raw_id


def to_frontend(row: dict) -> dict:
    published = (row.get("published_at") or "")[:10]
    month = int(published[5:7]) if len(published) >= 7 else None

    code_links = row.get("code_links") or []
    code_url = code_links[0] if isinstance(code_links, list) and code_links else ""

    return {
        "id": strip_prefix(row["id"]),
        "title": row.get("title", ""),
        "abstract": row.get("abstract_excerpt") or "",
        "authors": row.get("authors") or [],
        "published": published,
        "year": row.get("year"),
        "month": month,
        "pdf_url": row.get("open_access_pdf") or "",
        "arxiv_url": row.get("arxiv_url") or "",
        "code": code_url,
        "has_code": bool(code_url),
        "type": row.get("paper_type") or "",
        "_domains": row.get("domains") or [],
        "_tasks": row.get("tasks") or [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from backend.db import get_client
    client = get_client()

    # 加载现有本地数据
    local: list[dict] = []
    if os.path.exists(LOCAL):
        local = json.load(open(LOCAL, encoding="utf-8"))
    seen = {p["id"] for p in local if p.get("id")}
    print(f"Local: {len(local)} papers")

    # 从 Supabase 拉取最近 6 天的 arxiv 论文
    from datetime import timedelta
    since = (date.today() - timedelta(days=3)).isoformat()
    remote: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        rows = (
            client.table("papers")
            .select("id,title,abstract_excerpt,authors,published_at,year,open_access_pdf,arxiv_url,code_links,paper_type,domains,tasks")
            .eq("source", "arxiv")
            .gte("published_at", since)
            .order("published_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
        )
        if not rows:
            break
        remote.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    print(f"Supabase: {len(remote)} arxiv papers (since {since})")

    new_papers = [to_frontend(r) for r in remote if r["id"] not in seen and (r.get("domains") or [])]
    print(f"New: {len(new_papers)} papers to append")

    if not new_papers:
        print("Nothing to add.")
        return 0

    if args.dry_run:
        for p in new_papers[:5]:
            print(f"  + {p['id']} {p['published']} {p['title'][:80]}")
        if len(new_papers) > 5:
            print(f"  ... and {len(new_papers) - 5} more")
        return 0

    merged = local + new_papers
    tmp = LOCAL + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, LOCAL)
    size_mb = os.path.getsize(LOCAL) / 1024 / 1024
    print(f"Wrote {len(merged)} papers ({size_mb:.2f} MB) to {LOCAL}")

    # 更新 meta.json 最新日期
    latest = max((p.get("published") or "" for p in merged if p.get("published")), default="")
    if latest:
        with open(META, "w", encoding="utf-8") as f:
            json.dump({"last_updated": latest[:10]}, f)
        print(f"Updated meta.json: last_updated={latest[:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
