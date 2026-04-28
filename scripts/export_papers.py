#!/usr/bin/env python3
"""从 Supabase 导出 arXiv 论文到 frontend/data/papers_{year}.json（按年增量合并）

用法：
    python scripts/export_papers.py
    python scripts/export_papers.py --dry-run
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import date, timedelta
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "data")
META = os.path.join(DATA_DIR, "meta.json")
YEARS = [2023, 2024, 2025, 2026]


def local_path(year: int) -> str:
    return os.path.join(DATA_DIR, f"papers_{year}.json")


def strip_prefix(raw_id: str) -> str:
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

    # 加载现有本地各年份文件
    local_by_year: dict[int, list] = {}
    seen: set[str] = set()
    for year in YEARS:
        path = local_path(year)
        if os.path.exists(path):
            papers = json.load(open(path, encoding="utf-8"))
            local_by_year[year] = papers
            seen.update(p["id"] for p in papers if p.get("id"))
        else:
            local_by_year[year] = []
    total_local = sum(len(v) for v in local_by_year.values())
    print(f"Local: {total_local} papers across {len(YEARS)} year files")

    # 从 Supabase 拉取最近 3 天的 arxiv 论文
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

    new_by_year: dict[int, list] = defaultdict(list)
    for r in remote:
        pid = strip_prefix(r["id"])
        if pid in seen or not (r.get("domains") or []):
            continue
        p = to_frontend(r)
        year = p.get("year") or date.today().year
        if year in YEARS:
            new_by_year[year].append(p)

    total_new = sum(len(v) for v in new_by_year.values())
    print(f"New: {total_new} papers to append")

    if not total_new:
        print("Nothing to add.")
        return 0

    if args.dry_run:
        for year, papers in sorted(new_by_year.items()):
            print(f"  {year}: +{len(papers)} papers")
        return 0

    latest = ""
    for year in YEARS:
        if not new_by_year[year]:
            continue
        merged = local_by_year[year] + new_by_year[year]
        path = local_path(year)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
        size_mb = os.path.getsize(path) / 1024 / 1024
        print(f"  papers_{year}.json: {len(merged)} papers ({size_mb:.1f} MB)")
        yr_latest = max((p.get("published") or "" for p in merged if p.get("published")), default="")
        if yr_latest > latest:
            latest = yr_latest

    if latest:
        with open(META, "w", encoding="utf-8") as f:
            json.dump({"last_updated": latest[:10]}, f)
        print(f"Updated meta.json: last_updated={latest[:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
