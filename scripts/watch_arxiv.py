#!/usr/bin/env python3
"""用 tqdm 实时显示 arxiv backfill 两阶段进度。

用法：
    .venv/bin/python scripts/watch_arxiv.py
"""

import json
import os
import re
import sys
import time

from tqdm import tqdm

LOG = "/tmp/arxiv_backfill.log"
CACHE = "output/llm_arxiv_cache.json"


def parse_log() -> dict:
    """从日志解析当前阶段 + 进度。"""
    if not os.path.exists(LOG):
        return {"stage": "starting", "windows_done": 0, "windows_total": 0, "pool": 0}

    text = open(LOG, errors="ignore").read()

    m_total = re.search(r"\[arxiv\] (\d+) windows", text)
    windows_total = int(m_total.group(1)) if m_total else 0

    # tqdm 行匹配："arxiv fetch:  X%|...| done/total"
    tqdm_matches = re.findall(r"arxiv fetch:\s*\d+%[^|]*\|[^|]*\|\s*(\d+)/(\d+)", text)
    if tqdm_matches:
        windows_done = int(tqdm_matches[-1][0])
    else:
        old = re.findall(r"\[arxiv\] \[(\d+)/\d+\]", text)
        windows_done = int(old[-1]) if old else 0

    # 候选池
    pool = 0
    for m in re.finditer(r"pool:\s*([\d,]+)", text):
        pool = max(pool, int(m.group(1).replace(",", "")))
    m_pool2 = re.search(r"candidate pool:\s*([\d,]+)", text)
    if m_pool2:
        pool = max(pool, int(m_pool2.group(1).replace(",", "")))

    if "Wrote" in text and "papers →" in text:
        stage = "DONE"
    elif "LLM classifying" in text:
        stage = "2-LLM"
    elif windows_total > 0:
        stage = "1-fetch"
    else:
        stage = "starting"

    return {
        "stage": stage,
        "windows_done": windows_done,
        "windows_total": windows_total,
        "pool": pool,
    }


def cache_count() -> int:
    try:
        return len(json.load(open(CACHE)))
    except Exception:
        return 0


def main() -> None:
    if not os.path.exists(LOG):
        print(f"等待 {LOG} 出现...")
        while not os.path.exists(LOG):
            time.sleep(1)

    # 等待第一行解析出 windows_total
    info = parse_log()
    while info["windows_total"] == 0 and info["stage"] != "DONE":
        time.sleep(1)
        info = parse_log()

    pbar1 = tqdm(
        total=info["windows_total"],
        desc="阶段1 拉候选",
        unit="win",
        position=0,
        leave=True,
        dynamic_ncols=True,
    )
    # 阶段 2 totals 占位用一个估值，候选池跑完会自动更新成实际值
    pbar2 = tqdm(
        total=1,
        desc="阶段2 LLM  ",
        unit="paper",
        position=1,
        leave=True,
        dynamic_ncols=True,
    )

    try:
        while True:
            info = parse_log()
            cached = cache_count()

            # 阶段 1 更新
            if info["windows_done"] > pbar1.n:
                pbar1.update(info["windows_done"] - pbar1.n)
            pbar1.set_postfix_str(f"候选池: {info['pool']:,}")

            # 阶段 2 更新（动态 total）
            new_total = max(info["pool"], 1)
            if new_total != pbar2.total:
                pbar2.total = new_total
                pbar2.refresh()
            if cached > pbar2.n:
                pbar2.update(cached - pbar2.n)

            if info["stage"] == "DONE":
                pbar1.set_postfix_str(f"完成，候选池 {info['pool']:,}")
                pbar2.set_postfix_str("✓ 完成")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        pbar1.close()
        pbar2.close()


if __name__ == "__main__":
    main()
