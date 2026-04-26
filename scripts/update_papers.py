#!/usr/bin/env python3
"""增量更新 frontend/data/papers.json

策略：从 papers4ai/Paperscope-hub 拉取最新 papers.json，按 id 与本地去重，
仅 append 新增条目到现有数组末尾，保留旧数据原有顺序（便于浏览器缓存友好）。

用法：
    python scripts/update_papers.py
    python scripts/update_papers.py --dry-run   # 仅显示将新增多少条
    python scripts/update_papers.py --source <url>
"""
import argparse
import json
import os
import sys
import urllib.request

DEFAULT_SOURCE = "https://raw.githubusercontent.com/papers4ai/Paperscope-hub/main/output/papers.json"
LOCAL = os.path.join(os.path.dirname(__file__), "..", "frontend", "data", "papers.json")
KEEP_FIELDS = ["id", "title", "abstract", "authors", "published", "year", "month",
               "pdf_url", "arxiv_url", "code", "has_code", "type", "_domains", "_tasks"]


def slim(p):
    return {k: p.get(k) for k in KEEP_FIELDS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Fetching {args.source} ...")
    with urllib.request.urlopen(args.source) as r:
        remote = json.load(r)
    remote = [p for p in remote if p.get("_domains")]
    print(f"Remote: {len(remote)} papers (with _domains)")

    local = []
    if os.path.exists(LOCAL):
        local = json.load(open(LOCAL))
    print(f"Local:  {len(local)} papers")

    seen = {p["id"] for p in local if p.get("id")}
    new_papers = [slim(p) for p in remote if p.get("id") and p["id"] not in seen]

    if not new_papers:
        print("No new papers.")
        return 0

    print(f"New:    {len(new_papers)} papers")
    if args.dry_run:
        for p in new_papers[:10]:
            print(f"  + {p['id']} {p.get('published', '')[:10]} {p['title'][:80]}")
        if len(new_papers) > 10:
            print(f"  ... and {len(new_papers) - 10} more")
        return 0

    merged = local + new_papers
    tmp = LOCAL + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, LOCAL)
    size_mb = os.path.getsize(LOCAL) / 1024 / 1024
    print(f"Wrote {len(merged)} papers to {LOCAL} ({size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
