#!/usr/bin/env python3
"""一次性清理 papers_*.json 里的"假阳性" domain 标签。

LLM classify 早期 prompt 过宽，把许多明显不属于 world_model/physical_ai/
medical_ai 的论文也打上了 domain 标签。本脚本用 cleaning.domain_filter 的
锚点规则做事后过滤，把没证据的 domain 从 _domains 里剔除。

锚点 = task tag 命中 anchor 集合 OR title/topics 命中关键词
剔除后 _domains 变空的论文，保留在 JSON 里但不会进任何 domain 视图。

用法：
    python scripts/filter_false_domains.py              # 应用并写回
    python scripts/filter_false_domains.py --dry-run    # 只看统计
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from collections import Counter
from glob import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cleaning.domain_filter import filter_domains, WHITELIST

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "data")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    paths = sorted(glob(os.path.join(DATA_DIR, "papers_[0-9]*.json")))
    print(f"Found {len(paths)} paper files")

    total_before = Counter()
    total_after = Counter()
    total_papers_before = 0
    total_papers_after = 0
    touched_papers = 0
    dropped_papers = 0   # _domains 变空 → 整条丢弃

    for path in paths:
        with open(path, encoding="utf-8") as f:
            papers = json.load(f)
        before = Counter(d for p in papers for d in (p.get("_domains") or []))
        kept: list[dict] = []
        file_touched = 0
        file_dropped = 0
        for p in papers:
            doms = p.get("_domains") or []
            if not doms:
                file_dropped += 1
                continue
            clean = filter_domains(
                doms,
                p.get("_tasks") or [],
                p.get("title") or "",
                p.get("_topics") or [],
            )
            if not clean:
                file_dropped += 1
                continue
            if clean != doms:
                p["_domains"] = clean
                file_touched += 1
            kept.append(p)
        papers = kept
        after = Counter(d for p in papers for d in (p.get("_domains") or []))

        total_before += before
        total_after += after
        total_papers_before += len(papers) + file_dropped
        total_papers_after += len(papers)
        touched_papers += file_touched
        dropped_papers += file_dropped

        print(f"  {os.path.basename(path)}: {len(papers):,} kept "
              f"({file_dropped:,} dropped, {file_touched:,} pruned)")
        for d in sorted(WHITELIST):
            b, a = before.get(d, 0), after.get(d, 0)
            if b != a:
                print(f"    {d}: {b} → {a}  ({a-b:+d})")

        if not args.dry_run:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(papers, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, path)

    print()
    print(f"=== Totals across {len(paths)} files ===")
    print(f"Papers before: {total_papers_before:,}")
    print(f"Papers after:  {total_papers_after:,}  "
          f"(dropped {dropped_papers:,}, pruned {touched_papers:,})")
    for d in sorted(WHITELIST):
        b, a = total_before.get(d, 0), total_after.get(d, 0)
        print(f"  {d}: {b:,} → {a:,}  ({a-b:+,})")

    if args.dry_run:
        print("[dry-run] nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
