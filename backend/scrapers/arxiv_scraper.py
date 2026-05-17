"""arXiv 每日新论文抓取（速览）。

用 arXiv Atom API。rate limit: 官方建议 3s 一次。
只抓最近 N 天、匹配三个领域关键词的论文。
"""

from __future__ import annotations
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import requests

from backend.config import DOMAINS
from backend.config.domains import get_keywords

ARXIV_API = "https://export.arxiv.org/api/query"
DEFAULT_DELAY = 3.0
MAX_RESULTS_PER_PAGE = 100
MAX_RETRIES = 5
REQUEST_TIMEOUT = 120   # arXiv 有时响应慢，60s 不够


def _build_query(keywords: list[str], days: int = 3,
                 date_from: str | None = None, date_to: str | None = None) -> str:
    """构造 arXiv 查询字符串，关键词 OR，时间窗口 AND。

    优先使用 date_from/date_to（YYYY-MM-DD），否则按 days 回溯。
    """
    if date_from:
        from_str = date_from.replace("-", "") + "0000"
        to_str   = (date_to.replace("-", "") + "2359") if date_to else "999912312359"
    else:
        cutoff   = datetime.now(timezone.utc) - timedelta(days=days)
        from_str = cutoff.strftime("%Y%m%d%H%M")
        to_str   = "999912312359"
    kw_expr = " OR ".join(f'all:"{k}"' for k in keywords)
    return f"({kw_expr}) AND submittedDate:[{from_str} TO {to_str}]"


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
            r = requests.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code == 429:
                wait = 60 * (attempt + 1)
                print(f"  [arxiv] 429 rate limit, retry {attempt + 1}/{MAX_RETRIES} in {wait}s...", flush=True)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                # arxiv 偶发 503/504，退避重试
                wait = 30 * (attempt + 1)
                print(f"  [arxiv] {r.status_code} server error, retry {attempt + 1}/{MAX_RETRIES} in {wait}s...", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            feed = feedparser.parse(r.text)
            return [_parse_entry(e) for e in feed.entries]
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = 30 * (attempt + 1)
                print(f"  [arxiv] {type(e).__name__}, retry {attempt + 1}/{MAX_RETRIES} in {wait}s...", flush=True)
                time.sleep(wait)
            else:
                print(f"  [arxiv] giving up after {MAX_RETRIES} attempts: {e}", flush=True)
                return []
        except requests.exceptions.HTTPError as e:
            # 其他 HTTP 错误（4xx 等）不重试，但也不崩溃，返回空页
            print(f"  [arxiv] HTTPError, giving up: {e}", flush=True)
            return []
    return []


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
        "abstract_excerpt": entry.summary.strip().replace("\n", " "),
    }


