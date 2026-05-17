"""
LLM-based paper classification using any OpenAI-compatible API.
- Replaces regex domain matching with semantic understanding
- Discovers dynamic subtopic tags instead of hardcoded task labels
- Caches results so papers are only classified once
- Concurrent async batching (Semaphore-controlled) for throughput

Supported providers (set env vars):
  智谱 GLM-4-Flash (free, recommended):
    LLM_API_KEY=<your_key>
    LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
    LLM_MODEL=glm-4-flash

  DeepSeek (cheap):
    LLM_BASE_URL=https://api.deepseek.com/v1
    LLM_MODEL=deepseek-chat

  Gemini (free tier, OpenAI-compatible endpoint):
    LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
    LLM_MODEL=gemini-2.0-flash

  Groq (free tier):
    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_MODEL=llama-3.3-70b-versatile
"""

import asyncio
import json
import logging
import os
import sys
from typing import List, Dict

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # progress bar disabled if tqdm not installed

logger = logging.getLogger(__name__)

DEFAULT_CACHE_FILE = "output/llm_classify_cache.json"


def _cache_file_path() -> str:
    """每次调用时读环境变量，支持运行时切换 cache 文件（如多 key 并行跑）。"""
    return os.environ.get("LLM_CACHE_FILE") or DEFAULT_CACHE_FILE
# 可通过环境变量覆盖：LLM_BATCH_SIZE / LLM_CONCURRENCY
BATCH_SIZE = int(os.environ.get("LLM_BATCH_SIZE", "30"))   # papers per API call
CONCURRENCY = int(os.environ.get("LLM_CONCURRENCY", "10")) # concurrent in-flight batches
SAVE_EVERY_N_BATCH = int(os.environ.get("LLM_SAVE_EVERY", "1"))  # flush cache every N batches

# Defaults target 智谱 GLM-4-Flash (completely free)
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "glm-4-flash"

DOMAIN_DESCRIPTIONS = {
    "world_model": (
        "World Models: video generation/prediction, neural radiance fields (NeRF), "
        "3D Gaussian splatting, model-based reinforcement learning, sim-to-real transfer, "
        "embodied agents with world models, scene representation learning, latent dynamics"
    ),
    "physical_ai": (
        "Physical AI: physics-informed neural networks (PINN), neural operators (FNO/DeepONet), "
        "robotics/manipulation/grasping, embodied intelligence, fluid dynamics, climate modeling, "
        "molecular dynamics, material simulation, physical reasoning"
    ),
    "medical_ai": (
        "Medical AI: medical image analysis (MRI/CT/X-ray), pathology/histopathology, "
        "cancer detection/segmentation, drug discovery/molecular design, protein structure, "
        "clinical decision support, surgical robotics, medical VLMs/LLMs, health monitoring"
    ),
}

# 三大领域白名单 — LLM 偶尔会自创非白名单的 domain（如 environmental_science、
# biotechnology、climate_modeling 等），在写入前必须过滤掉，避免污染前端筛选。
DOMAIN_WHITELIST = set(DOMAIN_DESCRIPTIONS.keys())


