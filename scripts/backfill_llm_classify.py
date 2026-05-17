#!/usr/bin/env python3
"""
对已有 output/papers_curated.json 跑 LLM 分类 backfill。
- 跳过 cache 命中和已有 _topics 的论文
- 保留 venue 强信号（_domains 与 LLM 结果合并）
- 重复运行安全

用法：
    LLM_API_KEY=xxx python scripts/backfill_llm_classify.py
    LLM_API_KEY=xxx python scripts/backfill_llm_classify.py --limit 200   # 小批测试
    LLM_API_KEY=xxx python scripts/backfill_llm_classify.py --input output/papers_curated.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cleaning.llm_classify import classify_papers_with_llm_async
from fetch_curated_fast import ALL_VENUES, S2_VENUES


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="output/papers_curated.json")
    ap.add_argument("--limit", type=int, help="只跑前 N 篇（测试用）")
    ap.add_argument("--dry-run", action="store_true", help="不写回文件")
    args = ap.parse_args()

    if not os.environ.get("LLM_API_KEY"):
        print("ERROR: LLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    with open(args.input, encoding="utf-8") as f:
        papers: List[Dict] = json.load(f)
    print(f"Loaded {len(papers)} papers from {args.input}")

    # venue 强信号（MICCAI/ICRA/TRO 等专业 venue 的硬编码 domains）
    venue_cfg_all = {**ALL_VENUES, **S2_VENUES}
    venue_pinned: Dict[str, List[str]] = {}
    for p in papers:
        cfg = venue_cfg_all.get(p.get("venue", ""), {})
        if cfg.get("domains"):
            venue_pinned[p["id"]] = list(cfg["domains"])

    # 只对有摘要的论文跑 LLM
    llm_input = [p for p in papers if (p.get("abstract") or "").strip()]
    if args.limit:
        llm_input = llm_input[:args.limit]
        print(f"Limit applied: only processing first {len(llm_input)} papers")
    print(f"Sending {len(llm_input)} papers to LLM (cache + prior _topics will skip)…")

    t0 = time.time()
    await classify_papers_with_llm_async(llm_input)
    elapsed = time.time() - t0
    print(f"LLM phase done in {elapsed:.1f}s ({len(llm_input) / max(elapsed, 1):.1f} papers/s)")

    # 合并 venue 强信号到 LLM 结果
    merged_count = 0
    for p in papers:
        pinned = venue_pinned.get(p["id"])
        if pinned:
            before = set(p.get("_domains") or [])
            p["_domains"] = sorted(before | set(pinned))
            if p["_domains"] != list(before):
                merged_count += 1
    print(f"Venue-pinned domains merged into {merged_count} papers")

    # 统计
    from collections import Counter
    classified = sum(1 for p in papers if p.get("_topics"))
    domain_counts = Counter(d for p in papers for d in (p.get("_domains") or []))
    print(f"Stats: {classified}/{len(papers)} have _topics; domains={dict(domain_counts)}")

    if args.dry_run:
        print("[dry-run] not writing")
        return

    tmp = args.input + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, args.input)
    size_mb = os.path.getsize(args.input) / 1024 / 1024
    print(f"Wrote {len(papers)} papers → {args.input} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
