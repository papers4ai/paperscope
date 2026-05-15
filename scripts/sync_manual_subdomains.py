#!/usr/bin/env python3
"""
sync_manual_subdomains.py — 同步 keywords_manual.json 到 task_meta.json。

功能：
  1. 读取 keywords_manual.json 中每个子领域的 zh/en 标签
  2. 如果只填了一种语言，调用 LLM 自动翻译另一种
  3. 将翻译结果回写到 keywords_manual.json
  4. 将新子领域合并写入 frontend/data/task_meta.json（tasks + domain_tasks）

用法：
    python scripts/sync_manual_subdomains.py
    python scripts/sync_manual_subdomains.py --dry-run

环境变量（翻译功能可选，不设则只做格式补全）：
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
"""

from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path

ROOT          = Path(__file__).parent.parent
MANUAL_PATH   = ROOT / "backend" / "config" / "keywords_manual.json"
TASK_META_PATH = ROOT / "frontend" / "data" / "task_meta.json"

DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL    = "glm-4-flash"

DOMAINS = ["world_model", "physical_ai", "medical_ai"]

# ── 语言检测 ──────────────────────────────────────────────────────────────────

def is_chinese(text: str) -> bool:
    return bool(re.search(r'[一-鿿]', text))


# ── Tag key 生成（英文标签 → CamelCase） ──────────────────────────────────────

def to_tag_key(en_label: str) -> str:
    """'Robot World Model' → 'RobotWorldModel'"""
    return re.sub(r'[^a-zA-Z0-9]', '', en_label.title().replace(' ', ''))


# ── LLM 翻译 ─────────────────────────────────────────────────────────────────

def _llm_client():
    try:
        import openai
    except ImportError:
        return None
    if not os.environ.get("LLM_API_KEY"):
        return None
    return openai.OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL,
    )


def translate(text: str, to_lang: str, client) -> str:
    """翻译 AI 研究子领域标签名。to_lang: 'zh' or 'en'"""
    if client is None:
        return ""
    model = os.environ.get("LLM_MODEL") or DEFAULT_MODEL
    if to_lang == "zh":
        prompt = (
            f"Translate this AI research sub-field label to concise Chinese (2-8 characters, "
            f"no explanation): '{text}'. Output the Chinese translation only."
        )
    else:
        prompt = (
            f"Translate this Chinese AI research sub-field label to concise English (2-4 words, "
            f"title case, no explanation): '{text}'. Output the English translation only."
        )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=30,
        )
        return resp.choices[0].message.content.strip().strip('"\'')
    except Exception as e:
        print(f"  [warn] translation failed: {e}")
        return ""


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manual: dict = json.loads(MANUAL_PATH.read_text(encoding="utf-8"))
    task_meta: dict = json.loads(TASK_META_PATH.read_text(encoding="utf-8"))

    client = _llm_client()
    if client is None:
        print("[info] No LLM client — translations will be skipped (fill both zh/en manually if needed)")

    manual_changed    = False
    taskmeta_changed  = False

    for domain in DOMAINS:
        entries = manual.get(domain, [])
        if not isinstance(entries, list):
            continue

        for item in entries:
            if not isinstance(item, dict):
                continue

            zh  = (item.get("zh") or "").strip()
            en  = (item.get("en") or "").strip()
            kws = item.get("keywords") or []

            # ── 补全缺失语言 ────────────────────────────────────────────────
            if zh and not en:
                translated = translate(zh, "en", client)
                if translated:
                    item["en"] = translated
                    en = translated
                    manual_changed = True
                    print(f"  [{domain}] translated zh→en: '{zh}' → '{translated}'")
                else:
                    # fallback: pinyin-style camelcase (最差情况)
                    item["en"] = zh
                    en = zh
                    print(f"  [{domain}] no translation available, using zh as en: '{zh}'")

            elif en and not zh:
                translated = translate(en, "zh", client)
                if translated:
                    item["zh"] = translated
                    zh = translated
                    manual_changed = True
                    print(f"  [{domain}] translated en→zh: '{en}' → '{translated}'")
                else:
                    item["zh"] = en
                    zh = en
                    print(f"  [{domain}] no translation available, using en as zh: '{en}'")

            if not en or not kws:
                continue

            # ── 生成 tag key ─────────────────────────────────────────────────
            tag = to_tag_key(en)

            # ── 写入 task_meta.tasks ─────────────────────────────────────────
            existing = task_meta["tasks"].get(tag, {})
            new_entry = {"zh": zh, "en": en}
            if existing != new_entry:
                task_meta["tasks"][tag] = new_entry
                taskmeta_changed = True
                print(f"  [{domain}] task_meta.tasks['{tag}'] = {new_entry}")

            # ── 写入 task_meta.domain_tasks ──────────────────────────────────
            dt = task_meta.setdefault("domain_tasks", {})
            dt.setdefault(domain, [])
            if tag not in dt[domain]:
                dt[domain].append(tag)
                taskmeta_changed = True
                print(f"  [{domain}] domain_tasks['{domain}'] += '{tag}'")

    # ── 写回文件 ─────────────────────────────────────────────────────────────
    if args.dry_run:
        print("\n[dry-run] no files written")
        if manual_changed:
            print("keywords_manual.json would be updated")
        if taskmeta_changed:
            print("task_meta.json would be updated")
    else:
        if manual_changed:
            MANUAL_PATH.write_text(
                json.dumps(manual, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"\n✓ Updated {MANUAL_PATH}")
        if taskmeta_changed:
            TASK_META_PATH.write_text(
                json.dumps(task_meta, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"✓ Updated {TASK_META_PATH}")

    if not manual_changed and not taskmeta_changed:
        print("✓ Nothing to update")

    return 0


if __name__ == "__main__":
    sys.exit(main())
