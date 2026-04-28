#!/usr/bin/env python3
"""把 output/papers_curated.json 按领域（+ world_model 按年份）拆分到 frontend/data/

输出文件：
  papers_curated_world_model_2023.json   (~28 MB)
  papers_curated_world_model_2024.json   (~39 MB)
  papers_curated_world_model_2025.json   (~35 MB)
  papers_curated_world_model_2026.json   (~15 MB)
  papers_curated_physical_ai.json        (~37 MB)
  papers_curated_medical_ai.json         (~67 MB)

用法：
    python scripts/sync_curated.py
    python scripts/sync_curated.py --local output/papers_curated.json
    python scripts/sync_curated.py --dry-run
"""
import argparse, json, os, sys, urllib.request
from collections import Counter

REMOTE = "https://raw.githubusercontent.com/Jefferyzhifeng/Paperscope-hub/main/output/papers_curated.json"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "data")

DOMAINS = ["world_model", "physical_ai", "medical_ai"]
START_YEAR = 2023

def get_years() -> list:
    from datetime import date
    return list(range(START_YEAR, date.today().year + 1))

KEEP = [
    "id", "title", "authors", "published", "year", "month",
    "pdf_url", "arxiv_url", "code", "has_code", "type",
    "_domains", "_tasks", "venue", "venue_tier", "citation_count",
]


def slim(p: dict) -> dict:
    out = {k: p[k] for k in KEEP if k in p and p[k] is not None}
    raw_abs = (p.get("abstract") or "").strip()
    if raw_abs:
        out["abstract"] = raw_abs
    return out


def write_file(path: str, plist: list, dry_run: bool):
    plist.sort(key=lambda x: x.get("citation_count", 0), reverse=True)
    raw = json.dumps(plist, ensure_ascii=False, separators=(",", ":"))
    size_mb = len(raw.encode()) / 1024 / 1024
    top_venues = Counter(p.get("venue") for p in plist).most_common(3)
    label = os.path.basename(path)
    print(f"  {label}: {len(plist)} 篇  {size_mb:.1f} MB  top={top_venues}")
    if not dry_run:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(raw)
        os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="本地 papers_curated.json 路径")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.local:
        print(f"Loading from {args.local} ...")
        papers = json.load(open(args.local, encoding="utf-8"))
    else:
        print(f"Fetching {REMOTE} ...")
        with urllib.request.urlopen(REMOTE) as r:
            papers = json.load(r)

    papers = [p for p in papers if (p.get("year") or 0) >= 2023 and p.get("venue")]
    print(f"Total after filter (2023+, has venue): {len(papers)}\n")

    # ── 三个领域全部按年份拆分 ────────────────────────────────────────────────
    YEARS = get_years()
    for domain in DOMAINS:
        by_year: dict = {y: [] for y in YEARS}
        for p in papers:
            if domain not in (p.get("_domains") or []):
                continue
            year = p.get("year")
            if year in by_year:
                by_year[year].append(slim(p))
        for year in YEARS:
            path = os.path.join(DATA_DIR, f"papers_curated_{domain}_{year}.json")
            write_file(path, by_year[year], args.dry_run)

    if args.dry_run:
        print("\n[dry-run] 未写文件")
    else:
        print(f"\n✓ 写出文件到 {DATA_DIR}")


if __name__ == "__main__":
    sys.exit(main())
