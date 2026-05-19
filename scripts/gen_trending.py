#!/usr/bin/env python3
"""
gen_trending.py — Compute trending research topics from paper data.

Reads  : frontend/data/papers_*.json
Writes : frontend/data/trending.json

No external API keys required; uses n-gram frequency + domain specificity.
Run    : python scripts/gen_trending.py
"""

import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "frontend" / "data"
OUTPUT = DATA_DIR / "trending.json"

DOMAINS = ["world_model", "physical_ai", "medical_ai"]
MONTHS = 6      # 用于 radar / topic cards / predictions 的稳定窗口
HOT_DAYS = 90   # 用于 Hot Topics / 对比 / 深度分析 / 预测 — 3 个月窗口
TOP_N = 8       # 6 个月窗口每 domain 主题数 (Topic Cards 实际只取前 2)
HOT_TOP_N = 30  # 30 天 Hot Topics 每 domain 主题数 (前端用滚动列表呈现)

STOP = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "this", "that", "is", "are", "was", "were",
    "be", "been", "have", "has", "do", "does", "we", "our", "it", "its",
    "they", "which", "as", "such", "can", "also", "not", "but", "than",
    "based", "proposed", "approach", "method", "model", "models", "paper",
    "propose", "presents", "present", "show", "shows", "use", "using",
    "used", "results", "demonstrate", "work", "however", "state", "art",
    "two", "three", "new", "novel", "existing", "recent", "learning",
    "deep", "neural", "network", "networks", "data", "task", "tasks",
    "training", "trained", "large", "high", "low", "via", "into",
    "each", "both", "across", "while", "without", "further", "thus",
    "extensive", "experiments", "outperforms", "significantly", "achieves",
    "benchmark", "performance", "evaluation", "superior", "experimental",
    "https", "github", "http", "com", "available", "code", "page",
    "project", "arxiv", "www", "pdes", "pinns", "pinn", "odes",
}

NORM = {
    "images": "image", "models": "model", "networks": "network",
    "equations": "equation", "methods": "method", "agents": "agent",
    "fields": "field", "operators": "operator", "algorithms": "algorithm",
    "systems": "system", "problems": "problem", "tasks": "task",
}

BOILERPLATE = re.compile(
    r"(extensive experiment|state.of.the.art|code available|project page"
    r"|success rate|real.world|significantly outperform|achieves state"
    r"|available https|github com|page https)",
    re.IGNORECASE,
)

