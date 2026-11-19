#!/usr/bin/env bash
# 按 Codex 额度排队跑一批 agent，每跑完一个就打分。
# 用法：bash scripts/queue_runs.sh "A1 45261575 0" "A1 47331262 0" ...
# 开跑前估计这次要占 5 小时窗口 EST_PRIMARY 个百分点（默认 60；实测最多 51）。CODEX_HOMES 里的几个账户轮换：
# 挑一个窗口和每周额度都够的跑；都不够就等最早的窗口重置。
# run_agent.sh 的护栏照旧：单次每周额度涨超过 15 个百分点等情况整批停下（退出码 3）；每天 6 次用完（退出码 5）就等到第二天接着跑。
# 所有账户的每周额度都不够（已用 + 10 > 95）就停（退出码 3）。同一条线同一时间只许一个队列（锁文件，拿不到退出码 4）；
# LANE=b 等另开一条线（自己的锁文件），可以和默认那条同时跑，各自排不同的运行。
# SCORE=0 时跑完不打分（评测协议冻结之前给测试集排队用）。
# DRIVER=claude（10-27 起的主实验）：每次开跑前用一次很短的调用读 Claude 订阅额度，每周到 CLAUDE_WEEKLY_MAX（85%）就停，
# 5 小时窗口到 CLAUDE_PRIMARY_MAX 就等它重置（10-28 起默认 100%：用完才等；运行中途撞上限由 run_agent.sh 等重置后续跑）；
# 单次运行本身不设上限。AHa-3D 内部的审查仍走 Codex，照样挑有额度的账户。
set -uo pipefail
source "$(dirname "$0")/env.sh"
EST_PRIMARY="${EST_PRIMARY:-60}"
SCORE="${SCORE:-1}"
DRIVER="${DRIVER:-codex}"
# Claude 驱动时 Codex 只做 AHa-3D 内部的审查，占 5 小时窗口少得多
[ "$DRIVER" = claude ] && EST_PRIMARY="${EST_REVIEW:-10}"
claude_probe() {   # 很短的一次调用，只为读订阅额度（stream 里的 rate_limit_event）
  ( cd "$AHA" && CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_ARTIFACT=1 timeout 120 "$CLAUDE" -p "Reply with OK." \
      --output-format stream-json --verbose --model "$CLAUDE_MODEL" --effort low --no-session-persistence \
      --setting-sources project,local --disable-slash-commands --strict-mcp-config < /dev/null > "$PROJ/runs/.claude_probe${LANE:+-$LANE}.jsonl" 2>/dev/null )
}
LOCK="$PROJ/runs/.queue${LANE:+-$LANE}.lock"
exec 9>"$LOCK"
flock -n 9 || { echo "!! 另一个队列正在跑（$LOCK），退出"; exit 4; }
# 子进程都用 9>&- 关掉锁文件句柄：否则 agent 留下的后台进程（看门狗的 sleep、生成任务）会在队列结束后继续占着锁
for job in "$@"; do
  read -r ARM SID SEED <<< "$job"
  while :; do
    # 几个 Codex 账户里挑一个这次跑得下的（5 小时窗口和每周额度都够）；都不够就等最早的窗口重置；每周都用完就停
    read -r ACC WAIT < <("$PY" -c "
from smallobj import runlog
acc, wait = runlog.pick_account('$CODEX_HOMES'.split(), est_primary=$EST_PRIMARY)
print(acc or '-', wait if wait is not None else -1)")
    if [ "$ACC" != - ]; then export CODEX_HOME="$ACC"; break; fi
    if [ "$WAIT" = -1 ]; then echo "!! $(date +%H:%M) 所有 Codex 账户的每周额度都不够再跑一次，整批停下"; exit 3; fi
    echo ">> $(date +%H:%M) 账户的 5 小时窗口都满了，等 ${WAIT}s 到最早的重置"; sleep "$WAIT"
  done
  while [ "$DRIVER" = claude ]; do
    claude_probe 9>&-
    read -r ACT CW FIVE WEEK < <("$PY" -c "
from smallobj import runlog
w = runlog.claude_windows('$PROJ/runs/.claude_probe${LANE:+-$LANE}.jsonl')
a, s = runlog.claude_gate(w, $CLAUDE_WEEKLY_MAX, $CLAUDE_PRIMARY_MAX)
print(a, s or 0, w.get('five_hour', {}).get('pct', '-'), w.get('seven_day', {}).get('pct', '-'))")
    if [ "$ACT" = run ]; then echo ">> $(date +%H:%M) Claude 额度：5 小时 ${FIVE}%，每周 ${WEEK}%"; break; fi
    if [ "$ACT" = stop ]; then echo "!! $(date +%H:%M) Claude 每周额度 ${WEEK}% 到了 ${CLAUDE_WEEKLY_MAX}%（或读不到额度），整批停下"; exit 3; fi
    echo ">> $(date +%H:%M) Claude 5 小时窗口 ${FIVE}% 到了 ${CLAUDE_PRIMARY_MAX}%，等 ${CW}s 到重置"; sleep "$CW"
  done
  echo ">> $(date +%H:%M) 开跑 $ARM $SID $SEED"
  bash "$PROJ/scripts/run_agent.sh" "$ARM" "$SID" "$SEED" 9>&-; CODE=$?
  while (( CODE == 5 )); do   # 今天的次数满了（只数 Codex）：等到明天 00:05 再跑这一个（DAY_WAIT_S 可覆盖，测试用）
    WAIT="${DAY_WAIT_S:-$(( $(date -d 'tomorrow 00:05' +%s) - $(date +%s) ))}"
    echo ">> $(date +%H:%M) 今天的次数用完了，等 ${WAIT}s 到明天"; sleep "$WAIT"
    bash "$PROJ/scripts/run_agent.sh" "$ARM" "$SID" "$SEED" 9>&-; CODE=$?
  done
  (( CODE == 3 )) && { echo "!! 护栏触发（额度或每日上限），整批停下"; exit 3; }
  RUN="$PROJ/runs/$ARM$( [ "$DRIVER" = claude ] && echo -claude )/$SID/$SEED"
  [ "$SCORE" = 1 ] && [ -f "$RUN/scene.blend" ] && bash "$PROJ/scripts/score_run.sh" "$RUN" 9>&-
done
echo ">> 队列跑完"
