#!/usr/bin/env python3
"""把 output/papers_curated.json 按 domain + year + month 拆分到 frontend/data/

输出文件：
  papers_curated_{domain}_{year}_{month:02d}.json   (每个 ~1-3 MB)
  papers_curated_manifest.json                       (前端按此索引加载)

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
    "_domains", "_tasks", "_topics", "venue", "venue_tier", "citation_count",
    "summary_zh", "summary_en", "insights", "insights_en",
]


def slim(p: dict) -> dict:
    out = {k: p[k] for k in KEEP if k in p and p[k] is not None}
    raw_abs = (p.get("abstract") or "").strip()
    if raw_abs:
        out["abstract"] = raw_abs
    return out


def write_file(path: str, plist: list, dry_run: bool, verbose: bool = False) -> int:
    """写文件，返回字节数。verbose=True 时打印明细。"""
    plist.sort(key=lambda x: x.get("citation_count", 0), reverse=True)
    raw = json.dumps(plist, ensure_ascii=False, separators=(",", ":"))
    size_bytes = len(raw.encode())
    if verbose:
        top_venues = Counter(p.get("venue") for p in plist).most_common(3)
        print(f"  {os.path.basename(path)}: {len(plist)} 篇  {size_bytes/1024/1024:.1f} MB  top={top_venues}")
    if not dry_run:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(raw)
        os.replace(tmp, path)
    return size_bytes


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

    YEARS = get_years()
    # manifest[domain][year] = [month, month, ...]，前端据此 fetch
    manifest: dict = {d: {} for d in DOMAINS}

    # ── 按 domain × year × month 拆分 ─────────────────────────────────────────
    for domain in DOMAINS:
        by_ym: dict = {}
        for p in papers:
            if domain not in (p.get("_domains") or []):
                continue
            year = p.get("year")
            if year not in YEARS:
                continue
            month = p.get("month") or 0
            if not (1 <= month <= 12):
                month = 1   # 缺月份的归到 1 月
            by_ym.setdefault((year, month), []).append(slim(p))

        total_papers = sum(len(v) for v in by_ym.values())
        total_bytes = 0
        for (year, month), plist in sorted(by_ym.items()):
            path = os.path.join(DATA_DIR, f"papers_curated_{domain}_{year}_{month:02d}.json")
            total_bytes += write_file(path, plist, args.dry_run)
            manifest[domain].setdefault(str(year), []).append(month)
        print(f"  {domain}: {len(by_ym)} 月文件, 共 {total_papers:,} 篇, {total_bytes/1024/1024:.1f} MB")

    # 排序 manifest 的月份列表
    for d in manifest:
        for y in manifest[d]:
            manifest[d][y] = sorted(set(manifest[d][y]))

    # 写 manifest
    manifest_path = os.path.join(DATA_DIR, "papers_curated_manifest.json")
    if args.dry_run:
        print(f"\n[dry-run] would write manifest to {manifest_path}")
    else:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        total_files = sum(len(months) for d in manifest.values() for months in d.values())
        print(f"\n✓ manifest: {total_files} 个月文件 → {manifest_path}")
        print(f"✓ 写出 {DATA_DIR}")


if __name__ == "__main__":
    sys.exit(main())
