#!/usr/bin/env python3
"""
update_domain_keywords.py — 用 LLM 分析近1个月高引论文，自动发现新兴研究子热点，
写入 backend/config/keywords_auto.json，供 arXiv 查询和领域分类使用。

用法：
    python scripts/update_domain_keywords.py
    python scripts/update_domain_keywords.py --dry-run
    python scripts/update_domain_keywords.py --months 2

环境变量（同 cleaning/llm_classify.py）：
    LLM_API_KEY    必填
    LLM_BASE_URL   可选，默认智谱 GLM-4-Flash
    LLM_MODEL      可选，默认 glm-4-flash
"""

from __future__ import annotations
import argparse, json, os, re, sys
from datetime import date, timedelta
from pathlib import Path

ROOT     = Path(__file__).parent.parent
DATA_DIR = ROOT / "frontend" / "data"
OUT_PATH = ROOT / "backend" / "config" / "keywords_auto.json"

DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL    = "glm-4-flash"

MAX_PAPERS   = 120   # 每域最多取多少篇作为 LLM 上下文
MAX_AUTO_KWS = 8     # 每域最多写入多少条自动关键词

DOMAIN_DESC = {
    "world_model": (
        "World Model research: video generation/prediction, scene reconstruction, "
        "NeRF/Gaussian splatting, model-based RL, sim-to-real, robot world models, "
        "embodied agents, latent dynamics, action/predictive models"
    ),
    "physical_ai": (
        "Physical AI research: physics-informed neural networks (PINN), neural operators, "
        "robot learning/manipulation, embodied AI, humanoid robots, fluid/climate simulation, "
        "3D reconstruction, dexterous manipulation"
    ),
    "medical_ai": (
        "Medical AI research: medical imaging (CT/MRI/pathology), cancer detection, "
        "drug discovery, protein structure, clinical decision support, "
        "surgical navigation, medical vision-language models"
    ),
}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_recent_papers(domain: str, months: int) -> list[dict]:
    cutoff = (date.today() - timedelta(days=months * 31)).isoformat()
    papers: list[dict] = []
    for year in [date.today().year, date.today().year - 1]:
        path = DATA_DIR / f"papers_curated_{domain}_{year}.json"
        if not path.exists():
            continue
        batch = json.loads(path.read_text(encoding="utf-8"))
        papers.extend(p for p in batch if (p.get("published") or "") >= cutoff)
    papers.sort(key=lambda p: p.get("citation_count", 0), reverse=True)
    return papers[:MAX_PAPERS]


# ── Prompt ────────────────────────────────────────────────────────────────────

def build_prompt(domain: str, papers: list[dict]) -> str:
    lines = []
    for p in papers:
        title    = (p.get("title") or "").strip()
        abstract = (p.get("abstract") or "")[:180].strip()
        lines.append(f"- {title}. {abstract}")
    paper_block = "\n".join(lines) or "(no papers)"

    return f"""You are a research trend analyst specializing in AI/ML.

Field: {DOMAIN_DESC[domain]}

Below are the most-cited papers from the past {MAX_PAPERS} in this field (last 1 month):
{paper_block}

Task:
Identify 5-8 **emerging sub-topic keyword phrases** suitable as arXiv API search terms.

Rules:
1. Each phrase must be 2-5 words, lowercase.
2. Must be specific enough to find relevant arXiv papers via exact phrase match.
3. Must represent a genuinely growing sub-direction seen in the papers above.
4. Do NOT include overly generic terms (e.g. "deep learning", "large language model", "neural network").
5. Do NOT repeat terms already in the core keyword list for this field.

Output ONLY a valid JSON array of strings. No explanation, no markdown.
Example: ["keyword phrase one", "keyword phrase two", "keyword phrase three"]"""


# ── LLM call ─────────────────────────────────────────────────────────────────

def call_llm(prompt: str) -> str:
    try:
        import openai
    except ImportError:
        print("  [error] pip install openai", file=sys.stderr)
        sys.exit(1)

    client = openai.OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL),
    )
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=400,
    )
    return resp.choices[0].message.content.strip()


# ── Parse & validate ──────────────────────────────────────────────────────────

def parse_keywords(raw: str) -> list[str]:
    m = re.search(r'\[.*?\]', raw, re.DOTALL)
    if not m:
        return []
    try:
        arr = json.loads(m.group())
    except Exception:
        return []
    out = []
    for k in arr:
        if not isinstance(k, str):
            continue
        k = k.strip().lower()
        words = k.split()
        if 2 <= len(words) <= 5 and re.match(r'^[a-z0-9 \-]+$', k):
            out.append(k)
    return out[:MAX_AUTO_KWS]


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="不写文件，只打印结果")
    ap.add_argument("--months", type=int, default=1, help="分析最近几个月的论文")
    args = ap.parse_args()

    if not os.environ.get("LLM_API_KEY"):
        print("[error] LLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # 读取现有文件（保留 _note 等元数据）
    existing: dict = {}
    if OUT_PATH.exists():
        existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))

    result = {
        "_updated": date.today().isoformat(),
        "_note": existing.get("_note", "Auto-generated by scripts/update_domain_keywords.py"),
    }

    for domain in ["world_model", "physical_ai", "medical_ai"]:
        print(f"\n── {domain} ──")
        papers = load_recent_papers(domain, args.months)
        print(f"  Loaded {len(papers)} papers (last {args.months} month(s))")

        if not papers:
            result[domain] = existing.get(domain, [])
            print("  No papers found, keeping existing keywords")
            continue

        prompt = build_prompt(domain, papers)
        print("  Calling LLM...")
        try:
            raw = call_llm(prompt)
        except Exception as e:
            print(f"  [warn] LLM call failed: {e}, keeping existing")
            result[domain] = existing.get(domain, [])
            continue

        keywords = parse_keywords(raw)
        print(f"  → {keywords}")
        result[domain] = keywords

    if args.dry_run:
        print("\n[dry-run] Would write:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        OUT_PATH.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\n✓ Written to {OUT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
