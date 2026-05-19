"""启发式过滤：移除"被 LLM 错贴标签但没有任何具体证据"的 domain。

每个 domain 需要 至少一条 锚点证据才会被保留：
  - 论文的 task tag 命中该 domain 的 anchor task 集合，或
  - 论文的 title / topics 文本里命中该 domain 的关键词

否则该 domain 从 _domains 中移除。若移除后 _domains 变空，调用方
可以选择丢弃该论文。

锚点 task 来自 frontend/data/task_meta.json 里的 zh/en 含义；
keywords 是手工挑的强信号短语。
"""
from __future__ import annotations
from typing import Iterable

WHITELIST = ("world_model", "physical_ai", "medical_ai")

# 每个 domain 的 "task 锚点" — 命中其中任一就足以保留该 domain
DOMAIN_ANCHOR_TASKS: dict[str, frozenset[str]] = {
    "world_model": frozenset({
        "WorldModel", "ActionModel", "VidGen", "NeRF", "MBRL", "Sim2Real",
        "EmbodiedWM", "Predictive", "DiffusionWM", "3DRecon",
        "RobotWorldModel", "WorldActionModel", "AutonomousDrivingWorldModel",
    }),
    "physical_ai": frozenset({
        "PINN", "NeuralOp", "RobotLearn", "Sim2Real", "Embodied",
        "FluidSim", "Climate", "ActionModel",
    }),
    "medical_ai": frozenset({
        "MedImg", "Pathology", "Cancer", "MedVLM", "DrugMol", "Protein",
        "Clinical", "Surgery", "HealthMon", "AngiographySynthesis",
    }),
}

# 每个 domain 的 "关键词锚点" — 在 title.lower() 或任一 topic.lower() 里
# 包含子串就算命中。挑过强信号、避免泛词（"learning"、"model" 不算）。
DOMAIN_ANCHOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "world_model": (
        "world model", "world-model",
        "3d gaussian", "3dgs", "gaussian splat",
        "nerf", "neural radiance", "radiance field",
        "video diffusion", "video generation", "video prediction",
        "novel view synthesis", "scene synthesis", "scene generation",
        "4d scene", "4d generation",
        "model-based rl", "model-based reinforcement",
        "model based rl", "model based reinforcement",
        "world simulator", "neural simulator", "learned simulator",
        "sim-to-real", "sim2real",
        "future frame", "future-frame",
        "latent dynamics",
        "embodied world",
        "autonomous driving world",
        "occupancy prediction",
    ),
    "physical_ai": (
        "physics-informed", "physics informed", "pinn",
        "neural operator", "fno ", "deeponet",
        "robot manipulation", "robotic manipulation",
        "robot grasping", "robotic grasping",
        "robot learning", "robot policy", "robotic policy",
        "robot locomotion", "robotic locomotion",
        "legged robot", "quadruped",
        "embodied", "sim-to-real", "sim2real",
        "fluid simulation", "fluid dynamics",
        "climate model", "weather forecast", "weather prediction",
        "molecular dynamics", "md simulation",
        "material simulation",
        "physical reasoning", "physical world",
    ),
    "medical_ai": (
        "medical imag", "clinical", "patient",
        " ct ", "ct scan", "mri", "x-ray", "xray", "ultrasound",
        "ecg", "ekg",
        "histopath", "pathology",
        "cancer", "tumor", "tumour", "lesion", "metasta",
        "drug discov", "drug design", "drug repurpos",
        "drug-target", "drug target",
        "molecular generation", "molecular property",
        "protein folding", "protein structure",
        "clinical decision", "ehr ", "electronic health",
        "surgery", "surgical",
        "radiolog", "diagnos",
        "biomedical",
        "health monitor", "vital sign",
        "icu ", "intensive care",
        "medical vlm", "medical llm",
    ),
}


def _normalize_text(*parts: object) -> str:
    """把若干字段拼成一个用来扫关键词的 lowercase 字符串。"""
    out = []
    for p in parts:
        if p is None:
            continue
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, (list, tuple)):
            for x in p:
                if isinstance(x, str):
                    out.append(x)
    return " ".join(out).lower()


def domain_is_supported(
    domain: str,
    tasks: Iterable[str] | None,
    title: str | None,
    topics: Iterable[str] | None,
) -> bool:
    """判断 domain 是否有锚点证据支持。"""
    if domain not in WHITELIST:
        return False
    task_set = set(tasks or [])
    if task_set & DOMAIN_ANCHOR_TASKS[domain]:
        return True
    text = _normalize_text(title, topics)
    for kw in DOMAIN_ANCHOR_KEYWORDS[domain]:
        if kw in text:
            return True
    return False


def filter_domains(
    domains: Iterable[str] | None,
    tasks: Iterable[str] | None,
    title: str | None,
    topics: Iterable[str] | None,
) -> list[str]:
    """根据锚点过滤 domains。空白名单 / 非白名单 一律剔除。"""
    if not domains:
        return []
    return [d for d in domains
            if d in WHITELIST and domain_is_supported(d, tasks, title, topics)]
