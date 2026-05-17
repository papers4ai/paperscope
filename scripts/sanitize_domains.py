#!/usr/bin/env python3
"""清理 _domains 字段里非三大白名单的 domain（LLM 自创的污染）。

处理：
  - output/papers_curated.json:  paper["_domains"] 过滤白名单
  - output/llm_classify_cache.json:  cache[id]["domains"] 过滤白名单
  - output/llm_arxiv_cache.json:    同上（如果存在）

用法：
    .venv/bin/python scripts/sanitize_domains.py
    .venv/bin/python scripts/sanitize_domains.py --dry-run
"""

import argparse
import json
import os
import sys
from collections import Counter

WHITELIST = {"world_model", "physical_ai", "medical_ai"}


def sanitize_papers(path: str, dry_run: bool) -> None:
    if not os.path.exists(path):
        print(f"  [skip] {path}: not found")
        return
    print(f"Loading {path}...")
    papers = json.load(open(path, encoding="utf-8"))
    print(f"  {len(papers):,} papers")

    before = Counter(d for p in papers for d in (p.get("_domains") or []))
    fixed_count = 0
    for p in papers:
        domains = p.get("_domains") or []
        clean = [d for d in domains if d in WHITELIST]
        if clean != domains:
            p["_domains"] = clean
            fixed_count += 1
    after = Counter(d for p in papers for d in (p.get("_domains") or []))

    dropped = {d: c for d, c in before.items() if d not in WHITELIST}
    print(f"  {fixed_count:,} papers had dirty domains")
    print(f"  Before: {dict(before)}")
    print(f"  After:  {dict(after)}")
    print(f"  Dropped {len(dropped)} non-whitelist domain types ({sum(dropped.values())} occurrences)")

    if dry_run:
        print("  [dry-run] not writing")
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    print(f"  ✓ rewrote {path} ({os.path.getsize(path)/1024/1024:.1f} MB)")


def sanitize_cache(path: str, dry_run: bool) -> None:
    if not os.path.exists(path):
        print(f"  [skip] {path}: not found")
        return
    print(f"Loading {path}...")
    cache = json.load(open(path))
    print(f"  {len(cache):,} cache entries")

    fixed = 0
    before = Counter()
    after = Counter()
    for pid, classification in cache.items():
        domains = classification.get("domains") or []
        before.update(domains)
        clean = [d for d in domains if d in WHITELIST]
        if clean != domains:
            classification["domains"] = clean
            fixed += 1
        after.update(clean)

    dropped = {d: c for d, c in before.items() if d not in WHITELIST}
    print(f"  {fixed:,} cache entries had dirty domains")
    print(f"  Dropped: {len(dropped)} types, {sum(dropped.values())} occurrences")

    if dry_run:
        print("  [dry-run] not writing")
        return
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, path)
    print(f"  ✓ rewrote {path}")


def main():
    import glob

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("=== Sanitizing papers JSON ===")
    sanitize_papers("output/papers_curated.json", args.dry_run)
    print()
    print("=== Sanitizing arxiv backfill outputs ===")
    arxiv_outputs = sorted(glob.glob("output/arxiv_backfill_*.json"))
    arxiv_outputs = [f for f in arxiv_outputs if not f.endswith("_candidates.json")]
    if not arxiv_outputs:
        print("  (none found)")
    for f in arxiv_outputs:
        sanitize_papers(f, args.dry_run)
    print()
    print("=== Sanitizing curated cache ===")
    sanitize_cache("output/llm_classify_cache.json", args.dry_run)
    print()
    print("=== Sanitizing arxiv cache (if exists) ===")
    sanitize_cache("output/llm_arxiv_cache.json", args.dry_run)


if __name__ == "__main__":
    main()
