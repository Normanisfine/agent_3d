#!/usr/bin/env bash
# 看门狗：agent 完成的命令执行次数到上限就停掉它（configs/run_caps.json 的 tool_calls）。
# 用法：bash scripts/watch_tool_cap.sh <agent 进程号> <events.jsonl> <上限> <标记文件> [检查间隔秒，默认 10] [计数用的正则]
# 默认数 Codex 的完成命令；Claude 驱动传 '"type":"tool_use"'。
# 停掉时先写标记文件，run_agent.sh 据此把状态记为 tool_cap。
PID="$1"; EVENTS="$2"; CAP="$3"; MARK="$4"; EVERY="${5:-10}"
PAT="${6:-\"type\":\"item.completed\",\"item\":{\"id\":\"[^\"]*\",\"type\":\"command_execution\"}"
while kill -0 "$PID" 2>/dev/null; do
  N=$(grep -o "$PAT" "$EVENTS" 2>/dev/null | wc -l)
  if (( ${N:-0} >= CAP )); then
    echo "$N" > "$MARK"
    kill "$PID" 2>/dev/null
    exit 0
  fi
  sleep "$EVERY"
done
