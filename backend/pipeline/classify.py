"""论文分类 & 元数据提取。

职责（对抓取器返回的论文做补强）:
  1. 论文类型: Method / Dataset / Survey
  2. 代码链接提取 (GitHub / GitLab / HuggingFace)
  3. 任务子标签 (从标题+摘要匹配领域关键词)
  4. 缺失 domains 的回填
"""

from __future__ import annotations
import re

from backend.config import DOMAINS
from backend.config.domains import get_keywords, get_manual_subdomains

# ---------- 论文类型 ----------
_TYPE_PATTERNS = {
    "Survey":  re.compile(r"\b(survey|review|overview|comprehensive study)\b", re.I),
    "Dataset": re.compile(r"\b(dataset|benchmark|corpus|a new dataset)\b", re.I),
}


def classify_type(title: str, abstract: str) -> str:
    text = f"{title} {abstract}"
    for t, pat in _TYPE_PATTERNS.items():
        if pat.search(text):
            return t
    return "Method"


# ---------- 代码链接 ----------
_CODE_RE = re.compile(
    r"https?://(?:github\.com|gitlab\.com|huggingface\.co|bitbucket\.org)/[^\s\)\]\>\"]+",
    re.I,
)


def extract_code_links(title: str, abstract: str) -> list[str]:
    raw = _CODE_RE.findall(f"{title} {abstract}")
    # 去重 + 截掉尾部标点
    seen = set()
    out = []
    for url in raw:
        url = url.rstrip(".,;:")
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


# ---------- 任务标签（正则）----------
# 子任务 → 正则。可按需扩展。
TASK_PATTERNS: dict[str, re.Pattern] = {
    # World Model
    "WorldModel":    re.compile(r"\bworld model(s|ing)?\b", re.I),
    "VidGen":        re.compile(r"\bvideo (generation|diffusion|synthesis)\b", re.I),
    "NeRF":          re.compile(r"\b(nerf|neural radiance field|gaussian splatting|3dgs)\b", re.I),
    "MBRL":          re.compile(r"\bmodel[- ]based (rl|reinforcement learning)\b", re.I),
    "Sim2Real":      re.compile(r"\bsim[- ]?to[- ]?real\b|\bsim2real\b", re.I),
    # Physical AI
    "PINN":          re.compile(r"\bphysics[- ]informed (neural )?(network|learning)\b|\bpinn\b", re.I),
    "NeuralOp":      re.compile(r"\bneural operator(s)?\b", re.I),
    "Embodied":      re.compile(r"\bembodied (ai|intelligence|agent)\b", re.I),
    "RobotLearn":    re.compile(r"\brobot(ic)? (learning|manipulation|policy)\b", re.I),
    "FluidSim":      re.compile(r"\b(fluid|turbulence|aerodynamics) (simulation|dynamics|modeling)\b", re.I),
    "3DRecon":       re.compile(r"\b3d reconstruction\b", re.I),
    # Medical AI
    "Pathology":     re.compile(r"\b(pathology|histopatholog|whole[- ]slide image|wsi)\b", re.I),
    "MedImg":        re.compile(r"\bmedical imag(ing|e)\b|\bct scan\b|\bmri\b", re.I),
    "Cancer":        re.compile(r"\b(cancer|tumor|oncolog|carcinoma)\b", re.I),
    "MedVLM":        re.compile(r"\bmedical (vision[- ]language|vlm)\b|\bclip.*medical\b", re.I),
    "DrugMol":       re.compile(r"\b(drug discovery|molecular (generation|design|property))\b", re.I),
    "Protein":       re.compile(r"\bprotein (structure|folding|design|language model)\b", re.I),
    "Clinical":      re.compile(r"\bclinical (decision|note|prediction)\b|\bEHR\b", re.I),
    "Surgery":       re.compile(r"\bsurg(ery|ical) (navigation|workflow|phase)\b", re.I),
}


def tag_tasks(title: str, abstract: str) -> list[str]:
    text = f"{title} {abstract}"
    tags = [name for name, pat in TASK_PATTERNS.items() if pat.search(text)]
    tags += [name for name, pat in _MANUAL_TASK_PATTERNS.items()
             if pat.search(text) and name not in tags]
    return tags


