#!/usr/bin/env python3
"""
一次性修复 papers_curated.json 中的领域标注

问题：旧版抓取器将 TPAMI / NeurIPS / Nature 等综合期刊的
所有论文都打上了 ["world_model", "physical_ai", "medical_ai"]，
原因是 check_domains_all(paper_dict) 传了 dict 导致 TypeError，
被 except 静默忽略，最终使用 venue 预归属（三个领域全上）。

修复策略：
  - 专业 venue（MICCAI / ICRA 等）：保持 venue 预归属，不变
  - 综合 venue（NeurIPS / TPAMI 等）：重新做关键词检测，
    检测到 → 用检测结果；未检测到 → 用 default_domain 兜底

用法：
    python reclassify_domains.py
    python reclassify_domains.py --dry-run
    python reclassify_domains.py --input /path/to/papers_curated.json
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from cleaning import check_domains_all, tag_tasks_all, classify_paper_type, extract_code_links

# ── 与 fetch_curated_fast.py 保持一致 ────────────────────────────────────────
# domains=[]  → 综合 venue，完全依赖关键词
# domains=[…] → 专业 venue，保持硬编码
VENUE_CONFIG = {
    # 综合 AI/ML 顶会（关键词决定领域）
    "NeurIPS":        {"domains": [], "default": "world_model"},
    "ICML":           {"domains": [], "default": "world_model"},
    "ICLR":           {"domains": [], "default": "world_model"},
    "AAAI":           {"domains": [], "default": "world_model"},
    "IJCAI":          {"domains": [], "default": "world_model"},
    "AISTATS":        {"domains": [], "default": "world_model"},
    # CV 顶会
    "CVPR":           {"domains": [], "default": "world_model"},
    "ICCV":           {"domains": [], "default": "world_model"},
    "ECCV":           {"domains": [], "default": "world_model"},
    "SIGGRAPH":       {"domains": ["world_model"]},
    "SIGGRAPH Asia":  {"domains": ["world_model"]},
    "ACM MM":         {"domains": ["world_model"]},
    # NLP 顶会
    "ACL":            {"domains": [], "default": "world_model"},
    "EMNLP":          {"domains": [], "default": "world_model"},
    "NAACL":          {"domains": [], "default": "world_model"},
    # AI/CV 顶刊
    "TPAMI":          {"domains": [], "default": "world_model"},
    "IJCV":           {"domains": [], "default": "world_model"},
    "TIP":            {"domains": [], "default": "world_model"},
    "JMLR":           {"domains": [], "default": "world_model"},
    "TMLR":           {"domains": [], "default": "world_model"},
    # 综合科学顶刊
    "Nature":                      {"domains": [], "default": "world_model"},
    "Nature Machine Intelligence": {"domains": [], "default": "world_model"},
    "Nature Communications":       {"domains": [], "default": "world_model"},
    "Science":        {"domains": [], "default": "medical_ai"},
    "PNAS":           {"domains": [], "default": "medical_ai"},
    # 机器人（固定）
    "ICRA":           {"domains": ["physical_ai"]},
    "IROS":           {"domains": ["physical_ai"]},
    "CoRL":           {"domains": ["physical_ai"]},
    "RSS":            {"domains": ["physical_ai"]},
    "ICAPS":          {"domains": ["physical_ai"]},
    "AAMAS":          {"domains": ["physical_ai"]},
    "Science Robotics": {"domains": ["physical_ai"]},
    "TRO":            {"domains": ["physical_ai"]},
    "IJRR":           {"domains": ["physical_ai"]},
    "RA-L":           {"domains": ["physical_ai"]},
    # 医学（固定）
    "MICCAI":         {"domains": ["medical_ai"]},
    "MIDL":           {"domains": ["medical_ai"]},
    "CHI":            {"domains": ["medical_ai"]},
    "Nature Medicine":{"domains": ["medical_ai"]},
    "Nature Methods": {"domains": ["medical_ai"]},
    "The Lancet":     {"domains": ["medical_ai"]},
    "JAMA":           {"domains": ["medical_ai"]},
    "BMJ":            {"domains": ["medical_ai"]},
    "Cell":           {"domains": ["medical_ai"]},
    "TMI":            {"domains": ["medical_ai"]},
    "Radiology":      {"domains": ["medical_ai"]},
    "Bioinformatics": {"domains": ["medical_ai"]},
    # 不在白名单的 venue → 只跑关键词检测
}


def reclassify(p: dict) -> dict:
    venue = p.get("venue", "")
    vcfg  = VENUE_CONFIG.get(venue, {})
    fixed_domains = vcfg.get("domains")  # None = 未知 venue
    default       = vcfg.get("default")
    title    = p.get("title", "")
    abstract = p.get("abstract", "") or ""

    if fixed_domains is not None and len(fixed_domains) > 0:
        # 专业 venue：保持固定领域，但仍重新跑任务标注
        p["_domains"] = fixed_domains
    else:
        # 综合 venue 或未知 venue：关键词决定
        detected, _ = check_domains_all(title, abstract)
        if detected:
            p["_domains"] = detected
        elif default:
            p["_domains"] = [default]
        else:
            # 连兜底都没有：保留原值（不做破坏性修改）
            pass

    # 重新跑任务标注（统一更新）
    try:
        tasks, _ = tag_tasks_all(title, abstract)
        p["_tasks"] = tasks
        p["type"] = classify_paper_type(title, abstract)
        if not p.get("code"):
            links = extract_code_links(f"{title} {abstract}")
            if links:
                p["code"] = links[0]
                p["has_code"] = True
    except Exception:
        pass

    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",  default="output/papers_curated.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"File not found: {args.input}")
        sys.exit(1)

    papers = json.load(open(args.input, encoding="utf-8"))
    print(f"Loaded {len(papers)} papers")

    # Before stats
    before = Counter(d for p in papers for d in (p.get("_domains") or []))
    multi_before = sum(1 for p in papers if len(p.get("_domains") or []) > 1)
    print(f"Before — domains: {dict(before)}  multi-domain: {multi_before} ({100*multi_before//len(papers)}%)")

    papers = [reclassify(p) for p in papers]

    after  = Counter(d for p in papers for d in (p.get("_domains") or []))
    multi_after  = sum(1 for p in papers if len(p.get("_domains") or []) > 1)
    print(f"After  — domains: {dict(after)}   multi-domain: {multi_after} ({100*multi_after//len(papers)}%)")

    if args.dry_run:
        print("[dry-run] No file written.")
        return

    tmp = args.input + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, args.input)
    size = os.path.getsize(args.input) / 1024 / 1024
    print(f"Wrote {len(papers)} papers → {args.input} ({size:.2f} MB)")


if __name__ == "__main__":
    main()
