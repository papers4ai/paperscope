"""arXiv 每日新论文抓取（速览）。

用 arXiv Atom API。rate limit: 官方建议 3s 一次。
只抓最近 N 天、匹配三个领域关键词的论文。
"""

from __future__ import annotations
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import requests

from backend.config import DOMAINS

ARXIV_API = "https://export.arxiv.org/api/query"
DEFAULT_DELAY = 3.0
MAX_RESULTS_PER_PAGE = 100
MAX_RETRIES = 3


def _build_query(keywords: list[str], days: int) -> str:
    """构造 arXiv 查询字符串，关键词 OR，时间窗口 AND。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    date_str = cutoff.strftime("%Y%m%d%H%M")
    kw_expr = " OR ".join(f'all:"{k}"' for k in keywords)
    return f"({kw_expr}) AND submittedDate:[{date_str} TO 999912312359]"


def _fetch_page(query: str, start: int, page_size: int) -> list[dict]:
    params = {
        "search_query": query,
        "start": start,
        "max_results": page_size,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?" + "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            feed = feedparser.parse(r.text)
            return [_parse_entry(e) for e in feed.entries]
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                wait = 10 * (attempt + 1)
                print(f"  [arxiv] timeout, retry {attempt + 1}/{MAX_RETRIES} in {wait}s...")
                time.sleep(wait)
            else:
                raise


def _parse_entry(entry) -> dict:
    arxiv_id = entry.id.rsplit("/", 1)[-1].split("v")[0]
    pdf = next((l.href for l in entry.links if l.get("type") == "application/pdf"), None)
    return {
        "id": f"arxiv:{arxiv_id}",
        "source": "arxiv",
        "source_id": arxiv_id,
        "title": entry.title.strip().replace("\n", " "),
        "authors": [{"name": a.name} for a in entry.get("authors", [])],
        "venue": "arXiv",
        "venue_type": "preprint",
        "venue_tier": "arXiv",
        "year": int(entry.published[:4]) if entry.get("published") else None,
        "published_at": entry.published[:10] if entry.get("published") else None,
        "arxiv_url": entry.link,
        "open_access_pdf": pdf,
        "abstract_excerpt": entry.summary.strip().replace("\n", " ")[:500],
    }


def fetch_domain(domain: str, days: int = 3, max_results: int = 500,
                 delay: float = DEFAULT_DELAY) -> list[dict]:
    """抓取某个领域最近 N 天的 arXiv 新论文。"""
    keywords = DOMAINS[domain]["keywords"]
    query = _build_query(keywords, days)
    results: list[dict] = []
    start = 0
    while start < max_results:
        page = _fetch_page(query, start, MAX_RESULTS_PER_PAGE)
        if not page:
            break
        for p in page:
            p["domains"] = [domain]
        results.extend(page)
        start += MAX_RESULTS_PER_PAGE
        time.sleep(delay)
    return results


def fetch_all_domains(days: int = 3) -> list[dict]:
    """抓取三个领域，按 id 去重（同一篇可能跨域）。"""
    merged: dict[str, dict] = {}
    for domain in DOMAINS:
        for paper in fetch_domain(domain, days=days):
            if paper["id"] in merged:
                existing = merged[paper["id"]]
                existing["domains"] = list(set(existing["domains"] + [domain]))
            else:
                merged[paper["id"]] = paper
    return list(merged.values())


if __name__ == "__main__":
    papers = fetch_all_domains(days=1)
    print(f"Fetched {len(papers)} papers")
    for p in papers[:3]:
        print(" -", p["title"], "|", p["domains"])