def fetch_domain(domain: str, days: int = 3, max_results: int = 2000,
                 delay: float = DEFAULT_DELAY,
                 date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """抓取某个领域最近 N 天（或指定日期段）的 arXiv 新论文。"""
    keywords = get_keywords(domain)
    query = _build_query(keywords, days, date_from=date_from, date_to=date_to)
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


def fetch_all_domains(days: int = 3,
                      date_from: str | None = None,
                      date_to: str | None = None) -> list[dict]:
    """旧策略：按关键词 OR 抓取三个领域。保留作为 fallback。"""
    merged: dict[str, dict] = {}
    domain_list = list(DOMAINS.keys())
    for i, domain in enumerate(domain_list):
        for paper in fetch_domain(domain, days=days, date_from=date_from, date_to=date_to):
            if paper["id"] in merged:
                existing = merged[paper["id"]]
                existing["domains"] = list(set(existing["domains"] + [domain]))
            else:
                merged[paper["id"]] = paper
        if i < len(domain_list) - 1:
            time.sleep(10)
    return list(merged.values())


# ════════════════════════════════════════════════════════════════════════════
# 新策略：按 arxiv 学科类别抓取（覆盖广），LLM 在下游做语义过滤
# ════════════════════════════════════════════════════════════════════════════

# 三大领域涉及的 arxiv 学科类别（取并集）
DEFAULT_CATEGORIES = [
    "cs.AI",       # 人工智能（通用）
    "cs.LG",       # 机器学习
    "cs.CV",       # 计算机视觉（→ world_model 视频生成/NeRF；medical_ai 医学影像）
    "cs.RO",       # 机器人（→ physical_ai）
    "cs.NE",       # 神经网络
    "eess.IV",     # 图像/视频信号处理（→ medical_ai 医学影像）
    "q-bio.QM",    # 定量生物方法（→ medical_ai）
]


def _build_category_query(categories: list[str],
                          date_from: str, date_to: str | None = None) -> str:
    """构造 arxiv 学科类别 + 时间窗的查询字符串。"""
    from_str = date_from.replace("-", "") + "0000"
    to_str   = (date_to.replace("-", "") + "2359") if date_to else "999912312359"
    cat_expr = " OR ".join(f"cat:{c}" for c in categories)
    return f"({cat_expr}) AND submittedDate:[{from_str} TO {to_str}]"


def _split_windows(date_from: str, date_to: str | None = None,
                   window_days: int = 7) -> list[tuple[str, str]]:
    """把 [date_from, date_to] 按 window_days 切窗（含两端）。"""
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = (datetime.strptime(date_to, "%Y-%m-%d").date()
           if date_to else datetime.now(timezone.utc).date())
    windows = []
    cur = start
    while cur <= end:
        win_end = min(cur + timedelta(days=window_days - 1), end)
        windows.append((cur.isoformat(), win_end.isoformat()))
        cur = win_end + timedelta(days=1)
    return windows


def fetch_by_categories(date_from: str,
                        date_to: str | None = None,
                        categories: list[str] | None = None,
                        window_days: int = 7,
                        max_per_window: int = 5000,
                        delay: float = DEFAULT_DELAY) -> list[dict]:
    """按 arxiv 学科类别 + 时间窗切窗抓取，带 tqdm 进度条。"""
    import sys
    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    categories = categories or DEFAULT_CATEGORIES
    windows = _split_windows(date_from, date_to, window_days=window_days)
    print(f"  [arxiv] {len(windows)} windows × {window_days}d, cats={','.join(categories)}", flush=True)

    is_tty = sys.stderr.isatty()
    pbar = (
        tqdm(
            total=len(windows),
            desc="arxiv fetch",
            unit="win",
            dynamic_ncols=True,
            disable=False,
            mininterval=10 if not is_tty else 0.1,  # 非 tty 每 10 秒追加一行
            ascii=not is_tty,
            file=sys.stderr,
        )
        if tqdm is not None else None
    )

    # 增量保存候选池：每 5 个窗写一次 /tmp/arxiv_candidates_partial.json，避免崩溃丢全部
    # 文件结构: {"completed_windows": ["2023-01-01_2023-01-07", ...], "papers": [...]}
    # 启动时若存在且 categories/window_days 与本次一致，自动跳过已完成的窗
    SNAPSHOT_EVERY = 5
    snapshot_path = "/tmp/arxiv_candidates_partial.json"
    cache_key = f"{','.join(categories)}|{window_days}d"

    merged: dict[str, dict] = {}
    completed: set[str] = set()
    if os.path.exists(snapshot_path):
        try:
            import json as _json
            with open(snapshot_path, encoding="utf-8") as f:
                saved = _json.load(f)
            if isinstance(saved, dict) and saved.get("cache_key") == cache_key:
                completed = set(saved.get("completed_windows", []))
                for p in saved.get("papers", []):
                    if p.get("id"):
                        merged[p["id"]] = p
                if completed:
                    print(f"  [arxiv] RESUME: skipping {len(completed)} completed windows "
                          f"({len(merged):,} papers in pool)", flush=True)
            else:
                print(f"  [arxiv] partial file exists but cache_key mismatch, starting fresh", flush=True)
        except Exception as e:
            print(f"  [arxiv] partial file unreadable, starting fresh: {e}", flush=True)

    for wi, (win_from, win_to) in enumerate(windows):
        win_key = f"{win_from}_{win_to}"
        if win_key in completed:
            if pbar is not None:
                pbar.set_postfix_str(f"{win_from}~{win_to}: SKIP (cached) (pool: {len(merged):,})")
                pbar.update(1)
            continue

        try:
            query = _build_category_query(categories, win_from, win_to)
            start = 0
            win_count = 0
            while start < max_per_window:
                page = _fetch_page(query, start, MAX_RESULTS_PER_PAGE)
                if not page:
                    break
                for p in page:
                    p.setdefault("domains", [])
                    if p["id"] not in merged:
                        merged[p["id"]] = p
                win_count += len(page)
                start += MAX_RESULTS_PER_PAGE
                time.sleep(delay)
            cap_hit = " (HIT CAP)" if win_count >= max_per_window else ""
        except Exception as e:
            # 单窗失败不影响其他窗：记录错误后继续
            cap_hit = f" (ERROR: {type(e).__name__})"
            win_count = 0
            print(f"  [arxiv] window {win_from}~{win_to} failed, skipping: {e}", flush=True)

        # 记录此窗已完成（即使 win_count==0，也算尝试过）
        completed.add(win_key)

        if pbar is not None:
            pbar.set_postfix_str(f"{win_from}~{win_to}: +{win_count}{cap_hit} (pool: {len(merged):,})")
            pbar.update(1)
        else:
            print(f"  [arxiv] [{wi+1}/{len(windows)}] {win_from}~{win_to}: {win_count}{cap_hit}", flush=True)

        # 每 N 窗增量保存（防 OOM/网络异常导致全部丢失）
        if (wi + 1) % SNAPSHOT_EVERY == 0 or (wi + 1) == len(windows):
            try:
                tmp = snapshot_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    import json as _json
                    _json.dump({
                        "cache_key": cache_key,
                        "completed_windows": sorted(completed),
                        "papers": list(merged.values()),
                    }, f, ensure_ascii=False, separators=(",", ":"))
                os.replace(tmp, snapshot_path)
            except Exception as e:
                print(f"  [arxiv] snapshot save failed (continuing): {e}", flush=True)

    if pbar is not None:
        pbar.close()
    return list(merged.values())


if __name__ == "__main__":
    papers = fetch_by_categories(date_from="2026-05-10")
    print(f"Fetched {len(papers)} papers")
    for p in papers[:3]:
        print(" -", p["title"])
