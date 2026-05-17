"""
LLM-based 论文中文 AI 解读：summary_zh (3 句中文摘要) + insights (3 个 key points)

复用 llm_classify 的架构：async + 多 key round-robin + 429 重试 + cache + 白名单
独立 cache 文件 (output/llm_summary_cache.json)，独立 batch size。

环境变量同 llm_classify：
  LLM_API_KEYS / LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
  可选 LLM_CACHE_FILE （默认 output/llm_summary_cache.json）
  可选 LLM_BATCH_SIZE_SUM (默认 8 - summary 输出 token 多，batch 小一些)
  可选 LLM_CONCURRENCY (沿用 llm_classify 默认 10)
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
    tqdm = None

logger = logging.getLogger(__name__)

DEFAULT_CACHE_FILE = "output/llm_summary_cache.json"
BATCH_SIZE = int(os.environ.get("LLM_BATCH_SIZE_SUM", "8"))
CONCURRENCY = int(os.environ.get("LLM_CONCURRENCY", "10"))
SAVE_EVERY_N_BATCH = int(os.environ.get("LLM_SAVE_EVERY", "1"))

DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "glm-4-flash"


def _cache_file_path() -> str:
    return os.environ.get("LLM_CACHE_FILE_SUM") or DEFAULT_CACHE_FILE


def _load_cache() -> Dict:
    path = _cache_file_path()
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache: Dict):
    path = _cache_file_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, path)


def _build_prompt(papers: List[Dict]) -> str:
    """生成 batch prompt 让 LLM 同时解读多篇论文。"""
    papers_text = "\n\n".join(
        f"[{i+1}] Title: {p.get('title', '')}\nAbstract: {p.get('abstract', '')[:800]}"
        for i, p in enumerate(papers)
    )
    return f"""你是科研论文中文助手。请为下面每篇论文用简体中文生成：
1. summary: 3 句话概括论文的研究问题、方法、主要结果（每句 30-60 字）
2. insights: 3 条 key insights，每条一句话（强调创新点 / 方法亮点 / 实验关键发现）

输入论文：
{papers_text}

返回一个 JSON 数组，长度严格等于 {len(papers)}，按输入顺序：
[
  {{
    "index": 1,
    "summary": "本文研究...。方法上...。实验表明...。",
    "insights": ["创新点：...", "方法亮点：...", "关键发现：..."]
  }}
]

要求：
- 全部中文，不要英文术语长翻译（专有名词如 NeRF / Transformer 可保留）
- summary 3 句，每句独立成意，整段中性客观
- insights 3 条，每条聚焦一个 takeaway，不要重复 summary
- 只返回 JSON 数组，不要 markdown 代码块，不要解释。"""


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.split("```")[0].strip()
    return text


async def _summarize_batch_async(papers: List[Dict], client, model: str) -> List[Dict]:
    prompt = _build_prompt(papers)
    # summary ~150 字 + insights 3 × 50 字 ≈ 300 tokens/篇 + JSON overhead
    out_tokens = max(2000, len(papers) * 350 + 300)

    delay = 30.0
    for attempt in range(6):
        try:
            resp = await client.chat.completions.create(
                model=model,
                max_tokens=out_tokens,
                temperature=0.3,
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


async def summarize_papers_async(papers: List[Dict]) -> List[Dict]:
    """对 papers 列表生成 summary_zh + insights，结果写入 paper["summary_zh"], paper["insights"]。

    paper 至少要有 id, title, abstract 字段。
    跳过已有 summary_zh 或在 cache 里的论文。
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.warning("openai package not installed — skipping LLM summarize")
        return papers

    api_keys_raw = (
        os.environ.get("LLM_API_KEYS")
        or os.environ.get("LLM_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or ""
    )
    api_keys = [k.strip() for k in api_keys_raw.split(",") if k.strip()]
    if not api_keys:
        logger.warning("LLM_API_KEY(S) not set — skipping summarize")
        return papers

    base_url = os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL
    model = os.environ.get("LLM_MODEL") or DEFAULT_MODEL
    logger.info(f"LLM summarize: base_url={base_url}, model={model}, keys={len(api_keys)}")

    clients = [AsyncOpenAI(api_key=k, base_url=base_url) for k in api_keys]
    cache = _load_cache()

    def _already_done(p: Dict) -> bool:
        return p.get("id") in cache or bool(p.get("summary_zh"))

    uncached = [(i, p) for i, p in enumerate(papers) if not _already_done(p)]
    logger.info(
        f"LLM summarize: {len(uncached)} papers to process "
        f"({len(papers) - len(uncached)} skipped) "
        f"[batch={BATCH_SIZE}, concurrency={CONCURRENCY}, keys={len(api_keys)}]"
    )

    if not uncached:
        return _apply_cached(papers, cache)

    batches = [uncached[i:i + BATCH_SIZE] for i in range(0, len(uncached), BATCH_SIZE)]
    total_batches = len(batches)
    sem = asyncio.Semaphore(CONCURRENCY * len(clients))
    done_count = 0
    lock = asyncio.Lock()

    is_tty = sys.stderr.isatty()
    pbar = (
        tqdm(
            total=len(uncached),
            desc="LLM summarize",
            unit="paper",
            dynamic_ncols=True,
            disable=False,
            mininterval=60 if not is_tty else 0.1,
            ascii=not is_tty,
            file=sys.stderr,
        )
        if tqdm is not None else None
    )

    async def process_batch(batch_num: int, batch: List[tuple]) -> None:
        nonlocal done_count
        indices = [x[0] for x in batch]
        batch_papers = [x[1] for x in batch]
        client = clients[batch_num % len(clients)]

        async with sem:
            try:
                results = await _summarize_batch_async(batch_papers, client, model)
            except Exception as e:
                logger.error(f"summarize batch {batch_num} failed: {e}")
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
                summary = (result.get("summary") or "").strip()
                insights = [s.strip() for s in (result.get("insights") or []) if s.strip()][:3]
                if not summary:
                    continue
                payload = {"summary_zh": summary, "insights": insights}
                cache[paper_id] = payload
                papers[paper_idx]["summary_zh"] = summary
                papers[paper_idx]["insights"] = insights

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
    logger.info("LLM summarize complete")
    return papers


def _apply_cached(papers: List[Dict], cache: Dict) -> List[Dict]:
    for p in papers:
        pid = p.get("id", "")
        if pid in cache and not p.get("summary_zh"):
            entry = cache[pid]
            p["summary_zh"] = entry.get("summary_zh", "")
            p["insights"] = entry.get("insights", [])
    return papers


def summarize_papers(papers: List[Dict]) -> List[Dict]:
    """Sync wrapper."""
    return asyncio.run(summarize_papers_async(papers))
