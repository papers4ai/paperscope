#!/usr/bin/env python3
"""把 Jefferyzhifeng/Paperscope-hub 的 papers_curated.json 同步到前端静态文件

用法：
    python scripts/sync_curated.py                  # 从远程 GitHub 拉
    python scripts/sync_curated.py --local /path/to/papers_curated.json
    python scripts/sync_curated.py --dry-run
"""
import argparse, json, os, sys, urllib.request

REMOTE = "https://raw.githubusercontent.com/Jefferyzhifeng/Paperscope-hub/main/output/papers_curated.json"
OUT = os.path.join(os.path.dirname(__file__), "..", "frontend", "data", "papers_curated.json")

# abstract 不写入前端（单文件体积 218 MB → 88 MB）
# 详情页摘要可在前端按需从 arXiv API 补充
KEEP = ["id", "title", "authors", "published", "year", "month",
        "pdf_url", "arxiv_url", "code", "has_code", "type",
        "_domains", "_tasks", "venue", "venue_tier", "citation_count"]


def slim(p):
    return {k: p.get(k) for k in KEEP if p.get(k) is not None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="本地 papers_curated.json 路径（不从网络拉）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.local:
        print(f"Loading from {args.local}")
        remote = json.load(open(args.local))
    else:
        print(f"Fetching {REMOTE} ...")
        with urllib.request.urlopen(REMOTE) as r:
            remote = json.load(r)

    # 只保留 2023+ 且有 venue
    filtered = [slim(p) for p in remote
                if (p.get("year") or 0) >= 2023 and p.get("venue")]
    print(f"Total: {len(remote)} → filtered (2023+, has venue): {len(filtered)}")

    # 如果本地已有，增量合并
    local = []
    if os.path.exists(OUT):
        local = json.load(open(OUT))
        seen = {p["id"] for p in local if p.get("id")}
        new = [p for p in filtered if p.get("id") and p["id"] not in seen]
        merged = local + new
        print(f"Local: {len(local)}, New: {len(new)}, Merged: {len(merged)}")
    else:
        merged = filtered
        print(f"Creating new file with {len(merged)} papers")

    from collections import Counter
    venues = Counter(p.get("venue") for p in merged if p.get("venue"))
    print("Top venues:", venues.most_common(10))

    if args.dry_run:
        return 0

    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    size_mb = os.path.getsize(OUT) / 1024 / 1024
    print(f"Wrote {len(merged)} papers → {OUT} ({size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
