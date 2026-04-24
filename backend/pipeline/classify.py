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
    return [name for name, pat in TASK_PATTERNS.items() if pat.search(text)]


# ---------- 领域回填 ----------
_DOMAIN_REGEX = {
    d: re.compile("|".join(rf"\b{re.escape(k)}\b" for k in cfg["keywords"]), re.I)
    for d, cfg in DOMAINS.items()
}


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
    return [enrich(p) for p in papers]
