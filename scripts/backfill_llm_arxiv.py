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
from cleaning.llm_summarize import summarize_papers_async
from backend.db import get_client, upsert_papers


PAGE_SIZE = 1000


def fetch_all_papers(source: str,
                     date_from: str | None = None,
                     date_to: str | None = None) -> List[Dict]:
    """从 Supabase 拉指定 source 的论文（分页）。
    可选用 date_from/date_to (YYYY-MM-DD) 过滤 published_at。
    """
    client = get_client()
    out: List[Dict] = []
    offset = 0
    while True:
        q = (
            client.table("papers")
            .select("id,title,abstract_excerpt,domains,tasks,topics,paper_type,source,"
                    "summary_zh,summary_en,insights,insights_en,published_at")
            .eq("source", source)
            .order("published_at", desc=True)
        )
        if date_from:
            q = q.gte("published_at", date_from)
        if date_to:
            q = q.lte("published_at", date_to)
        rows = q.range(offset, offset + PAGE_SIZE - 1).execute().data
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
    ap.add_argument("--date-from", default=None,
                    help="只跑 published_at >= 这个日期的论文 (YYYY-MM-DD)")
    ap.add_argument("--date-to", default=None,
                    help="只跑 published_at <= 这个日期的论文 (YYYY-MM-DD)")
    ap.add_argument("--skip-classify", action="store_true",
                    help="只跑 summary，不跑 classify（适合已有 topics 的论文补 summary）")
    ap.add_argument("--skip-summary", action="store_true",
                    help="只跑 classify，不跑 summary")
    ap.add_argument("--force-summary", action="store_true",
                    help="忽略 summary 缓存,对所有论文重新生成双语 summary "
                         "(用于把只有 zh 的旧条目补出 en)")
    args = ap.parse_args()
    if args.force_summary:
        os.environ["LLM_SUMMARY_FORCE"] = "1"

    if not os.environ.get("LLM_API_KEY"):
        print("ERROR: LLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_KEY"):
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY not set", file=sys.stderr)
        sys.exit(1)

    scope_desc = f"source={args.source}"
    if args.date_from or args.date_to:
        scope_desc += f", published_at {args.date_from or '-'} → {args.date_to or '-'}"
    print(f"Loading {scope_desc} papers from Supabase...")
    rows = fetch_all_papers(args.source, date_from=args.date_from, date_to=args.date_to)
    print(f"  Got {len(rows):,} rows")

    updates_by_id: Dict[str, Dict] = {}   # id -> 更新字段

    # ── 阶段 1: classify (domains/topics/paper_type) ─────────────────
    if not args.skip_classify:
        classify_input = []
        for r in rows:
            if r.get("topics"):
                continue
            abs_ = (r.get("abstract_excerpt") or "").strip()
            if not abs_:
                continue
            classify_input.append({"id": r["id"], "title": r.get("title", ""), "abstract": abs_})
        if args.limit:
            classify_input = classify_input[:args.limit]
        print(f"\n[classify] {len(classify_input):,} papers (skipped {len(rows) - len(classify_input)} cached/no-abs)")

        if classify_input:
            t0 = time.time()
            await classify_papers_with_llm_async(classify_input)
            print(f"[classify] done in {time.time() - t0:.0f}s")
            row_by_id = {r["id"]: r for r in rows}
            for p in classify_input:
                if not p.get("_topics"):
                    continue
                r = row_by_id[p["id"]]
                regex_domains = set(r.get("domains") or [])
                llm_domains = set(p.get("_domains") or [])
                merged = sorted(regex_domains | llm_domains)
                upd = updates_by_id.setdefault(p["id"], {"id": p["id"]})
                upd["topics"] = p["_topics"]
                upd["domains"] = merged if merged else r.get("domains")
                upd["paper_type"] = p.get("type") or r.get("paper_type")
    else:
        print("[classify] skipped")

    # ── 阶段 2: summarize (summary_zh + summary_en + insights + insights_en) ────
    if not args.skip_summary:
        summary_input = []
        for r in rows:
            has_zh = bool(r.get("summary_zh"))
            has_en = bool(r.get("summary_en"))
            # force 时全部重跑；否则只要 zh 或 en 缺一就要跑
            if not args.force_summary and has_zh and has_en:
                continue
            abs_ = (r.get("abstract_excerpt") or "").strip()
            if not abs_:
                continue
            paper = {"id": r["id"], "title": r.get("title", ""), "abstract": abs_}
            # 把已有翻译塞进去，避免 _already_done 在 llm_summarize 内部判 paper 双语已齐
            # 误判跳过 (我们 force 模式已处理；非 force 模式这里就是缺一)
            summary_input.append(paper)
        if args.limit:
            summary_input = summary_input[:args.limit]
        print(f"\n[summary] {len(summary_input):,} papers (skipped {len(rows) - len(summary_input)} complete/no-abs)"
              + (" [FORCE]" if args.force_summary else ""))

        if summary_input:
            t0 = time.time()
            await summarize_papers_async(summary_input)
            print(f"[summary] done in {time.time() - t0:.0f}s")
            for p in summary_input:
                if not (p.get("summary_zh") or p.get("summary_en")):
                    continue
                upd = updates_by_id.setdefault(p["id"], {"id": p["id"]})
                if p.get("summary_zh"):
                    upd["summary_zh"] = p["summary_zh"]
                if p.get("summary_en"):
                    upd["summary_en"] = p["summary_en"]
                upd["insights"] = p.get("insights") or []
                upd["insights_en"] = p.get("insights_en") or []
    else:
        print("[summary] skipped")

    updates = list(updates_by_id.values())
    print(f"\nPrepared {len(updates):,} updates")

    if args.dry_run:
        print("[dry-run] not writing")
        return
    if not updates:
        print("Nothing to upsert.")
        return

    n = upsert_papers(updates)
    print(f"Upserted {n:,} papers to Supabase")


if __name__ == "__main__":
    asyncio.run(main())