UPPER_WORDS = {
    "pinn", "fno", "vla", "rl", "nlp", "mri", "ct", "vae",
    "gan", "llm", "vlm", "nerf", "ai", "3d", "2d", "ood",
    "cnn", "rnn", "gnn", "gpt", "ehr", "wsi", "oct",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_papers() -> list:
    papers = []
    for path in sorted(DATA_DIR.glob("papers_[0-9]*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                papers.extend(json.load(f))
        except Exception as e:
            print(f"  warn: could not read {path.name}: {e}", file=sys.stderr)
    print(f"Loaded {len(papers)} papers from {DATA_DIR}")
    return papers


def display(term: str) -> str:
    parts = []
    for w in term.split():
        parts.append(w.upper() if w in UPPER_WORDS else w.capitalize())
    return " ".join(parts)


def tokenize(text: str):
    tokens = re.findall(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", text.lower())
    return [t for t in tokens if t not in STOP and len(t) > 2]


def ngrams(texts: list) -> Counter:
    counter: Counter = Counter()
    for text in texts:
        toks = tokenize(text)
        for n in (2, 3):
            for i in range(len(toks) - n + 1):
                counter[" ".join(toks[i: i + n])] += 1
    return counter


def tok_set(term: str) -> set:
    return {NORM.get(w, w) for w in re.split(r"[\s\-]+", term.lower())}


def top_topics(domain_papers: list, all_texts: list, all_ng: Counter,
               total: int, top_n: int = TOP_N) -> list:
    texts = [
        f"{p.get('title', '')} {p.get('title', '')} {p.get('abstract', '')[:400]}"
        for p in domain_papers
    ]
    n_papers = max(len(texts), 1)
    domain_ng = ngrams(texts)

    candidates = []
    for gram, freq in domain_ng.most_common(1000):
        if freq < 3:
            break
        if BOILERPLATE.search(gram):
            continue
        global_freq = all_ng.get(gram, 0)
        specificity = (freq / n_papers) / (global_freq / total + 1e-6)
        if specificity > 1.3:
            candidates.append({
                "term": gram,
                "display": display(gram),
                "count": freq,
                "specificity": round(specificity, 2),
            })

    candidates.sort(key=lambda x: -x["count"])

    deduped: list = []
    for c in candidates:
        c_words = tok_set(c["term"])
        skip = False
        replacements = []
        for idx, existing in enumerate(deduped):
            e_words = tok_set(existing["term"])
            if c_words == e_words:
                skip = True
                break
            elif c_words > e_words:
                replacements.append(idx)
            elif c_words < e_words:
                skip = True
                break
        if skip:
            continue
        for idx in sorted(replacements, reverse=True):
            deduped.pop(idx)
        deduped.append(c)
        if len(deduped) >= top_n:
            break

    return deduped


# ── Radar scoring ─────────────────────────────────────────────────────────────

# Six radar dimensions: keywords that signal papers in that dimension
RADAR_DIMS = [
    # 0 Generation
    ["generat", "diffusion", "synthesis", "text-to-video", "text-to-image",
     "generative", "image synthesis", "video generation", "image generation"],
    # 1 Physics
    ["physics", "simulation", "fluid", "dynamics", "pde", "navier",
     "finite element", "rigid body", "physical", "continuum", "turbulence"],
    # 2 Control
    ["control", "manipulat", "planning", "policy", "reinforcement",
     "actuator", "trajectory", "locomotion", "navigation", "dexterous"],
    # 3 Reasoning
    ["reasoning", "chain-of-thought", "inference", "logic", "understanding",
     "question answer", "comprehension", "commonsense", "causal", "language model"],
    # 4 Efficiency
    ["efficient", "few-shot", "zero-shot", "lightweight", "compress",
     "pruning", "quantization", "distillation", "sample efficient", "low-resource"],
    # 5 Generalization
    ["generali", "transfer", "domain adapt", "robustness", "out-of-distribution",
     "ood", "cross-domain", "unseen", "distribution shift"],
]


def radar_scores(domain_papers: list) -> list[float]:
    """Return 6 normalised scores [0,1] for a domain's papers."""
    texts = [
        (p.get("title", "") + " " + p.get("abstract", "")[:300]).lower()
        for p in domain_papers
    ]
    n = max(len(texts), 1)
    raw = []
    for kws in RADAR_DIMS:
        hits = sum(1 for t in texts if any(k in t for k in kws))
        raw.append(hits / n)

    # Normalise so max dimension = 0.95 (leave visual headroom)
    mx = max(raw) if max(raw) > 0 else 1.0
    return [round(min(v / mx * 0.95, 1.0), 3) for v in raw]


# SVG geometry: center (240,240), outer vertex offsets at score=1
_OUTER = [(0, -170), (150, -90), (150, 90), (0, 170), (-150, 90), (-150, -90)]
CX, CY = 240, 240


def scores_to_points(scores: list[float]) -> str:
    pts = []
    for s, (dx, dy) in zip(scores, _OUTER):
        pts.append(f"{round(CX + s*dx)},{round(CY + s*dy)}")
    return " ".join(pts)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    papers = load_papers()
    if not papers:
        print("No papers found — aborting.", file=sys.stderr)
        sys.exit(1)

    cutoff = (date.today() - timedelta(days=MONTHS * 30)).isoformat()
    recent = [p for p in papers if p.get("published", "") >= cutoff]
    if not recent:
        recent = sorted(papers, key=lambda x: x.get("published", ""), reverse=True)[:800]
    print(f"Using {len(recent)} papers from last {MONTHS} months (cutoff {cutoff})")

    papers_by_domain = {
        d: [p for p in recent if d in p.get("_domains", [])]
        for d in DOMAINS
    }
    for d, ps in papers_by_domain.items():
        print(f"  {d}: {len(ps)} papers")

    all_texts = [
        f"{p.get('title', '')} {p.get('title', '')} {p.get('abstract', '')[:400]}"
        for p in recent
    ]
    all_ng = ngrams(all_texts)
    total = max(len(all_texts), 1)

    # Trending topics (6 个月窗口) — 用于 Topic Cards 深度分析 + Predictions
    trends = {}
    for domain in DOMAINS:
        topics = top_topics(papers_by_domain[domain], all_texts, all_ng, total)
        trends[domain] = topics
        print(f"  {domain} topics (6mo): {[t['display'] for t in topics[:3]]}")

    # ── Hot Topics — 30 天窗口排行 + 与前 30 天对比的 trend 箭头 ──────
    # 单独算一份给 "Hot Research Topics" 图表用,避免大体量主题永远占榜。
    hot_cutoff   = (date.today() - timedelta(days=HOT_DAYS)).isoformat()
    prev_cutoff_ = (date.today() - timedelta(days=HOT_DAYS * 2)).isoformat()
    hot_papers   = [p for p in papers if p.get("published", "") >= hot_cutoff]
    prev_papers_ = [p for p in papers
                    if prev_cutoff_ <= p.get("published", "") < hot_cutoff]
    print(f"Hot window: {len(hot_papers)} last-{HOT_DAYS}d, "
          f"{len(prev_papers_)} prev-{HOT_DAYS}d (for trend)")

    hot_papers_by_d  = {d: [p for p in hot_papers   if d in p.get("_domains", [])]
                        for d in DOMAINS}
    prev_papers_by_d = {d: [p for p in prev_papers_ if d in p.get("_domains", [])]
                        for d in DOMAINS}

    hot_all_texts = [f"{p.get('title','')} {p.get('title','')} {p.get('abstract','')[:400]}"
                     for p in hot_papers]
    hot_all_ng    = ngrams(hot_all_texts) if hot_all_texts else Counter()
    hot_total     = max(len(hot_all_texts), 1)

    prev_ng_by_d  = {
        d: ngrams([f"{p.get('title','')} {p.get('title','')} {p.get('abstract','')[:400]}"
                   for p in prev_papers_by_d[d]])
        for d in DOMAINS
    }

    def _trend_label(count, prev):
        # label ∈ {up, flat, down, new}; pct 可能为 None (prev=0)
        if prev == 0:
            return ("new", None) if count >= 3 else ("flat", None)
        delta_pct = round((count - prev) / prev * 100)
        if delta_pct >= 30:
            return ("up", delta_pct)
        if delta_pct <= -30:
            return ("down", delta_pct)
        return ("flat", delta_pct)

    hot_topics = {}
    for domain in DOMAINS:
        topics = top_topics(hot_papers_by_d[domain], hot_all_texts, hot_all_ng,
                            hot_total, top_n=HOT_TOP_N)
        prev_ng = prev_ng_by_d[domain]
        for t_ in topics:
            prev_c = prev_ng.get(t_["term"], 0)
            label, pct = _trend_label(t_["count"], prev_c)
            t_["prev_count"] = prev_c
            t_["trend"]      = label
            t_["trend_pct"]  = pct
        hot_topics[domain] = topics
        sample = [(t_["display"], t_["count"], t_["trend"], t_.get("trend_pct")) for t_ in topics[:3]]
        print(f"  {domain} hot ({HOT_DAYS}d): {sample}")

    # Radar scores
    radar = {}
    for domain in DOMAINS:
        scores = radar_scores(papers_by_domain[domain])
        radar[domain] = {
            "scores": scores,
            "points": scores_to_points(scores),
        }
        print(f"  {domain} radar: {scores}")

    # Dashboard stats (replaces loading all papers in the browser)
    recent_cutoff = (date.today() - timedelta(days=7)).isoformat()
    all_papers = load_papers()  # full corpus for total counts
    years = sorted({p.get("year") for p in all_papers if p.get("year")})
    stats = {
        "total": len(all_papers),
        "domains": {d: sum(1 for p in all_papers if d in p.get("_domains", [])) for d in DOMAINS},
        "recent": {
            "total": sum(1 for p in all_papers if p.get("published", "") >= recent_cutoff),
            **{d: sum(1 for p in all_papers if p.get("published", "") >= recent_cutoff and d in p.get("_domains", [])) for d in DOMAINS},
        },
        "trends": [
            {"year": y, "counts": {d: sum(1 for p in all_papers if p.get("year") == y and d in p.get("_domains", [])) for d in DOMAINS}}
            for y in years
        ],
    }
    print(f"  stats: total={stats['total']}, recent={stats['recent']['total']}")

    # ── Domain Comparison & Predictions 均改用 30 天窗口 ──
    # 之前用 6mo,数字偏大 (Video Generation 1469),用户觉得太累积、不够"当下"
    # 改用 hot_topics (30d) 之后,Video Generation 那种全年体量大的主题
    # 数字降到 ~200 量级,更能反映"近期热点"

    # Domain Comparison: top topics across all domains by 30d count
    comparison_pool = []
    for d in DOMAINS:
        for t_ in hot_topics[d][:3]:
            comparison_pool.append({
                "topic": t_["display"],
                "domain": d,
                "count": t_["count"],
                "trend": t_.get("trend"),
                "trend_pct": t_.get("trend_pct"),
            })
    comparison_pool.sort(key=lambda x: -x["count"])
    comparison = comparison_pool[:6]
    print(f"  comparison ({HOT_DAYS}d): {[(c['topic'], c['count']) for c in comparison]}")

    # Trend Predictions: 每个 domain 30d 内 top1,带 trend
    PRED_ICONS = {"world_model": "🚀", "physical_ai": "⚡", "medical_ai": "💡"}
    predictions = []
    for d in DOMAINS:
        if not hot_topics[d]:
            continue
        top1 = hot_topics[d][0]
        # 该 domain 30d 内相对热度 (该 topic 占该 domain top8 总和的百分比)
        total_top = sum(t_["count"] for t_ in hot_topics[d][:8]) or 1
        share = round(top1["count"] / total_top * 100)
        predictions.append({
            "topic": top1["display"],
            "domain": d,
            "count": top1["count"],
            "share_pct": share,
            "trend": top1.get("trend"),
            "trend_pct": top1.get("trend_pct"),
            "icon": PRED_ICONS.get(d, "🔮"),
            "keywords": [w for w in top1["term"].split() if w][:3],
        })
    pred_log = [(p["topic"], f"{p['share_pct']}%", p.get("trend")) for p in predictions]
    print(f"  predictions ({HOT_DAYS}d): {pred_log}")

    result = {
        "generated": date.today().isoformat(),
        "months": MONTHS,
        "hot_days": HOT_DAYS,
        "trends": trends,
        "hot_topics": hot_topics,
        "radar": radar,
        "stats": stats,
        "comparison": comparison,
        "predictions": predictions,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {OUTPUT}")


if __name__ == "__main__":
    main()
