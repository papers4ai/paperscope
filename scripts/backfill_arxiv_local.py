#!/usr/bin/env python3
"""
本地版 arxiv 回溯 + LLM 分类。结果保存到本地 JSON，不写 Supabase。

流程：
  1. 按学科类别 (cs.AI/cs.LG/cs.CV/cs.RO/cs.NE/eess.IV/q-bio.QM) + 周窗 拉 arxiv 候选
  2. LLM 判定 _domains/_topics/paper_type
  3. _domains 空的论文（LLM 判不属于三领域）丢弃
  4. 剩余写到 output/arxiv_backfill_<from>_<to>.json
  5. 用户审核后用 scripts/upsert_arxiv_local.py 上传 Supabase

用法：
    LLM_API_KEY=xxx .venv/bin/python scripts/backfill_arxiv_local.py \
        --date-from 2023-01-01 --date-to 2026-12-31

    # 测试小窗口（一周）
    LLM_API_KEY=xxx .venv/bin/python scripts/backfill_arxiv_local.py \
        --date-from 2026-05-10 --date-to 2026-05-16

    # 自定义窗大小（密集月份建议 3 天）
    LLM_API_KEY=xxx .venv/bin/python scripts/backfill_arxiv_local.py \
        --date-from 2024-07-01 --date-to 2024-08-31 --window-days 3
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

from backend.scrapers.arxiv_scraper import fetch_by_categories, DEFAULT_CATEGORIES
from backend.pipeline.classify import enrich_many_async


def out_path(date_from: str, date_to: str) -> str:
    return f"output/arxiv_backfill_{date_from}_{date_to}.json"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", required=True, help="开始日期 YYYY-MM-DD")
    ap.add_argument("--date-to", default=date.today().isoformat(), help="结束日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--window-days", type=int, default=7, help="切窗粒度（默认 7 天）")
    ap.add_argument("--categories", default=None,
                    help=f"逗号分隔的 arxiv 类别。默认 {','.join(DEFAULT_CATEGORIES)}")
    ap.add_argument("--limit", type=int, default=None,
                    help="只跑前 N 个窗（测试用）")
    ap.add_argument("--output", default=None, help="自定义输出路径")
    args = ap.parse_args()

    if not os.environ.get("LLM_API_KEY"):
        print("ERROR: LLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    cats = args.categories.split(",") if args.categories else None
    output = args.output or out_path(args.date_from, args.date_to)
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

    print(f"[arxiv-local] window: {args.date_from} → {args.date_to} ({args.window_days}d each)")
    print(f"[arxiv-local] output: {output}")
    print()

    # ── 阶段 1：拉 arxiv 候选 ────────────────────────────────────────────────
    t0 = time.time()
    papers = fetch_by_categories(
        date_from=args.date_from,
        date_to=args.date_to,
        categories=cats,
        window_days=args.window_days,
    )
    if args.limit:
        papers = papers[:args.limit]
        print(f"[arxiv-local] LIMIT applied: {len(papers)} papers")
    print(f"\n[arxiv-local] candidate pool: {len(papers):,} unique papers ({time.time()-t0:.0f}s)")

    if not papers:
        print("[arxiv-local] empty candidate pool, exit.")
        return

    # 把候选池先落盘一份（防止 LLM 阶段断电丢数据）
    candidates_path = output.replace(".json", "_candidates.json")
    with open(candidates_path, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[arxiv-local] candidates saved → {candidates_path} ({os.path.getsize(candidates_path)/1024/1024:.1f} MB)")

    # ── 阶段 2：LLM 分类 ─────────────────────────────────────────────────────
    print(f"\n[arxiv-local] LLM classifying...")
    t1 = time.time()
    papers = await enrich_many_async(papers, skip_existing=False)
    print(f"[arxiv-local] LLM done ({time.time()-t1:.0f}s)")

    # ── 阶段 3：过滤 + 写盘 ───────────────────────────────────────────────────
    kept = [p for p in papers if p.get("domains")]
    dropped = len(papers) - len(kept)
    print(f"\n[arxiv-local] {len(kept):,} kept, {dropped:,} dropped (LLM said not relevant)")

    # 统计
    from collections import Counter
    domain_counter = Counter(d for p in kept for d in (p.get("domains") or []))
    print(f"[arxiv-local] By domain: {dict(domain_counter)}")

    tmp = output + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, output)
    size_mb = os.path.getsize(output) / 1024 / 1024
    print(f"[arxiv-local] Wrote {len(kept):,} papers → {output} ({size_mb:.1f} MB)")
    print(f"\n[arxiv-local] Total time: {(time.time()-t0)/60:.1f} min")
    print(f"\n下一步：审核结果后跑")
    print(f"  .venv/bin/python scripts/upsert_arxiv_local.py {output}")


if __name__ == "__main__":
    asyncio.run(main())
