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
import re
import sys
from typing import List, Dict, Optional

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
    """生成 batch prompt 让 LLM 同时解读多篇论文（中英双语）。"""
    papers_text = "\n\n".join(
        f"[{i+1}] Title: {p.get('title', '')}\nAbstract: {p.get('abstract', '')[:800]}"
        for i, p in enumerate(papers)
    )
    return f"""You are a research paper assistant. For each paper below, generate **both** Chinese and English versions:
1. summary_zh / summary_en: 3-sentence summary covering research problem, method, and main results (each sentence 30-60 chars in zh, 60-120 chars in en)
2. insights_zh / insights_en: 3 key insights, each one sentence (novelty / methodological highlight / experimental finding)

Papers:
{papers_text}

Return a JSON array of length exactly {len(papers)}, in input order:
[
  {{
    "index": 1,
    "title": "<copy the paper's title VERBATIM, used to align your output back to the input>",
    "summary_zh": "本文研究...。方法上...。实验表明...。",
    "summary_en": "This paper studies... The method... Experiments show...",
    "insights_zh": ["创新点：...", "方法亮点：...", "关键发现：..."],
    "insights_en": ["Novelty: ...", "Method highlight: ...", "Key finding: ..."]
  }}
]

Requirements:
- index/title: index is the input number; title MUST be copied verbatim from the matching paper above (this is how each result is matched back — a wrong title attaches the summary to the wrong paper)
- summary_zh: 简体中文 3 句，每句独立成意，中性客观（专有名词如 NeRF / Transformer 可保留英文）
- summary_en: English, 3 sentences, parallel structure to summary_zh
- insights_*: exactly 3 entries each, focus on one takeaway each, do not repeat summary
- zh and en should convey the SAME content (one is not a literal translation of the other, but the meaning matches)
- Output ONLY the JSON array, no markdown fences, no explanation."""


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.split("```")[0].strip()
    return text


def _norm_title(t: str) -> str:
    """小写 + 去掉所有非字母数字，便于鲁棒比对（容忍标点/空格/大小写差异）。"""
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def _title_match(a: str, b: str) -> bool:
    """判断两个标题是否指同一篇：规范化后相等 / 一方是另一方前缀（容忍截断）/ 词集高度重叠。"""
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # 容忍模型截断标题：取较短一方至少 15 字符作为前缀比对
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(shorter) >= 15 and longer.startswith(shorter):
        return True
    # 词集 Jaccard（防止轻微改写/漏词）
    wa = set(re.findall(r"[a-z0-9]+", (a or "").lower()))
    wb = set(re.findall(r"[a-z0-9]+", (b or "").lower()))
    if wa and wb:
        inter = len(wa & wb)
        union = len(wa | wb)
        if union and inter / union >= 0.6:
            return True
    return False


def _resolve_result_pos(
    result: Dict, result_k: int, n_results: int, batch_papers: List[Dict]
) -> Optional[int]:
    """把一条 LLM 返回结果对应回 batch 内的论文下标（0-based）。

    优先用模型回显的 title 做内容级匹配，避免单纯信任 index 导致张冠李戴：
      1. title 命中唯一论文 → 用它
      2. 有 title 但 batch 里没有任何匹配 → 判为越界/幻觉结果，返回 None（宁可丢弃也不污染）
      3. 无 title / title 歧义 → 退回 index 提示，再退回位置序 k
    """
    rtitle = (result.get("title") or "").strip()
    if rtitle:
        cands = [i for i, bp in enumerate(batch_papers)
                 if _title_match(rtitle, bp.get("title", ""))]
        if len(cands) == 1:
            return cands[0]
        if len(cands) == 0:
            return None  # 标题对不上任何输入论文 → 不要安插到别人头上
        # len(cands) > 1：标题歧义，落到 index/位置兜底
    idx = result.get("index")
    if isinstance(idx, int) and 1 <= idx <= len(batch_papers):
        return idx - 1
    if n_results == len(batch_papers) and 0 <= result_k < len(batch_papers):
        return result_k
    return None


async def _summarize_batch_async(papers: List[Dict], client, model: str) -> List[Dict]:
    prompt = _build_prompt(papers)
    # 双语: summary_zh ~150 + summary_en ~200 + 3×insights_zh ~150 + 3×insights_en ~200
    # ≈ 700 tokens/篇 + JSON overhead
    out_tokens = max(3000, len(papers) * 750 + 500)

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

    force = bool(os.environ.get("LLM_SUMMARY_FORCE"))

    def _entry_is_complete(entry: Dict) -> bool:
        return bool(entry.get("summary_zh")) and bool(entry.get("summary_en"))

    def _already_done(p: Dict) -> bool:
        if force:
            return False
        cached = cache.get(p.get("id"))
        if cached and _entry_is_complete(cached):
            return True
        # paper 自身已有双语 → 跳过
        return bool(p.get("summary_zh")) and bool(p.get("summary_en"))

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
            for result_k, result in enumerate(results):
                idx_in_batch = _resolve_result_pos(
                    result, result_k, len(results), batch_papers
                )
                if idx_in_batch is None:
                    logger.warning(
                        "summarize batch %d: dropped result (index=%r, title=%r) — "
                        "no confident match to any input paper",
                        batch_num, result.get("index"), (result.get("title") or "")[:60],
                    )
                    continue
                paper_idx = indices[idx_in_batch]
                paper_id = batch_papers[idx_in_batch].get("id", "")
                # 双语字段（兼容旧字段名 summary / insights → 当作 _zh）
                summary_zh = (result.get("summary_zh") or result.get("summary") or "").strip()
                summary_en = (result.get("summary_en") or "").strip()
                ins_zh_raw = result.get("insights_zh") or result.get("insights") or []
                ins_en_raw = result.get("insights_en") or []
                insights_zh = [s.strip() for s in ins_zh_raw if s and s.strip()][:3]
                insights_en = [s.strip() for s in ins_en_raw if s and s.strip()][:3]
                if not summary_zh and not summary_en:
                    continue
                payload = {
                    "summary_zh": summary_zh,
                    "summary_en": summary_en,
                    "insights": insights_zh,        # 兼容旧字段名
                    "insights_en": insights_en,
                }
                cache[paper_id] = payload
                papers[paper_idx]["summary_zh"] = summary_zh
                papers[paper_idx]["summary_en"] = summary_en
                papers[paper_idx]["insights"] = insights_zh
                papers[paper_idx]["insights_en"] = insights_en

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
        entry = cache.get(pid)
        if not entry:
            continue
        if not p.get("summary_zh") and entry.get("summary_zh"):
            p["summary_zh"] = entry["summary_zh"]
        if not p.get("summary_en") and entry.get("summary_en"):
            p["summary_en"] = entry["summary_en"]
        if not p.get("insights") and entry.get("insights"):
            p["insights"] = entry["insights"]
        if not p.get("insights_en") and entry.get("insights_en"):
            p["insights_en"] = entry["insights_en"]
    return papers


def summarize_papers(papers: List[Dict]) -> List[Dict]:
    """Sync wrapper."""
    return asyncio.run(summarize_papers_async(papers))
