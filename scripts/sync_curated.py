#!/usr/bin/env python3
"""把 output/papers_curated.json 按领域拆分，同步到 frontend/data/

输出文件（3 个，各 ~15-50 MB，均低于 GitHub 100 MB 限制）：
  frontend/data/papers_curated_world_model.json
  frontend/data/papers_curated_physical_ai.json
  frontend/data/papers_curated_medical_ai.json

用法：
    python scripts/sync_curated.py
    python scripts/sync_curated.py --local output/papers_curated.json
    python scripts/sync_curated.py --dry-run
"""
import argparse, json, os, sys, urllib.request
from collections import defaultdict, Counter

REMOTE = "https://raw.githubusercontent.com/Jefferyzhifeng/Paperscope-hub/main/output/papers_curated.json"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "data")

DOMAINS = ["world_model", "physical_ai", "medical_ai"]

# 写入前端的字段（不含 abstract，控制文件体积）
KEEP = [
    "id", "title", "authors", "published", "year", "month",
    "pdf_url", "arxiv_url", "code", "has_code", "type",
    "_domains", "_tasks", "venue", "venue_tier", "citation_count",
]


def slim(p: dict) -> dict:
    return {k: p[k] for k in KEEP if k in p and p[k] is not None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="本地 papers_curated.json 路径（不从网络拉）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # ── 加载数据 ───────────────────────────────────────────────────────────────
    if args.local:
        print(f"Loading from {args.local} ...")
        papers = json.load(open(args.local, encoding="utf-8"))
    else:
        print(f"Fetching {REMOTE} ...")
        with urllib.request.urlopen(REMOTE) as r:
            papers = json.load(r)

    # 过滤：只保留 2023+ 且有 venue 的论文
    papers = [p for p in papers if (p.get("year") or 0) >= 2023 and p.get("venue")]
    print(f"Total after filter (2023+, has venue): {len(papers)}")

    # ── 按领域分桶 ────────────────────────────────────────────────────────────
    buckets: dict = {d: [] for d in DOMAINS}
    for p in papers:
        p_slim = slim(p)
        for d in (p.get("_domains") or []):
            if d in buckets:
                buckets[d].append(p_slim)

    # ── 统计并写出 ────────────────────────────────────────────────────────────
    for domain in DOMAINS:
        plist = buckets[domain]
        # 按引用数降序排列（前端展示用）
        plist.sort(key=lambda x: x.get("citation_count", 0), reverse=True)

        out_path = os.path.join(DATA_DIR, f"papers_curated_{domain}.json")
        raw = json.dumps(plist, ensure_ascii=False, separators=(",", ":"))
        size_mb = len(raw.encode()) / 1024 / 1024

        top_venues = Counter(p.get("venue") for p in plist).most_common(5)
        print(f"\n  [{domain}] {len(plist)} 篇  {size_mb:.1f} MB")
        print(f"    top venues: {top_venues}")

        if not args.dry_run:
            tmp = out_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(raw)
            os.replace(tmp, out_path)
            print(f"    → {out_path}")

    if args.dry_run:
        print("\n[dry-run] 未写文件")
    else:
        print(f"\n✓ 写出 3 个领域文件到 {DATA_DIR}")


if __name__ == "__main__":
    sys.exit(main())
