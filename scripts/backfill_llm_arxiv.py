#!/usr/bin/env python3
"""
对 Supabase 中所有 arxiv 来源的论文跑 LLM 分类 backfill。
- 跳过 topics 已非空的论文
- 用 LLM 重写 paper_type、补 topics、合并 domains（正则结果 ∪ LLM 结果）
- 批量 upsert 回 Supabase

用法：
    LLM_API_KEY=xxx SUPABASE_URL=... SUPABASE_SERVICE_KEY=... \
      .venv/bin/python scripts/backfill_llm_arxiv.py
    .venv/bin/python scripts/backfill_llm_arxiv.py --limit 200 --dry-run
    .venv/bin/python scripts/backfill_llm_arxiv.py --source s2     # 同样可以对 s2/pubmed 来源跑
"""

import argparse
import asyncio
import os
import sys
import time
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cleaning.llm_classify import classify_papers_with_llm_async
from backend.db import get_client, upsert_papers


PAGE_SIZE = 1000


def fetch_all_papers(source: str) -> List[Dict]:
    """从 Supabase 拉指定 source 的全部论文（分页）。"""
    client = get_client()
    out: List[Dict] = []
    offset = 0
    while True:
        rows = (
            client.table("papers")
            .select("id,title,abstract_excerpt,domains,tasks,topics,paper_type,source")
            .eq("source", source)
            .order("published_at", desc=True)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
            .data
        )
        if not rows:
            break
        out.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="arxiv", help="论文来源：arxiv / s2 / pubmed")
    ap.add_argument("--limit", type=int, help="只跑前 N 篇（测试用）")
    ap.add_argument("--dry-run", action="store_true", help="不写回 Supabase")
    args = ap.parse_args()

    if not os.environ.get("LLM_API_KEY"):
        print("ERROR: LLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_KEY"):
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY not set", file=sys.stderr)
        sys.exit(1)

    print(f"Loading source={args.source} papers from Supabase...")
    rows = fetch_all_papers(args.source)
    print(f"  Got {len(rows):,} rows")

    # 准备 LLM 输入：跳过 topics 已非空 + 无 abstract
    llm_input = []
    for r in rows:
        if r.get("topics"):     # 已分类
            continue
        abstract = (r.get("abstract_excerpt") or "").strip()
        if not abstract:
            continue
        llm_input.append({
            "id":       r["id"],
            "title":    r.get("title", ""),
            "abstract": abstract,
        })

    if args.limit:
        llm_input = llm_input[:args.limit]

    print(f"Sending {len(llm_input):,} papers to LLM (skipped {len(rows) - len(llm_input)} with topics or no abstract)")

    if not llm_input:
        print("Nothing to do.")
        return

    t0 = time.time()
    await classify_papers_with_llm_async(llm_input)
    print(f"LLM phase done in {time.time() - t0:.1f}s")

    # 合并到原 rows，准备 upsert
    llm_by_id = {p["id"]: p for p in llm_input if p.get("_topics")}
    print(f"Got LLM results for {len(llm_by_id):,} papers")

    updates: List[Dict] = []
    for r in rows:
        llm_p = llm_by_id.get(r["id"])
        if not llm_p:
            continue
        regex_domains = set(r.get("domains") or [])
        llm_domains = set(llm_p.get("_domains") or [])
        merged_domains = sorted(regex_domains | llm_domains)
        update = {
            "id":         r["id"],
            "topics":     llm_p["_topics"],
            "domains":    merged_domains if merged_domains else r.get("domains"),
            "paper_type": llm_p.get("type") or r.get("paper_type"),
        }
        updates.append(update)

    print(f"Prepared {len(updates):,} updates")

    if args.dry_run:
        print("[dry-run] not writing")
        return

    n = upsert_papers(updates)
    print(f"Upserted {n:,} papers")


if __name__ == "__main__":
    asyncio.run(main())
