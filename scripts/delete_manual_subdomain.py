#!/usr/bin/env python3
"""
delete_manual_subdomain.py — 删除一个手动维护的子领域，并清理所有副本。

清理范围（三处）：
  1. backend/config/keywords_manual.json  — 移除匹配 zh/en label 的条目
  2. frontend/data/task_meta.json         — 从 tasks 字典和 domain_tasks 列表里移除对应 tag
  3. frontend/data/papers*.json           — 从每篇论文的 _tasks 数组里剥掉这个 tag

用法：
    # 按英文 label 删（推荐，精确匹配 keywords_manual.json 的 "en" 字段）
    python scripts/delete_manual_subdomain.py --domain world_model --label "world model for robot"

    # 按中文 label 删也可以
    python scripts/delete_manual_subdomain.py --domain world_model --label "机器人世界模型"

    # 直接按生成的 tag key 删（绕过 label 匹配）
    python scripts/delete_manual_subdomain.py --domain world_model --tag WorldModelForRobot

    # 预览不写盘
    python scripts/delete_manual_subdomain.py --domain world_model --label "..." --dry-run
"""

from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT           = Path(__file__).parent.parent
MANUAL_PATH    = ROOT / "backend" / "config" / "keywords_manual.json"
TASK_META_PATH = ROOT / "frontend" / "data" / "task_meta.json"
DATA_DIR       = ROOT / "frontend" / "data"


def to_tag_key(en_label: str) -> str:
    """'Robot World Model' → 'RobotWorldModel'（与 sync_manual_subdomains.py 保持一致）"""
    return re.sub(r"[^a-zA-Z0-9]", "", en_label.title().replace(" ", ""))


def remove_from_manual(domain: str, label: str | None, tag: str | None,
                       dry_run: bool) -> tuple[bool, set[str]]:
    """从 keywords_manual.json 删除条目。返回 (是否改动, 被删条目对应的 tag 集合)。"""
    data = json.loads(MANUAL_PATH.read_text(encoding="utf-8"))
    entries = data.get(domain, [])
    if not isinstance(entries, list):
        print(f"[warn] domain '{domain}' has no list entries — nothing to delete")
        return False, set()

    removed_tags: set[str] = set()
    kept = []
    for item in entries:
        if not isinstance(item, dict):
            kept.append(item)
            continue
        en = (item.get("en") or "").strip()
        zh = (item.get("zh") or "").strip()
        item_tag = to_tag_key(en) if en else ""

        matches = False
        if tag and item_tag == tag:
            matches = True
        elif label and (en == label or zh == label):
            matches = True

        if matches:
            removed_tags.add(item_tag)
            print(f"  [manual] removing entry: zh='{zh}' en='{en}' tag='{item_tag}'")
        else:
            kept.append(item)

    if not removed_tags:
        print(f"[info] no matching entry in keywords_manual.json[{domain}]")
        return False, set()

    data[domain] = kept
    if not dry_run:
        MANUAL_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return True, removed_tags


def remove_from_task_meta(domain: str, tags: set[str], dry_run: bool) -> bool:
    """从 task_meta.json 的 tasks 字典和 domain_tasks 列表里移除 tag。"""
    if not tags:
        return False
    data = json.loads(TASK_META_PATH.read_text(encoding="utf-8"))
    changed = False

    tasks = data.get("tasks", {})
    for tag in list(tags):
        if tag in tasks:
            print(f"  [task_meta] removing tasks['{tag}']")
            del tasks[tag]
            changed = True

    dt_list = data.get("domain_tasks", {}).get(domain, [])
    if isinstance(dt_list, list):
        new_list = [t for t in dt_list if t not in tags]
        if new_list != dt_list:
            print(f"  [task_meta] domain_tasks['{domain}'] -= {sorted(tags & set(dt_list))}")
            data["domain_tasks"][domain] = new_list
            changed = True

    # 防御：如果 tag 漏跑到了其它 domain_tasks 里（不该有，但顺手清掉）
    for other_domain, lst in (data.get("domain_tasks") or {}).items():
        if other_domain == domain or not isinstance(lst, list):
            continue
        new_lst = [t for t in lst if t not in tags]
        if new_lst != lst:
            print(f"  [task_meta] domain_tasks['{other_domain}'] -= {sorted(tags & set(lst))} (stray)")
            data["domain_tasks"][other_domain] = new_lst
            changed = True

    if changed and not dry_run:
        TASK_META_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return changed


def strip_from_papers(tags: set[str], dry_run: bool) -> int:
    """从所有 papers*.json 的 _tasks 数组里去掉这些 tag。返回被清理的论文数。"""
    if not tags:
        return 0
    total_papers = 0
    for path in sorted(DATA_DIR.glob("papers*.json")):
        papers = json.loads(path.read_text(encoding="utf-8"))
        file_changed = 0
        for p in papers:
            cur = p.get("_tasks")
            if not cur:
                continue
            new = [t for t in cur if t not in tags]
            if len(new) != len(cur):
                p["_tasks"] = new
                file_changed += 1
        if file_changed:
            print(f"  [papers] {path.name}: stripped tag from {file_changed} paper(s)")
            total_papers += file_changed
            if not dry_run:
                path.write_text(
                    json.dumps(papers, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
    return total_papers


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True,
                    choices=["world_model", "physical_ai", "medical_ai"])
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--label", help="中文或英文 label（匹配 keywords_manual.json 的 zh/en 字段）")
    group.add_argument("--tag",   help="直接指定 tag key，如 WorldModelForRobot")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manual_changed, removed_tags = remove_from_manual(
        args.domain, args.label, args.tag, args.dry_run,
    )

    # 即便 manual 没匹配到，--tag 也允许我们继续清理 task_meta 和 papers
    if not removed_tags and args.tag:
        removed_tags = {args.tag}

    if not removed_tags:
        print("Nothing matched — no changes.")
        return 1

    meta_changed = remove_from_task_meta(args.domain, removed_tags, args.dry_run)
    paper_count  = strip_from_papers(removed_tags, args.dry_run)

    prefix = "[dry-run] " if args.dry_run else "✓ "
    print(f"\n{prefix}Removed tags: {sorted(removed_tags)}")
    print(f"{prefix}keywords_manual.json updated: {manual_changed}")
    print(f"{prefix}task_meta.json updated:       {meta_changed}")
    print(f"{prefix}papers updated:               {paper_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
