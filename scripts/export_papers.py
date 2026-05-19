#!/usr/bin/env python3
"""从 Supabase 导出 arXiv 论文到 frontend/data/papers_{year}.json（按年增量合并）

用法：
    python scripts/export_papers.py
    python scripts/export_papers.py --dry-run
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import date, timedelta
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "data")
META = os.path.join(DATA_DIR, "meta.json")
START_YEAR = 2023

def get_years() -> list[int]:
    # +1 多包含下一年，防止年底提交的论文被丢弃
    return list(range(START_YEAR, date.today().year + 2))


def local_path(year: int) -> str:
    return os.path.join(DATA_DIR, f"papers_{year}.json")


def strip_prefix(raw_id: str) -> str:
    for prefix in ("arxiv:", "s2:", "pubmed:"):
        if raw_id.startswith(prefix):
            return raw_id[len(prefix):]
    return raw_id


def to_frontend(row: dict) -> dict:
    from cleaning.domain_filter import filter_domains
    published = (row.get("published_at") or "")[:10]
    month = int(published[5:7]) if len(published) >= 7 else None
    code_links = row.get("code_links") or []
    code_url = code_links[0] if isinstance(code_links, list) and code_links else ""
    tasks = row.get("tasks") or []
    topics = row.get("topics") or []
    title = row.get("title", "")
    # 启发式过滤 LLM 错贴标签：domain 必须有 task 或 keyword 锚点
    domains = filter_domains(row.get("domains") or [], tasks, title, topics)
    return {
        "id": strip_prefix(row["id"]),
        "title": title,
        "abstract": row.get("abstract_excerpt") or "",
        "authors": row.get("authors") or [],
        "published": published,
        "year": row.get("year"),
        "month": month,
        "pdf_url": row.get("open_access_pdf") or "",
        "arxiv_url": row.get("arxiv_url") or "",
        "code": code_url,
        "has_code": bool(code_url),
        "type": row.get("paper_type") or "",
        "_domains": domains,
        "_tasks": tasks,
        "_topics": topics,
        "summary_zh": row.get("summary_zh") or "",
        "summary_en": row.get("summary_en") or "",
        "insights": row.get("insights") or [],
        "insights_en": row.get("insights_en") or [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--since", default=None,
                    help="只导出 published_at >= 这个日期的论文 (YYYY-MM-DD)。"
                         "默认 today - --since-days；workflow 手动 backfill 时应传 fetch 的 date_from。")
    ap.add_argument("--since-days", type=int, default=8,
                    help="--since 未指定时，回看 N 天 (默认 8，覆盖 --days 7 的 deep fetch + 1 天缓冲)")
    args = ap.parse_args()

    from backend.db import get_client
    from cleaning.domain_filter import filter_domains
    client = get_client()

    # 加载现有本地各年份文件
    YEARS = get_years()
    local_by_year: dict[int, list] = {}
    seen: set[str] = set()
    # id -> (year, paper_dict) 用来 in-place 更新已存在的本地论文 (AI 解读字段)
    local_idx: dict[str, tuple[int, dict]] = {}
    # 每次 export 都对存量做启发式过滤,把锚点不匹配的 domain 剔除。
    # 剔除后 _domains 仍非空的保留;变空的直接从数据集中丢弃 (本来就不属于
    # 我们关注的三大领域,留着只是噪声 + 让 dashboard 总数虚高)。
    # 这样未来 prompt/锚点规则改进时,无需手动跑 filter_false_domains.py。
    domain_swept_years: set[int] = set()
    domain_sweep_stripped = 0   # _domains 被剪短但还非空的
    domain_sweep_dropped = 0    # _domains 变空被丢弃的
    for year in YEARS:
        path = local_path(year)
        if not os.path.exists(path):
            local_by_year[year] = []
            continue
        papers = json.load(open(path, encoding="utf-8"))
        kept: list[dict] = []
        for p in papers:
            pid = p.get("id")
            orig_doms = p.get("_domains") or []
            if orig_doms:
                new_doms = filter_domains(
                    orig_doms,
                    p.get("_tasks") or [],
                    p.get("title") or "",
                    p.get("_topics") or [],
                )
                if not new_doms:
                    # 不再属于任何关注领域 → 直接丢
                    domain_sweep_dropped += 1
                    domain_swept_years.add(year)
                    continue
                if new_doms != orig_doms:
                    p["_domains"] = new_doms
                    domain_sweep_stripped += 1
                    domain_swept_years.add(year)
            else:
                # 历史遗留: 已经没 domain 的论文也清理掉
                domain_sweep_dropped += 1
                domain_swept_years.add(year)
                continue
            if pid:
                seen.add(pid)
                local_idx[pid] = (year, p)
            kept.append(p)
        local_by_year[year] = kept
    total_local = sum(len(v) for v in local_by_year.values())
    print(f"Local: {total_local} papers across {len(YEARS)} year files")
    if domain_sweep_stripped or domain_sweep_dropped:
        print(f"  domain sweep: stripped tags on {domain_sweep_stripped} papers, "
              f"dropped {domain_sweep_dropped} papers with no surviving domain")

    # 从 Supabase 拉取 since 之后的 arxiv 论文
    since = args.since or (date.today() - timedelta(days=args.since_days)).isoformat()
    remote: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        rows = (
            client.table("papers")
            .select("id,title,abstract_excerpt,authors,published_at,year,open_access_pdf,arxiv_url,code_links,paper_type,domains,tasks,topics,summary_zh,summary_en,insights,insights_en")
            .eq("source", "arxiv")
            .gte("published_at", since)
            .order("published_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
        )
        if not rows:
            break
        remote.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    print(f"Supabase: {len(remote)} arxiv papers (since {since})")
    # 按 published_at 拆开，方便排查：是 Supabase 没拿到新论文，还是 export 把它们丢了
    from collections import Counter
    by_date = Counter((r.get("published_at") or "")[:10] for r in remote)
    for d in sorted(by_date, reverse=True)[:7]:
        print(f"  {d}: {by_date[d]} papers in Supabase")
    no_domain = sum(1 for r in remote if not (r.get("domains") or []))
    if no_domain:
        print(f"  ! {no_domain} Supabase rows have empty domains (will be skipped)")

    # AI 解读字段 —— 已存在的本地论文也要更新（不动手动标签、domains 等其它字段）
    AI_FIELDS = ("summary_zh", "summary_en", "insights", "insights_en")

    new_by_year: dict[int, list] = defaultdict(list)
    updated_years: set[int] = set(domain_swept_years)  # domain sweep 改过的也算需重写
    refreshed_count = 0
    for r in remote:
        pid = strip_prefix(r["id"])
        domains = r.get("domains") or []
        if pid in seen:
            # 论文已在本地：补/更新 AI 解读字段
            year, lp = local_idx[pid]
            changed = False
            for f in AI_FIELDS:
                v = r.get(f)
                if v is None:
                    continue
                # 空值不覆盖已有值
                if isinstance(v, str) and not v.strip():
                    continue
                if isinstance(v, list) and not v:
                    continue
                if lp.get(f) != v:
                    lp[f] = v
                    changed = True
            if changed:
                updated_years.add(year)
                refreshed_count += 1
            continue
        if not domains:
            continue
        p = to_frontend(r)
        year = p.get("year") or date.today().year
        # 超出范围时落回当前年，不丢弃
        if year not in YEARS:
            year = date.today().year
        new_by_year[year].append(p)
        updated_years.add(year)

    total_new = sum(len(v) for v in new_by_year.values())
    print(f"New: {total_new} papers to append, refreshed AI fields on {refreshed_count} existing")

    if (not total_new and not refreshed_count
            and not domain_sweep_stripped and not domain_sweep_dropped):
        print("Nothing to add or update.")
        return 0

    if args.dry_run:
        for year in sorted(updated_years):
            print(f"  {year}: +{len(new_by_year[year])} new, ~{sum(1 for p in local_by_year[year] if p.get('id') in seen)} touched")
        return 0

    latest = ""
    for year in YEARS:
        if year not in updated_years:
            continue
        merged = local_by_year[year] + new_by_year[year]
        path = local_path(year)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
        size_mb = os.path.getsize(path) / 1024 / 1024
        print(f"  papers_{year}.json: {len(merged)} papers ({size_mb:.1f} MB)"
              + (f" [+{len(new_by_year[year])} new]" if new_by_year[year] else " [AI refresh only]"))
        yr_latest = max((p.get("published") or "" for p in merged if p.get("published")), default="")
        if yr_latest > latest:
            latest = yr_latest

    if latest:
        with open(META, "w", encoding="utf-8") as f:
            json.dump({"last_updated": latest[:10], "years": YEARS}, f)
        print(f"Updated meta.json: last_updated={latest[:10]}, years={YEARS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
