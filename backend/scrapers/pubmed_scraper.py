"""PubMed E-utilities 抓取器（医疗 AI 期刊）。

免费，无需 API Key (有 key 可提升到 10 req/s)。
文档: https://www.ncbi.nlm.nih.gov/books/NBK25501/

流程:
  esearch (关键词/期刊查询) → 拿 PMID 列表 → efetch 批量拿详情
"""

from __future__ import annotations
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

from backend.config import VENUES

load_dotenv()

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
API_KEY = os.environ.get("PUBMED_API_KEY")
# Without API key: max 3 req/s; use 1s to stay safely under the limit.
# With API key: max 10 req/s; 0.12s is fine.
DELAY = 0.12 if API_KEY else 1.0
BATCH_FETCH = 100


def _params(extra: dict) -> dict:
    p = {"tool": "paperscope", "email": "admin@paperscope.dev"}
    if API_KEY:
        p["api_key"] = API_KEY
    p.update(extra)
    return p


def _get_with_retry(url: str, params: dict, timeout: int = 30, max_retries: int = 4) -> requests.Response:
    """GET with exponential backoff on 429 / 5xx."""
    for attempt in range(max_retries):
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 429 or r.status_code >= 500:
            wait = 2 ** attempt * 2  # 2, 4, 8, 16 seconds
            print(f"  PubMed {r.status_code} — retrying in {wait}s (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


def esearch(term: str, days: int = 7, retmax: int = 500) -> list[str]:
    """搜 PubMed，返回 PMID 列表。"""
    r = _get_with_retry(
        f"{EUTILS}/esearch.fcgi",
        params=_params({
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": retmax,
            "datetype": "pdat",
            "reldate": days,
            "sort": "pub_date",
        }),
        timeout=30,
    )
    return r.json().get("esearchresult", {}).get("idlist", [])


def efetch(pmids: list[str]) -> list[dict]:
    """批量拉论文详情 (XML)。"""
    if not pmids:
        return []
    results: list[dict] = []
    for i in range(0, len(pmids), BATCH_FETCH):
        batch = pmids[i : i + BATCH_FETCH]
        r = _get_with_retry(
            f"{EUTILS}/efetch.fcgi",
            params=_params({
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
            }),
            timeout=60,
        )
        r.raise_for_status()
        results.extend(_parse_pubmed_xml(r.text))
        time.sleep(DELAY)
    return results


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    papers = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID")
        title = "".join(art.find(".//ArticleTitle").itertext()).strip() if art.find(".//ArticleTitle") is not None else ""
        abstract_parts = [
            "".join(a.itertext()) for a in art.findall(".//Abstract/AbstractText")
        ]
        abstract = " ".join(abstract_parts).strip()
        journal = art.findtext(".//Journal/Title") or ""
        year = art.findtext(".//JournalIssue/PubDate/Year")
        month = art.findtext(".//JournalIssue/PubDate/Month") or "01"
        day = art.findtext(".//JournalIssue/PubDate/Day") or "01"
        pub_date = _normalize_date(year, month, day)
        doi = art.findtext(".//ArticleId[@IdType='doi']")

        authors = []
        for a in art.findall(".//Author"):
            last = a.findtext("LastName") or ""
            fore = a.findtext("ForeName") or ""
            name = f"{fore} {last}".strip()
            aff = a.findtext(".//Affiliation")
            if name:
                authors.append({"name": name, "affiliation": aff})

        from backend.config import lookup_venue
        venue_cfg = lookup_venue(journal)

        papers.append({
            "id": f"pmid:{pmid}",
            "source": "pubmed",
            "source_id": pmid,
            "title": title,
            "authors": authors,
            "venue": venue_cfg["name"] if venue_cfg else journal,
            "venue_type": "journal",
            "venue_tier": venue_cfg["tier"] if venue_cfg else None,
            "year": int(year) if year and year.isdigit() else None,
            "published_at": pub_date,
            "doi": doi,
            "open_access_pdf": None,  # PubMed 不直接给 PDF
            "domains": ["medical_ai"],
            "abstract_excerpt": abstract[:500] if abstract else None,
        })
    return papers


_MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}


def _normalize_date(year: str | None, month: str, day: str) -> str | None:
    if not year or not year.isdigit():
        return None
    m = month if month.isdigit() else _MONTH_MAP.get(month[:3], "01")
    d = day if day.isdigit() else "01"
    try:
        return datetime(int(year), int(m), int(d)).strftime("%Y-%m-%d")
    except ValueError:
        return f"{year}-01-01"


def fetch_medical_journals(days: int = 7, per_journal: int = 50) -> list[dict]:
    """抓取白名单中 medical_ai 期刊最近 N 天的论文。"""
    journals = [
        (name, cfg) for name, cfg in VENUES.items()
        if "medical_ai" in cfg["domains"] and cfg["type"] == "journal"
    ]
    all_papers: dict[str, dict] = {}
    for name, _cfg in journals:
        term = f'"{name}"[Journal]'
        pmids = esearch(term, days=days, retmax=per_journal)
        if not pmids:
            continue
        for paper in efetch(pmids):
            all_papers[paper["id"]] = paper
        time.sleep(DELAY)
    return list(all_papers.values())


if __name__ == "__main__":
    papers = fetch_medical_journals(days=14, per_journal=10)
    print(f"Fetched {len(papers)} medical papers")
    for p in papers[:5]:
        print(" -", p["venue"], "|", p["title"][:80])
