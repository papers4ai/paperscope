#!/bin/bash
# 后台跑论文 AI 中文解读 backfill（cite>=50 OR 近 90 天）
#
# 用法：
#   bash scripts/start_summary.sh <LLM_API_KEYS>
#
# LLM_API_KEYS 是逗号分隔的多 key（推荐 2-3 个，速度线性扩展）：
#   bash scripts/start_summary.sh "key1,key2,key3"
#
# 可选环境变量：
#   LLM_CONCURRENCY=15      每 key 并发数
#   LLM_BATCH_SIZE_SUM=8    每 batch 论文数（summary 比 classify 输出多，batch 小）
#   SUM_MIN_CITE=50         筛选最小引用数
#   SUM_DAYS=90             筛选近 N 天

set -e

KEYS="${1:-${LLM_API_KEYS:-$LLM_API_KEY}}"
if [ -z "$KEYS" ]; then
  echo "ERROR: missing LLM_API_KEYS"
  echo "Usage: bash $0 \"key1,key2,...\""
  exit 1
fi

cd "$(dirname "$0")/.."

export LLM_API_KEYS="$KEYS"
export LLM_CONCURRENCY="${LLM_CONCURRENCY:-15}"
export LLM_BATCH_SIZE_SUM="${LLM_BATCH_SIZE_SUM:-8}"
MIN_CITE="${SUM_MIN_CITE:-50}"
DAYS="${SUM_DAYS:-90}"

LOG=/tmp/summary_backfill.log
PIDFILE=/tmp/summary_backfill.pid

if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE")" > /dev/null 2>&1; then
  echo "✗ Already running with PID $(cat "$PIDFILE")"
  echo "  Stop:  kill \$(cat $PIDFILE)"
  exit 1
fi

> "$LOG"
nohup caffeinate -is .venv/bin/python -u scripts/backfill_summaries.py \
  --min-citations "$MIN_CITE" --days "$DAYS" \
  > "$LOG" 2>&1 &
PID=$!
echo "$PID" > "$PIDFILE"
disown

sleep 3
if ps -p "$PID" > /dev/null; then
  KEY_COUNT=$(echo "$KEYS" | tr ',' '\n' | wc -l | tr -d ' ')
  echo "✓ PID $PID running"
  echo "  Filter:    cite>=$MIN_CITE OR last ${DAYS}d"
  echo "  LLM:       CONCURRENCY=$LLM_CONCURRENCY × $KEY_COUNT keys = total $(( LLM_CONCURRENCY * KEY_COUNT )) concurrent  BATCH=$LLM_BATCH_SIZE_SUM"
  echo "  Log:       tail -f $LOG"
  echo "  Stop:      kill \$(cat $PIDFILE)"
  echo
  echo "  跑完后 sync + commit:"
  echo "    .venv/bin/python scripts/sync_curated.py --local output/papers_curated.json"
  echo "    git add -A && git commit -m 'data: AI 解读 backfill' && git push"
else
  echo "✗ Process died immediately. Last log:"
  tail -20 "$LOG"
  exit 1
fi
