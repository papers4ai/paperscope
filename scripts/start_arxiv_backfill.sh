#!/bin/bash
# 后台启动 arxiv 回溯（学科类别 + LLM 过滤）
#
# 用法：
#   bash scripts/start_arxiv_backfill.sh <LLM_API_KEY> <date_from> [date_to] [window_days]
#
# 示例：
#   bash scripts/start_arxiv_backfill.sh $LLM_API_KEY 2023-01-01 2026-12-31 7
#   bash scripts/start_arxiv_backfill.sh $LLM_API_KEY 2026-05-10           # 默认到今天，7 天窗
#
# 监控：
#   tail -f /tmp/arxiv_backfill.log
#   .venv/bin/python scripts/watch_backfill.py    （也能读 llm_classify_cache）

set -e

KEY="${1:-$LLM_API_KEY}"
DATE_FROM="${2:?需要 date_from YYYY-MM-DD}"
DATE_TO="${3:-$(date -u +%Y-%m-%d)}"
WINDOW_DAYS="${4:-7}"

if [ -z "$KEY" ]; then
  echo "ERROR: missing LLM_API_KEY"
  exit 1
fi

cd "$(dirname "$0")/.."

export LLM_API_KEY="$KEY"
export LLM_CONCURRENCY="${LLM_CONCURRENCY:-15}"
export LLM_BATCH_SIZE="${LLM_BATCH_SIZE:-20}"
export LLM_SAVE_EVERY="${LLM_SAVE_EVERY:-1}"
# 独立 cache 文件，避免和 curated backfill 写同一个 cache 冲突
export LLM_CACHE_FILE="${LLM_CACHE_FILE:-output/llm_arxiv_cache.json}"

LOG=/tmp/arxiv_backfill.log
PIDFILE=/tmp/arxiv_backfill.pid

if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE")" > /dev/null 2>&1; then
  echo "✗ Already running with PID $(cat "$PIDFILE")"
  echo "  Stop:  kill \$(cat $PIDFILE)"
  exit 1
fi

> "$LOG"
nohup caffeinate -is .venv/bin/python -u scripts/backfill_arxiv_local.py \
  --date-from "$DATE_FROM" --date-to "$DATE_TO" --window-days "$WINDOW_DAYS" \
  > "$LOG" 2>&1 &
PID=$!
echo "$PID" > "$PIDFILE"
disown

sleep 3
if ps -p "$PID" > /dev/null; then
  echo "✓ PID $PID running"
  echo "  Range:     $DATE_FROM → $DATE_TO ($WINDOW_DAYS d/window)"
  echo "  LLM:       CONCURRENCY=$LLM_CONCURRENCY  BATCH_SIZE=$LLM_BATCH_SIZE"
  echo "  Cache:     $LLM_CACHE_FILE  (独立于 curated)"
  echo "  Log:       tail -f $LOG"
  echo "  Progress:  .venv/bin/python scripts/watch_backfill.py --cache $LLM_CACHE_FILE"
  echo "  Stop:      kill \$(cat $PIDFILE)"
  echo
  echo "  跑完后："
  echo "    .venv/bin/python scripts/upsert_arxiv_local.py output/arxiv_backfill_${DATE_FROM}_${DATE_TO}.json --dry-run"
else
  echo "✗ Process died immediately. Last log:"
  tail -20 "$LOG"
  exit 1
fi