# ---------- 领域回填 ----------
def _build_manual_task_patterns() -> dict[str, re.Pattern]:
    """keywords_manual.json の子领域名 → task 正则，供 tag_tasks() 使用。"""
    patterns: dict[str, re.Pattern] = {}
    for domain in DOMAINS:
        for label, keywords in get_manual_subdomains(domain).items():
            if not keywords:
                continue
            # tag key: 去掉非字母数字，CamelCase，如 "Robot World Model" → "RobotWorldModel"
            tag = re.sub(r'[^a-zA-Z0-9]', '', label.title().replace(' ', ''))
            expr = "|".join(rf"\b{re.escape(k)}\b" for k in keywords)
            patterns[tag] = re.compile(expr, re.I)
    return patterns

_MANUAL_TASK_PATTERNS: dict[str, re.Pattern] = _build_manual_task_patterns()


def _build_domain_regex() -> dict:
    return {
        d: re.compile("|".join(rf"\b{re.escape(k)}\b" for k in get_keywords(d)), re.I)
        for d in DOMAINS
    }

_DOMAIN_REGEX = _build_domain_regex()


def infer_domains(title: str, abstract: str, existing: list[str] | None = None) -> list[str]:
    text = f"{title} {abstract}"
    hits = [d for d, rx in _DOMAIN_REGEX.items() if rx.search(text)]
    if existing:
        hits = list({*existing, *hits})
    return hits


# ---------- 总入口 ----------
def enrich(paper: dict) -> dict:
    """给抓取到的原始论文补全分类字段，返回新 dict。"""
    title = paper.get("title") or ""
    abstract = paper.get("abstract_excerpt") or ""
    paper = {**paper}
    paper["paper_type"] = classify_type(title, abstract)
    paper["code_links"] = extract_code_links(title, abstract)
    paper["tasks"] = tag_tasks(title, abstract)
    paper["domains"] = infer_domains(title, abstract, paper.get("domains"))
    return paper


def enrich_many(papers: list[dict]) -> list[dict]:
    """同步入口：只跑正则。需要 LLM 用 enrich_many_async()。"""
    return [enrich(p) for p in papers]


async def enrich_many_async(papers: list[dict], skip_existing: bool = True) -> list[dict]:
    """异步入口：先跑正则 enrich，再用 LLM 补 topics + 合并 domains + 覆盖 paper_type。

    skip_existing=True 时查 Supabase 已有 topics 的论文跳过 LLM 调用（默认开启，
    避免每次抓取重复跑 LLM 浪费配额）。LLM 失败时静默回退到正则结果，主流程不阻断。
    """
    enriched = [enrich(p) for p in papers]

    # 查 Supabase 已有 topics 的论文，复用结果跳过 LLM
    existing_topics: dict[str, list] = {}
    if skip_existing:
        try:
            from backend.db import fetch_existing_topics
            ids = [p["id"] for p in enriched if p.get("id")]
            existing_topics = fetch_existing_topics(ids)
            if existing_topics:
                print(f"[enrich_async] skipping {len(existing_topics)} papers with existing topics")
        except Exception as e:
            print(f"[enrich_async] skip-existing query failed (continuing): {e}")

    # 把已有 topics 写回 paper（这些会保留，不被 LLM 覆盖；也用于 _already_done 检查）
    for p in enriched:
        if p["id"] in existing_topics:
            p["topics"] = existing_topics[p["id"]]

    # LLM 输入：把 abstract_excerpt 映射成 cleaning/llm_classify 期望的 abstract 字段；
    # 已有 _topics 让 LLM 内部的 _already_done() 自动跳过
    llm_input = []
    for p in enriched:
        if not (p.get("abstract_excerpt") or "").strip():
            continue
        item = {
            "id":       p["id"],
            "title":    p.get("title", ""),
            "abstract": p["abstract_excerpt"],
        }
        if p.get("topics"):
            item["_topics"] = p["topics"]
        llm_input.append(item)

    if not llm_input:
        return enriched

    try:
        from cleaning.llm_classify import classify_papers_with_llm_async
        await classify_papers_with_llm_async(llm_input)
    except Exception as e:
        print(f"[enrich_async] LLM failed: {e} — keeping regex results")
        return enriched

    # 合回 LLM 结果到 Supabase schema 字段名（_already_done 跳过的 _topics 不会被改写）
    llm_by_id = {p["id"]: p for p in llm_input}
    for p in enriched:
        llm_p = llm_by_id.get(p["id"])
        if not llm_p:
            continue
        regex_domains = set(p.get("domains") or [])
        llm_domains = set(llm_p.get("_domains") or [])
        merged = sorted(regex_domains | llm_domains)
        if merged:
            p["domains"] = merged
        if llm_p.get("_topics"):
            p["topics"] = llm_p["_topics"]
        if llm_p.get("type"):
            p["paper_type"] = llm_p["type"]

    return enriched
