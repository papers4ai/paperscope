#!/usr/bin/env python3
"""为论文生成中文 AI 解读（summary_zh + insights），存 output/papers_curated.json + 写回 Supabase.

筛选规则（默认）：
  - 引用 >= 50 (顶引用)
  OR
  - published_at >= today - 90 days (近 3 个月新论文)

用法：
    LLM_API_KEY=xxx .venv/bin/python scripts/backfill_summaries.py
    LLM_API_KEY=xxx .venv/bin/python scripts/backfill_summaries.py --min-citations 100 --days 180
    LLM_API_KEY=xxx .venv/bin/python scripts/backfill_summaries.py --limit 100 --dry-run
    # 全量：
    LLM_API_KEY=xxx .venv/bin/python scripts/backfill_summaries.py --all
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date, timedelta
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cleaning.llm_summarize import summarize_papers_async


def filter_papers(papers: List[Dict], min_citations: int, days: int, take_all: bool,
                  ids: List[str] | None = None) -> List[Dict]:
    if ids:
        want = set(ids)
        return [p for p in papers if p.get("id") in want]
    if take_all:
        return papers
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    out = []
    for p in papers:
        cite = p.get("citation_count") or 0
        pub = (p.get("published") or "")[:10]
        if cite >= min_citations or pub >= cutoff:
            out.append(p)
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="output/papers_curated.json")
    ap.add_argument("--min-citations", type=int, default=50,
                    help="引用 >= 此值的论文进入解读队列 (默认 50)")
    ap.add_argument("--days", type=int, default=90,
                    help="近 N 天发布的论文进入解读队列 (默认 90)")
    ap.add_argument("--all", action="store_true", help="全量跑（覆盖筛选规则）")
    ap.add_argument("--ids", help="只跑指定论文 id（逗号分隔，覆盖筛选规则）。"
                                  "重生成单篇时配合 LLM_SUMMARY_FORCE=1 可强制刷掉旧 cache。")
    ap.add_argument("--limit", type=int, help="只跑前 N 篇（测试用）")
    ap.add_argument("--dry-run", action="store_true", help="不写盘只统计")
    args = ap.parse_args()

    if not os.environ.get("LLM_API_KEY") and not os.environ.get("LLM_API_KEYS"):
        print("ERROR: LLM_API_KEY(S) not set", file=sys.stderr)
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        all_papers = json.load(f)
    print(f"Loaded {len(all_papers):,} papers from {args.input}")

    ids = [s.strip() for s in (args.ids or "").split(",") if s.strip()] or None
    candidates = filter_papers(all_papers, args.min_citations, args.days, args.all, ids)
    if ids:
        found = {p.get("id") for p in candidates}
        missing = [i for i in ids if i not in found]
        if missing:
            print(f"  [warn] {len(missing)} id(s) not found in input: {', '.join(missing)}")
    # 必须有 abstract
    candidates = [p for p in candidates if (p.get("abstract") or "").strip()]
    if args.limit:
        candidates = candidates[:args.limit]
    print(f"Candidates after filter (min_cite={args.min_citations}, days={args.days}, "
          f"all={args.all}, ids={ids}): {len(candidates):,}")

    if not candidates:
        print("Nothing to do.")
        return

    t0 = time.time()
    await summarize_papers_async(candidates)
    elapsed = time.time() - t0
    rate = len(candidates) / max(elapsed, 1)
    print(f"\nLLM done in {elapsed:.0f}s ({rate:.1f} paper/s)")

    # 把 summary 写回主文件（candidates 是 all_papers 的引用，原地修改后写回即可）
    new_summaries = sum(1 for p in candidates if p.get("summary_zh"))
    print(f"  {new_summaries:,} papers now have summary_zh")

    if args.dry_run:
        print("[dry-run] not writing back")
        return

    tmp = args.input + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(all_papers, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, args.input)
    print(f"  ✓ rewrote {args.input}")

    # 可选：写回 Supabase（如果设了 SUPABASE 环境变量）
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"):
        try:
            from backend.db import upsert_papers
            updates = [
                {"id": p["id"], "summary_zh": p["summary_zh"], "insights": p.get("insights") or []}
                for p in candidates if p.get("summary_zh")
            ]
            print(f"  Upserting {len(updates):,} papers to Supabase...")
            n = upsert_papers(updates)
            print(f"  ✓ upserted {n:,}")
        except Exception as e:
            print(f"  [warn] Supabase upsert failed: {e}")
    else:
        print("  (SUPABASE_URL/SERVICE_KEY 未设置，跳过 Supabase upsert)")


if __name__ == "__main__":
    asyncio.run(main())
