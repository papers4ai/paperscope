#!/bin/bash
# 启动 LLM 全量 backfill 后台进程（防睡眠 + 独立终端）
#
# 用法：
#   bash scripts/start_backfill.sh <LLM_API_KEY>
#
# 可选环境变量（启动前 export 即可覆盖）：
#   LLM_CONCURRENCY=5    并发 batch 数
#   LLM_BATCH_SIZE=20    每 batch 论文数
#   LLM_SAVE_EVERY=1     cache 写盘频率（每 N batch）

set -e

KEY="${1:-$LLM_API_KEY}"
if [ -z "$KEY" ]; then
  echo "ERROR: missing LLM_API_KEY"
  echo "Usage: bash $0 <LLM_API_KEY>"
  exit 1
fi

cd "$(dirname "$0")/.."

export LLM_API_KEY="$KEY"
export LLM_CONCURRENCY="${LLM_CONCURRENCY:-5}"
export LLM_BATCH_SIZE="${LLM_BATCH_SIZE:-20}"
export LLM_SAVE_EVERY="${LLM_SAVE_EVERY:-1}"

LOG=/tmp/backfill_full.log
PIDFILE=/tmp/backfill_full.pid

# 已有进程在跑 → 拒绝重复启动
if [ -f "$PIDFILE" ] && ps -p "$(cat "$PIDFILE")" > /dev/null 2>&1; then
  echo "✗ Already running with PID $(cat "$PIDFILE")"
  echo "  Stop it first:  kill \$(cat $PIDFILE)"
  exit 1
fi

> "$LOG"  # 清空旧日志
nohup caffeinate -is .venv/bin/python -u scripts/backfill_llm_classify.py > "$LOG" 2>&1 &
PID=$!
echo "$PID" > "$PIDFILE"
disown

sleep 3
if ps -p "$PID" > /dev/null; then
  echo "✓ PID $PID running"
  echo "  CONCURRENCY=$LLM_CONCURRENCY  BATCH_SIZE=$LLM_BATCH_SIZE  SAVE_EVERY=$LLM_SAVE_EVERY"
  echo "  Log:       tail -f $LOG"
  echo "  Progress:  .venv/bin/python scripts/watch_backfill.py"
  echo "  Stop:      kill \$(cat $PIDFILE)"
else
  echo "✗ Process died immediately. Last log:"
  tail -20 "$LOG"
  exit 1
fi
