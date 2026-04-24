"""热榜 / 新星论文计算。

数据基于 paper_stats 表 (周引用快照)。
  - 热榜: 本周引用增长 = 本周 citation - 上周 citation, 排序 desc
  - 新星: published < 6 个月 且 citation > 同期均值 × 2
"""

from __future__ import annotations
from datetime import date, timedelta

from backend.db import get_client


def compute_weekly_trending(domain: str | None = None, limit: int = 20) -> list[dict]:
    """按引用增长率排热榜。"""
    client = get_client()
    today = date.today()
    last_week = today - timedelta(days=7)

    # 取最近两次快照对比
    q = (
        client.table("paper_stats")
        .select("paper_id, snapshot_date, citation_count")
        .gte("snapshot_date", (today - timedelta(days=14)).isoformat())
        .execute()
    )
    snapshots: dict[str, dict[str, int]] = {}
    for row in q.data:
        snapshots.setdefault(row["paper_id"], {})[row["snapshot_date"]] = row["citation_count"]

    deltas = []
    for pid, by_date in snapshots.items():
        dates_sorted = sorted(by_date.keys())
        if len(dates_sorted) < 2:
            continue
        prev = by_date[dates_sorted[-2]]
        curr = by_date[dates_sorted[-1]]
        delta = curr - prev
        if delta <= 0:
            continue
        growth = delta / max(prev, 1)
        deltas.append({"paper_id": pid, "delta": delta, "growth": growth})

    deltas.sort(key=lambda r: (r["growth"], r["delta"]), reverse=True)
    top_ids = [d["paper_id"] for d in deltas[: limit * 3]]

    if not top_ids:
        return []

    papers_q = client.table("papers").select("*").in_("id", top_ids)
    if domain:
        papers_q = papers_q.contains("domains", [domain])
    papers = papers_q.execute().data

    by_id = {p["id"]: p for p in papers}
    ordered = []
    for d in deltas:
        p = by_id.get(d["paper_id"])
        if p:
            ordered.append({**p, "citation_delta": d["delta"], "growth": d["growth"]})
        if len(ordered) >= limit:
            break
    return ordered


def compute_rising_stars(domain: str | None = None, months: int = 6, limit: int = 20) -> list[dict]:
    """发表 < months 个月，引用超同期均值 × 2。"""
    client = get_client()
    cutoff = (date.today() - timedelta(days=30 * months)).isoformat()
    q = client.table("papers").select("*").gte("published_at", cutoff)
    if domain:
        q = q.contains("domains", [domain])
    papers = q.execute().data
    if not papers:
        return []

    avg = sum(p["citation_count"] for p in papers) / len(papers)
    stars = [p for p in papers if p["citation_count"] >= avg * 2]
    stars.sort(key=lambda p: p["citation_count"], reverse=True)
    return stars[:limit]
