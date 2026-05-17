#!/usr/bin/env python3
"""把 backfill_arxiv_local.py 跑出来的本地 JSON 上传到 Supabase。

用法：
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... \
      .venv/bin/python scripts/upsert_arxiv_local.py output/arxiv_backfill_2023-01-01_2026-12-31.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import upsert_papers


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="本地 JSON 路径")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and (not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_KEY")):
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY not set", file=sys.stderr)
        sys.exit(1)

    papers = json.load(open(args.input, encoding="utf-8"))
    print(f"Loaded {len(papers):,} papers from {args.input}")

    if args.dry_run:
        print("[dry-run] not uploading")
        from collections import Counter
        domains = Counter(d for p in papers for d in (p.get("domains") or []))
        types = Counter(p.get("paper_type") for p in papers)
        years = Counter(p.get("year") for p in papers)
        print(f"  domains: {dict(domains)}")
        print(f"  types:   {dict(types)}")
        print(f"  years:   {dict(sorted(years.items()))}")
        return

    n = upsert_papers(papers)
    print(f"Upserted {n:,} papers to Supabase")


if __name__ == "__main__":
    main()
