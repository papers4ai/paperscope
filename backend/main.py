"""Paperscope 主入口 — 按命令串联各子流程。

Usage:
  python -m backend.main arxiv-daily              # 每天 arXiv 新论文
  python -m backend.main journals-weekly          # 每周 SS 顶会+期刊
  python -m backend.main pubmed-weekly            # 每周医疗期刊
  python -m backend.main update-citations         # 每周刷引用数快照
"""

from __future__ import annotations
import argparse
import sys
from datetime import date

from backend.db import upsert_papers, snapshot_stats, get_client
from backend.pipeline.classify import enrich_many


def cmd_arxiv_daily(days: int = 2) -> None:
    from backend.scrapers.arxiv_scraper import fetch_all_domains
    print(f"[arxiv] fetching last {days} days...")
    papers = fetch_all_domains(days=days)
    print(f"[arxiv] got {len(papers)} papers")
    papers = enrich_many(papers)
    n = upsert_papers(papers)
    print(f"[arxiv] upserted {n}")


def cmd_journals_weekly(year_from: int | None = None, limit_per_venue: int = 200) -> None:
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
    merged = enrich_many(merged)
    n = upsert_papers(merged)
    print(f"[s2] upserted {n}")


def cmd_pubmed_weekly(days: int = 7) -> None:
    from backend.scrapers.pubmed_scraper import fetch_medical_journals
    papers = fetch_medical_journals(days=days, per_journal=50)
    print(f"[pubmed] got {len(papers)}")
    papers = enrich_many(papers)
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
    p1.add_argument("--days", type=int, default=2)

    p2 = sub.add_parser("journals-weekly")
    p2.add_argument("--year-from", type=int, default=None)
    p2.add_argument("--limit-per-venue", type=int, default=200)

    p3 = sub.add_parser("pubmed-weekly")
    p3.add_argument("--days", type=int, default=7)

    sub.add_parser("update-citations")

    args = ap.parse_args()
    if args.cmd == "arxiv-daily":
        cmd_arxiv_daily(days=args.days)
    elif args.cmd == "journals-weekly":
        cmd_journals_weekly(year_from=args.year_from, limit_per_venue=args.limit_per_venue)
    elif args.cmd == "pubmed-weekly":
        cmd_pubmed_weekly(days=args.days)
    elif args.cmd == "update-citations":
        cmd_update_citations()
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
