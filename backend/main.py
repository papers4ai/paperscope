"""Paperscope 主入口 — 按命令串联各子流程。

Usage:
  python -m backend.main arxiv-daily              # 每天 arXiv 新论文
  python -m backend.main journals-weekly          # 每周 SS 顶会+期刊
  python -m backend.main pubmed-weekly            # 每周医疗期刊
  python -m backend.main update-citations         # 每周刷引用数快照
"""

from __future__ import annotations
import argparse
import asyncio
import os
import sys
from datetime import date

from backend.db import upsert_papers, snapshot_stats, get_client
from backend.pipeline.classify import enrich_many_async


async def cmd_arxiv_daily(days: int = 3,
                          date_from: str | None = None,
                          date_to: str | None = None,
                          window_days: int = 7) -> None:
    """抓 arXiv 论文 → LLM 判定 → 只保留属于 world_model/physical_ai/medical_ai 的。

    使用学科类别 (cs.AI/cs.LG/cs.CV/cs.RO/cs.NE/eess.IV/q-bio.QM) 大范围拉取候选，
    LLM 在 enrich_many_async 内部判断 _domains，本函数过滤掉 _domains 空的论文。
    """
    from backend.scrapers.arxiv_scraper import fetch_by_categories
    from datetime import datetime, timedelta, timezone

    if not date_from:
        date_from = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
    print(f"[arxiv] fetching {date_from} → {date_to or 'today'} (by category, {window_days}d windows)")

    papers = fetch_by_categories(date_from=date_from, date_to=date_to, window_days=window_days)
    print(f"[arxiv] candidate pool: {len(papers)} papers")

    papers = await enrich_many_async(papers)

    # LLM 判 _domains 为空 → 不属于三个领域 → 丢弃
    kept = [p for p in papers if p.get("domains")]
    dropped = len(papers) - len(kept)
    print(f"[arxiv] after LLM filter: {len(kept)} kept, {dropped} dropped (not relevant)")

    # AI 中文解读（summary_zh + insights）—— 复用 cleaning/llm_summarize
    if (os.environ.get("LLM_API_KEY") or os.environ.get("LLM_API_KEYS")) and kept:
        from cleaning.llm_summarize import summarize_papers_async
        llm_input = [
            {"id": p["id"], "title": p.get("title", ""),
             "abstract": p.get("abstract_excerpt") or ""}
            for p in kept if (p.get("abstract_excerpt") or "").strip()
        ]
        if llm_input:
            print(f"[arxiv] generating AI summaries for {len(llm_input)} papers...")
            await summarize_papers_async(llm_input)
            id_to_sum = {p["id"]: p for p in llm_input if p.get("summary_zh")}
            for p in kept:
                hit = id_to_sum.get(p["id"])
                if hit:
                    p["summary_zh"] = hit["summary_zh"]
                    p["insights"] = hit.get("insights", [])
            print(f"[arxiv] summaries generated for {len(id_to_sum)} papers")

    n = upsert_papers(kept)
    print(f"[arxiv] upserted {n}")


async def cmd_journals_weekly(year_from: int | None = None, limit_per_venue: int = 200) -> None:
    from backend.scrapers.semantic_scholar_scraper import search_by_venue
    from backend.config import VENUES
    year_from = year_from or (date.today().year - 1)
    all_papers: dict[str, dict] = {}
    for name, cfg in VENUES.items():
        print(f"[s2] venue={name} ({cfg['tier']}) ...")
        try:
            papers = search_by_venue(name, year_from=year_from, limit=limit_per_venue)
        except Exception as e:
            print(f"  !! {name} 失败: {e}")
            continue
        for p in papers:
            all_papers[p["id"]] = p
        print(f"  got {len(papers)}")
    merged = list(all_papers.values())
    merged = await enrich_many_async(merged)
    n = upsert_papers(merged)
    print(f"[s2] upserted {n}")


async def cmd_pubmed_weekly(days: int = 7) -> None:
    from backend.scrapers.pubmed_scraper import fetch_medical_journals
    papers = fetch_medical_journals(days=days, per_journal=50)
    print(f"[pubmed] got {len(papers)}")
    papers = await enrich_many_async(papers)
    n = upsert_papers(papers)
    print(f"[pubmed] upserted {n}")


def cmd_update_citations(batch: int = 500) -> None:
    """拉全表 s2 论文的 paperId，批量刷新引用数 + 写快照。"""
    from backend.scrapers.semantic_scholar_scraper import fetch_citations
    client = get_client()
    # 只更新 s2 来源（arxiv/pubmed 没 citationCount）
    rows = client.table("papers").select("id").eq("source", "s2").execute().data
    ids = [r["id"] for r in rows]
    print(f"[citations] refreshing {len(ids)} papers")

    today = date.today().isoformat()
    for i in range(0, len(ids), batch):
        chunk = ids[i : i + batch]
        cite_map = fetch_citations(chunk)
        # 更新 papers 表 + 写快照
        updates = [{"id": pid, "citation_count": c} for pid, c in cite_map.items()]
        if updates:
            client.table("papers").upsert(updates, on_conflict="id").execute()
        snapshot_stats([
            {"paper_id": pid, "snapshot_date": today, "citation_count": c}
            for pid, c in cite_map.items()
        ])
        print(f"  batch {i // batch + 1}: updated {len(cite_map)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("arxiv-daily")
    p1.add_argument("--days", type=int, default=3)
    p1.add_argument("--date-from", default=None, help="开始日期 YYYY-MM-DD，填此项时忽略 --days")
    p1.add_argument("--date-to",   default=None, help="结束日期 YYYY-MM-DD（默认今天）")
    p1.add_argument("--window-days", type=int, default=7,
                    help="切窗粒度（默认 7 天/窗）。密集月份用 3，稀疏年份用 30")

    p2 = sub.add_parser("journals-weekly")
    p2.add_argument("--year-from", type=int, default=None)
    p2.add_argument("--limit-per-venue", type=int, default=200)

    p3 = sub.add_parser("pubmed-weekly")
    p3.add_argument("--days", type=int, default=7)

    sub.add_parser("update-citations")

    args = ap.parse_args()
    if args.cmd == "arxiv-daily":
        asyncio.run(cmd_arxiv_daily(days=args.days, date_from=args.date_from,
                                    date_to=args.date_to, window_days=args.window_days))
    elif args.cmd == "journals-weekly":
        asyncio.run(cmd_journals_weekly(year_from=args.year_from, limit_per_venue=args.limit_per_venue))
    elif args.cmd == "pubmed-weekly":
        asyncio.run(cmd_pubmed_weekly(days=args.days))
    elif args.cmd == "update-citations":
        cmd_update_citations()
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
