#!/usr/bin/env bash
# AHa-3D 内部审查调的 codex（run_agent.sh 把 .runtime/bin/codex 指到这里，AHa-3D 从 PATH 找到它）。
# 1. exec 调用固定模型和推理强度（CODEX_MODEL / CODEX_EFFORT，和 Codex agent 一致），不随账户的 config.toml 变：
#    ~/.codex 的 config 是 ultra、~/.codex-b 没设，10-27 之前的审查因此随挑到的账户不同。
# 2. 某个账户报额度用完（usage limit）就记下到什么时候能再用，换 CODEX_HOMES 里下一个账户重试（prompt 原样再送）；
#    都用完就照 codex 的样子失败。记录在 CODEX_BLOCK_DIR（默认 runs/.codex_blocked/），文件内容是能再用的时间戳。
# 其他子命令原样转给真的 codex。
set -uo pipefail
CODEX_REAL="${CODEX_REAL:-${CODEX:-}}"
if [ -z "$CODEX_REAL" ] || [ -z "${CODEX_MODEL:-}" ]; then source "$(dirname "$(readlink -f "$0")")/env.sh"; CODEX_REAL="${CODEX_REAL:-$CODEX}"; fi
[ "$(readlink -f "$CODEX_REAL")" = "$(readlink -f "$0")" ] && { echo "codex_review.sh: CODEX_REAL 指向自己" >&2; exit 2; }
[ "${1:-}" = exec ] || exec "$CODEX_REAL" "$@"
shift
BLOCK="${CODEX_BLOCK_DIR:-$(dirname "$(readlink -f "$0")")/../runs/.codex_blocked}"
mkdir -p "$BLOCK"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
if [ -t 0 ]; then : > "$tmp/stdin"; else cat > "$tmp/stdin"; fi
# 每次审查调用记一行到 CODEX_CALL_LOG（默认 runs/.codex_calls.log）：时间戳、哪次运行的场景、账户、退出码、是不是额度用完。
# supervise.sh 靠它判断一次运行有没有真的拿到过审查意见。
CALLS="${CODEX_CALL_LOG:-$(dirname "$BLOCK")/.codex_calls.log}"
SCENE_KEY="$( { printf '%s\n' "$*"; cat "$tmp/stdin"; } | grep -oE '[0-9]{8}_[a-z0-9]+-claude(-betty)?_s[0-9]+' | head -1)"
logcall() { echo "$(date +%s) ${SCENE_KEY:--} $1 $2 $3" >> "$CALLS" 2>/dev/null || true; }
order=("${CODEX_HOME:-$HOME/.codex}")
for h in ${CODEX_HOMES:-}; do [[ " ${order[*]} " == *" $h "* ]] || order+=("$h"); done
code=1; tried=0
for h in "${order[@]}"; do
  key="$(echo "$h" | tr '/' '_')"
  now="$(date +%s)"
  (( now < $(cat "$BLOCK/$key" 2>/dev/null || echo 0) )) && continue
  tried=1
  CODEX_HOME="$h" "$CODEX_REAL" exec -m "$CODEX_MODEL" -c "model_reasoning_effort=$CODEX_EFFORT" "$@" \
    < "$tmp/stdin" > "$tmp/out" 2> "$tmp/err"; code=$?
  cat "$tmp/out"; cat "$tmp/err" >&2
  if (( code != 0 )) && grep -qi "usage limit" "$tmp/out" "$tmp/err"; then
    at="$(grep -ohiE "try again at [^.]*" "$tmp/out" "$tmp/err" | head -1 | sed -E 's/^try again at //I; s/(st|nd|rd|th),/,/')"
    until="$(date -d "$at" +%s 2>/dev/null || echo $(( now + 3600 )))"
    (( until <= now )) && until=$(( until + 86400 ))   # 只给了钟点、已经过了：是明天的
    echo "$until" > "$BLOCK/$key"
    echo "!! codex_review: $h 额度用完，到 $(date -d "@$until" '+%m-%d %H:%M') 前换别的账户" >&2
    logcall "$h" "$code" 1
    continue
  fi
  logcall "$h" "$code" 0
  exit "$code"
done
(( tried )) || { echo "ERROR: every Codex account in CODEX_HOMES hit its usage limit (see $BLOCK)" >&2; logcall - 1 1; }
exit "$code"
