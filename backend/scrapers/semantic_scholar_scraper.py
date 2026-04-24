"""Semantic Scholar Graph API 抓取器。

核心数据源：会议/期刊论文 + 引用数 + 作者机构 + Fields of Study。
免费 rate: 100 req / 5 min；有 API Key 可到 1000 req / 5 min。

本文件实现：
  1. search_by_venue: 按 venue 白名单抓取
  2. fetch_citations: 批量更新已有论文的引用数
  3. fetch_paper_details: 拉取单篇完整详情（前端实时调用也可用）
"""

from __future__ import annotations
import os
import time
from typing import Iterable

import requests
from dotenv import load_dotenv

from backend.config import VENUES, lookup_venue

load_dotenv()

S2_BASE = "https://api.semanticscholar.org/graph/v1"
S2_API_KEY = os.environ.get("S2_API_KEY")
DELAY = 1.2 if S2_API_KEY else 3.5  # 有 key 加速

PAPER_FIELDS = ",".join([
    "paperId", "externalIds", "title", "abstract", "year",
    "publicationDate", "venue", "publicationVenue",
    "authors.name", "authors.authorId", "authors.affiliations",
    "citationCount", "referenceCount", "fieldsOfStudy",
    "openAccessPdf", "isOpenAccess",
])


def _headers() -> dict:
    h = {"Accept": "application/json"}
    if S2_API_KEY:
        h["x-api-key"] = S2_API_KEY
    return h


def _get(path: str, params: dict | None = None, retries: int = 3) -> dict:
    url = f"{S2_BASE}{path}"
    for attempt in range(retries):
        r = requests.get(url, params=params, headers=_headers(), timeout=30)
        if r.status_code == 429:
            time.sleep(2 ** attempt * 5)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"S2 API failed after {retries} retries: {path}")


def _normalize(item: dict, domains: list[str]) -> dict:
    ext = item.get("externalIds") or {}
    arxiv_id = ext.get("ArXiv")
    doi = ext.get("DOI")
    pid = f"s2:{item['paperId']}"  # 统一用 s2 前缀，arxiv 同篇在 arxiv 抓取器下处理

    venue_name = (item.get("publicationVenue") or {}).get("name") or item.get("venue") or ""
    venue_cfg = lookup_venue(venue_name) if venue_name else None

    abstract = item.get("abstract") or ""
    pdf = (item.get("openAccessPdf") or {}).get("url")

    return {
        "id": pid,
        "source": "s2",
        "source_id": item["paperId"],
        "title": (item.get("title") or "").strip(),
        "authors": [
            {
                "name": a.get("name"),
                "s2_id": a.get("authorId"),
                "affiliation": ", ".join(a.get("affiliations") or []) or None,
            }
            for a in (item.get("authors") or [])
        ],
        "venue": venue_cfg["name"] if venue_cfg else venue_name or None,
        "venue_type": venue_cfg["type"] if venue_cfg else None,
        "venue_tier": venue_cfg["tier"] if venue_cfg else None,
        "year": item.get("year"),
        "published_at": item.get("publicationDate"),
        "citation_count": item.get("citationCount") or 0,
        "reference_count": item.get("referenceCount") or 0,
        "fields_of_study": item.get("fieldsOfStudy") or [],
        "domains": domains,
        "open_access_pdf": pdf,
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
        "doi": doi,
        "abstract_excerpt": abstract[:500] if abstract else None,
    }


def search_by_venue(venue: str, year_from: int, limit: int = 100) -> list[dict]:
    """按 venue 搜索论文。S2 的 bulk search 支持 venue + year 筛选。"""
    cfg = VENUES.get(venue)
    domains = cfg["domains"] if cfg else []
    offset = 0
    out: list[dict] = []
    token = None
    while True:
        params = {
            "query": venue,                # 兜底关键词
            "venue": venue,
            "year": f"{year_from}-",
            "fields": PAPER_FIELDS,
            "limit": min(100, limit - len(out)),
        }
        if token:
            params["token"] = token
        data = _get("/paper/search/bulk", params)
        papers = data.get("data") or []
        for item in papers:
            out.append(_normalize(item, domains))
        token = data.get("token")
        if not token or len(out) >= limit:
            break
        time.sleep(DELAY)
    return out


def fetch_citations(paper_ids: Iterable[str]) -> dict[str, int]:
    """批量拉取引用数。用 /paper/batch 一次最多 500 个。"""
    ids = [pid.split(":", 1)[1] for pid in paper_ids if pid.startswith("s2:")]
    result: dict[str, int] = {}
    for i in range(0, len(ids), 500):
        batch = ids[i : i + 500]
        r = requests.post(
            f"{S2_BASE}/paper/batch",
            params={"fields": "citationCount"},
            json={"ids": batch},
            headers=_headers(),
            timeout=60,
        )
        r.raise_for_status()
        for item in r.json():
            if item and item.get("paperId"):
                result[f"s2:{item['paperId']}"] = item.get("citationCount") or 0
        time.sleep(DELAY)
    return result


def fetch_paper_details(paper_id: str) -> dict:
    """前端点击卡片时调用，拉完整详情 + 引用关系。"""
    pid = paper_id.split(":", 1)[1] if ":" in paper_id else paper_id
    data = _get(
        f"/paper/{pid}",
        params={
            "fields": PAPER_FIELDS
            + ",references.paperId,references.title,references.citationCount,references.year"
            + ",citations.paperId,citations.title,citations.citationCount,citations.year"
        },
    )
    return data


if __name__ == "__main__":
    # 测试：抓 NeurIPS 2024 最近 10 篇
    papers = search_by_venue("NeurIPS", 2024, limit=10)
    for p in papers:
        print(p["citation_count"], "|", p["venue"], "|", p["title"][:80])
