#!/usr/bin/env python3
"""
retag_manual_subdomains.py — 对 frontend/data/ 里现有 JSON 文件回溯打 manual 子领域标签。

当 keywords_manual.json 新增子领域后，已存在的论文不会自动获得新 task 标签。
此脚本对所有 papers_*.json 和 papers_curated_*.json 重跑匹配，补全 _tasks 字段。

用法：
    python scripts/retag_manual_subdomains.py
    python scripts/retag_manual_subdomains.py --dry-run
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT     = Path(__file__).parent.parent
DATA_DIR = ROOT / "frontend" / "data"
MANUAL   = ROOT / "backend" / "config" / "keywords_manual.json"


def load_patterns() -> dict[str, re.Pattern]:
    """从 keywords_manual.json 构建 {tag: 正则} 映射。"""
    data = json.loads(MANUAL.read_text(encoding="utf-8"))
    patterns: dict[str, re.Pattern] = {}
    for domain_entries in data.values():
        if not isinstance(domain_entries, list):
            continue
        for item in domain_entries:
            if not isinstance(item, dict):
                continue
            en  = (item.get("en") or "").strip()
            kws = item.get("keywords") or []
            if not en or not kws:
                continue
            tag = re.sub(r"[^a-zA-Z0-9]", "", en.title().replace(" ", ""))
            expr = "|".join(rf"\b{re.escape(k)}\b" for k in kws)
            patterns[tag] = re.compile(expr, re.I)
    return patterns


def retag_file(path: Path, patterns: dict[str, re.Pattern], dry_run: bool) -> int:
    papers = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for p in papers:
        text  = (p.get("title") or "") + " " + (p.get("abstract") or "")
        tasks = list(p.get("_tasks") or [])
        for tag, pat in patterns.items():
            if tag not in tasks and pat.search(text):
                tasks.append(tag)
                changed += 1
        if tasks != list(p.get("_tasks") or []):
            p["_tasks"] = tasks
    if changed and not dry_run:
        path.write_text(json.dumps(papers, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    patterns = load_patterns()
    if not patterns:
        print("No patterns found in keywords_manual.json")
        return 0
    print(f"Loaded {len(patterns)} manual tag patterns: {list(patterns)}")

    total = 0
    for path in sorted(DATA_DIR.glob("papers*.json")):
        changed = retag_file(path, patterns, args.dry_run)
        if changed:
            print(f"  {path.name}: +{changed} tag(s) applied")
            total += changed

    action = "[dry-run]" if args.dry_run else "✓"
    print(f"{action} Total: {total} tags applied across all files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
