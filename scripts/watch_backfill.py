#!/usr/bin/env python3
"""
监控 backfill_llm_classify 进度，用 tqdm 显示实时进度条。
另开一个终端跑，不影响后台 backfill 进程。

用法：
    .venv/bin/python scripts/watch_backfill.py
    .venv/bin/python scripts/watch_backfill.py --total 159883
    .venv/bin/python scripts/watch_backfill.py --interval 2
"""

import argparse
import json
import os
import sys
import time
from tqdm import tqdm

DEFAULT_CACHE_FILE = "output/llm_classify_cache.json"


def read_count(cache_file: str) -> int:
    try:
        with open(cache_file, "r") as f:
            return len(json.load(f))
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=159883, help="目标总数")
    ap.add_argument("--interval", type=float, default=1.0, help="刷新间隔秒数")
    ap.add_argument("--cache", default=DEFAULT_CACHE_FILE,
                    help=f"cache 文件路径，默认 {DEFAULT_CACHE_FILE}")
    args = ap.parse_args()
    cache_file = args.cache

    if not os.path.exists(cache_file):
        print(f"等待 {cache_file} 出现...")
        while not os.path.exists(cache_file):
            time.sleep(args.interval)

    initial = read_count(cache_file)
    pbar = tqdm(
        total=args.total,
        initial=initial,
        unit="paper",
        desc=f"LLM ({os.path.basename(cache_file)})",
        dynamic_ncols=True,
        smoothing=0.3,
    )

    last = initial
    try:
        while True:
            time.sleep(args.interval)
            cur = read_count(cache_file)
            if cur > last:
                pbar.update(cur - last)
                last = cur
            if cur >= args.total:
                break
    except KeyboardInterrupt:
        pass
    finally:
        pbar.close()
        print(f"\n当前 cache 条目数：{last:,} / {args.total:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
