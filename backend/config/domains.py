"""三大研究领域定义。

领域关键词用于 arXiv/OpenAlex 查询 + 分类辅助。
子任务标签在 pipeline/classify.py 中使用。
"""

from __future__ import annotations
import json
from pathlib import Path

DOMAINS = {
    "world_model": {
        "label_zh": "World Model",
        "label_en": "World Model",
        "icon": "🌍",
        "description": "视频生成、场景重建、强化学习、Sim2Real 等构建智能体对世界建模的方法",
        "keywords": [
            "world model", "video generation", "video diffusion",
            "scene reconstruction", "neural radiance field", "NeRF",
            "model-based reinforcement learning", "sim-to-real",
            "foundation model", "action model", "predictive model",
        ],
    },
    "physical_ai": {
        "label_zh": "具身智能",
        "label_en": "Physical AI",
        "icon": "🤖",
        "description": "物理启发的神经网络、机器人学习、流体/气候模拟、3D重建",
        "keywords": [
            "physics-informed neural network", "PINN", "neural operator",
            "embodied AI", "robot learning", "robotic manipulation",
            "fluid simulation", "climate modeling", "3D reconstruction",
            "humanoid robot", "dexterous manipulation",
        ],
    },
    "medical_ai": {
        "label_zh": "医疗AI",
        "label_en": "Medical AI",
        "icon": "🏥",
        "description": "医学影像、癌症检测、药物发现、临床决策、手术导航",
        "keywords": [
            "medical imaging", "pathology", "cancer detection",
            "drug discovery", "molecular", "protein structure",
            "clinical decision support", "surgical navigation",
            "health monitoring", "medical vision-language model",
        ],
    },
}

DOMAIN_IDS = list(DOMAINS.keys())

_AUTO_KW_PATH   = Path(__file__).parent / "keywords_auto.json"
_MANUAL_KW_PATH = Path(__file__).parent / "keywords_manual.json"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_manual_subdomains(domain: str) -> dict[str, list[str]]:
    """Return {SubdomainLabel: [keywords]} for a domain from keywords_manual.json."""
    data = _load_json(_MANUAL_KW_PATH)
    return {k: v for k, v in data.get(domain, {}).items() if not k.startswith("_")}


def get_keywords(domain: str) -> list[str]:
    """Return core + manual subdomain + LLM-auto keywords for a domain, deduplicated."""
    core = DOMAINS[domain]["keywords"]
    manual = [kw for kws in get_manual_subdomains(domain).values() for kw in kws]
    auto   = _load_json(_AUTO_KW_PATH).get(domain, [])
    seen: set[str] = set()
    result: list[str] = []
    for kw in core + manual + auto:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            result.append(kw)
    return result