def _load_cache() -> Dict:
    if os.path.exists(_cache_file_path()):
        try:
            with open(_cache_file_path(), "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache: Dict):
    os.makedirs("output", exist_ok=True)
    tmp = _cache_file_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.replace(tmp, _cache_file_path())


def _build_prompt(papers: List[Dict]) -> str:
    papers_text = "\n\n".join(
        f"[{i+1}] Title: {p.get('title', '')}\nAbstract: {p.get('abstract', '')[:400]}"
        for i, p in enumerate(papers)
    )
    domains_desc = "\n".join(f"- {k}: {v}" for k, v in DOMAIN_DESCRIPTIONS.items())

    return f"""Classify each research paper and extract its specific research subtopics.

Domain definitions:
{domains_desc}

Papers to classify:
{papers_text}

Return a JSON array with exactly {len(papers)} objects, one per paper in order:
[
  {{
    "index": 1,
    "domains": ["world_model"],
    "topics": ["video diffusion model", "future frame prediction"],
    "type": "Method"
  }}
]

Rules:
- domains: subset of [world_model, physical_ai, medical_ai]. Empty list if not relevant to any.
- topics: 2-4 specific research subtopics as lowercase strings (e.g. "3d gaussian splatting", "robotic grasping"). Be specific, not generic.
- type: "Method", "Dataset", or "Survey" only.

Return only valid JSON, no explanation."""


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.split("```")[0].strip()
    return text


async def _classify_batch_async(papers: List[Dict], client, model: str) -> List[Dict]:
    prompt = _build_prompt(papers)
    # 单 batch 输出大约 80 token/篇 × BATCH_SIZE + JSON 框架
    out_tokens = max(1500, len(papers) * 100 + 200)

    # 429/5xx 限流 → 长退避重试（GLM 免费层限流窗口约 1 分钟）
    delay = 30.0
    for attempt in range(6):
        try:
            resp = await client.chat.completions.create(
                model=model,
                max_tokens=out_tokens,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except Exception as e:
            msg = str(e).lower()
            is_throttle = "429" in msg or "rate" in msg or "限速" in msg or "速率" in msg
            if attempt == 5 or not is_throttle:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 180)

    text = _strip_json_fence(resp.choices[0].message.content or "")
    return json.loads(text)


async def classify_papers_with_llm_async(papers: List[Dict]) -> List[Dict]:
    """Async, concurrent LLM classification with persistent cache."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.warning("openai package not installed — skipping LLM classification")
        return papers

    # 支持多 key 轮换：LLM_API_KEYS=key1,key2,key3 优先于 LLM_API_KEY
    # 多 key 时 round-robin 分配 batch，每 key 独立维持限流配额 → 速度线性扩展
    api_keys_raw = (
        os.environ.get("LLM_API_KEYS")
        or os.environ.get("LLM_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or ""
    )
    api_keys = [k.strip() for k in api_keys_raw.split(",") if k.strip()]
    if not api_keys:
        logger.warning("LLM_API_KEY(S) not set — skipping LLM classification")
        return papers

    base_url = os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL
    model = os.environ.get("LLM_MODEL") or DEFAULT_MODEL
    logger.info(f"LLM provider: base_url={base_url}, model={model}, keys={len(api_keys)}")

    # 每个 key 一个 AsyncOpenAI client
    clients = [AsyncOpenAI(api_key=k, base_url=base_url) for k in api_keys]
    cache = _load_cache()

    def _already_done(p: Dict) -> bool:
        return p.get("id") in cache or bool(p.get("_topics"))

    uncached = [(i, p) for i, p in enumerate(papers) if not _already_done(p)]
    logger.info(
        f"LLM classifying {len(uncached)} papers "
        f"({len(papers) - len(uncached)} skipped: cache or prior _topics) "
        f"[batch={BATCH_SIZE}, concurrency={CONCURRENCY}]"
    )

    if not uncached:
        return _apply_cached(papers, cache)

    # Split into batches
    batches: List[List[tuple]] = [
        uncached[i:i + BATCH_SIZE] for i in range(0, len(uncached), BATCH_SIZE)
    ]
    total_batches = len(batches)
    # 总并发 = CONCURRENCY × key 数（每 key 独立限流，可以同时跑 CONCURRENCY 个 batch）
    sem = asyncio.Semaphore(CONCURRENCY * len(clients))
    done_count = 0
    lock = asyncio.Lock()  # protect cache + papers writes

    # tqdm 进度条：tty 用滚动条；非 tty（nohup/CI）每 60 秒追加一行
    is_tty = sys.stderr.isatty()
    pbar = (
        tqdm(
            total=len(uncached),
            desc="LLM classify",
            unit="paper",
            dynamic_ncols=True,
            disable=False,
            mininterval=60 if not is_tty else 0.1,
            ascii=not is_tty,
            file=sys.stderr,
        )
        if tqdm is not None
        else None
    )

    async def process_batch(batch_num: int, batch: List[tuple]) -> None:
        nonlocal done_count
        indices = [x[0] for x in batch]
        batch_papers = [x[1] for x in batch]
        # round-robin 选 client：每 key 独立限流，避免单 key 撞配额
        client = clients[batch_num % len(clients)]

        async with sem:
            try:
                results = await _classify_batch_async(batch_papers, client, model)
            except Exception as e:
                logger.error(f"LLM batch {batch_num} failed: {e}")
                async with lock:
                    done_count += 1
                    if pbar is not None:
                        pbar.update(len(batch))
                return

        async with lock:
            for result in results:
                idx_in_batch = result.get("index", 0) - 1
                if not (0 <= idx_in_batch < len(batch_papers)):
                    continue
                paper_idx = indices[idx_in_batch]
                paper_id = batch_papers[idx_in_batch].get("id", "")

                # 过滤白名单：LLM 偶尔会自创非白名单 domain，必须丢弃
                raw_domains = result.get("domains") or []
                clean_domains = [d for d in raw_domains if d in DOMAIN_WHITELIST]
                classification = {
                    "domains": clean_domains,
                    "topics": [t.lower().strip() for t in result.get("topics", [])],
                    "type": result.get("type", "Method"),
                }
                cache[paper_id] = classification
                papers[paper_idx]["_domains"] = clean_domains
                papers[paper_idx]["_topics"] = classification["topics"]
                papers[paper_idx]["type"] = classification["type"]

            done_count += 1
            if pbar is not None:
                pbar.update(len(batch))
            if done_count % SAVE_EVERY_N_BATCH == 0 or done_count == total_batches:
                _save_cache(cache)

    try:
        await asyncio.gather(*[process_batch(i, b) for i, b in enumerate(batches)])
    finally:
        if pbar is not None:
            pbar.close()

    _save_cache(cache)
    _apply_cached(papers, cache)
    logger.info("LLM classification complete")
    return papers


def _apply_cached(papers: List[Dict], cache: Dict) -> List[Dict]:
    """Backfill papers that already had a cache entry but weren't touched this run."""
    for paper in papers:
        paper_id = paper.get("id", "")
        if paper_id in cache and "_topics" not in paper:
            cached = cache[paper_id]
            # 过滤白名单：cache 可能含旧的脏 domain
            cached_domains = [d for d in (cached.get("domains") or []) if d in DOMAIN_WHITELIST]
            paper["_domains"] = cached_domains or paper.get("_domains", [])
            paper["_topics"] = cached.get("topics", [])
            if not paper.get("type"):
                paper["type"] = cached.get("type", "Method")
    return papers


def classify_papers_with_llm(papers: List[Dict]) -> List[Dict]:
    """Sync wrapper. Don't call from inside a running event loop — use the async API instead."""
    return asyncio.run(classify_papers_with_llm_async(papers))
