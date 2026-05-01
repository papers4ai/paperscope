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
MONTHS = 6     # look-back window
TOP_N = 8      # topics per domain

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
               total: int) -> list:
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
        if len(deduped) >= TOP_N:
            break

    return deduped


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

    trends = {}
    for domain in DOMAINS:
        topics = top_topics(papers_by_domain[domain], all_texts, all_ng, total)
        trends[domain] = topics
        print(f"  {domain}: {[t['display'] for t in topics]}")

    result = {
        "generated": date.today().isoformat(),
        "months": MONTHS,
        "trends": trends,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {OUTPUT}")


if __name__ == "__main__":
    main()
