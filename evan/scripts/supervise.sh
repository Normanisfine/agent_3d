#!/usr/bin/env bash
# 无人值守的总管：用户定时器 smallobj-supervise.timer 每 10 分钟调一次（开机 1 分钟后第一次），可以重复执行。
# 用法：bash scripts/supervise.sh [任务表]     默认 runs/jobs-current.txt，格式同 resume_runs.sh
# 有线在跑就什么都不做。没有线在跑时：
#   1）跑完的运行里，审查因为 Codex 额度一次都没成功的（runs/.codex_calls.log 里这次运行开始之后：有额度失败、没有一次成功），
#      连同 AHa-3D 的工作目录归档到 runs/_reviewer_unavailable/，回到待跑；同一个运行最多这样归档 2 次，第 3 次留着等人看。
#   2）Codex 账户全都还在额度封禁期（runs/.codex_blocked）就先不启动，下次再看。
#   3）调 resume_runs.sh 把没跑完的排上（Claude 额度不够时，队列自己等到窗口重置再开跑，运行中途撞上限也是等重置后续跑）。
#   4）任务表全部跑完后出一次汇总表（report_rooms.py、test_checks.py），同一张任务表只出一次。
set -uo pipefail
source "$(dirname "$0")/env.sh"
cd "$PROJ" || exit 1
JOBS="$(realpath "${1:-runs/jobs-current.txt}")"; STAMP=$(date +%Y%m%d-%H%M)
say() { echo ">> $(date '+%m-%d %H:%M') [总管] $*"; }
exec 8>"$PROJ/runs/.supervise.lock"; flock -n 8 || exit 0
systemctl --user list-units 'smallobj-lane-*' --state=active --no-legend | grep -q . && exit 0
CALLS="$PROJ/runs/.codex_calls.log"; NOW=$(date +%s); LEFT=0
while read -r LANE ARM SID SEED; do
  RUN="runs/$ARM-claude/$SID/$SEED"
  [ -f "$RUN/run_log.json" ] || { LEFT=$((LEFT + 1)); continue; }
  low="${ARM,,}"; KEY="${SID}_${low}-claude_s$SEED"; T0=$(stat -c %Y "$RUN/prompt.md" 2>/dev/null || echo 0)
  read -r OK LIM < <(awk -v k="$KEY" -v t="$T0" '$2 == k && $1 >= t { ok += ($4 == 0); lim += ($5 == 1) } END { print ok + 0, lim + 0 }' "$CALLS" 2>/dev/null || echo "0 0")
  (( LIM > 0 && OK == 0 )) || continue
  N=$(ls -d "runs/_reviewer_unavailable/$ARM-claude/$SID/$SEED-"* 2>/dev/null | wc -l)
  if (( N >= 2 )); then say "$ARM $SID $SEED 的审查又没跑成，已经归档过 $N 次，这次留着等人看"; continue; fi
  DST="runs/_reviewer_unavailable/$ARM-claude/$SID/$SEED-$STAMP"; mkdir -p "$DST"
  mv "$RUN" "$DST/run"; rmdir "runs/$ARM-claude/$SID" 2>/dev/null
  for sub in scenes deliveries runs; do
    [ -e "$AHA/$sub/$KEY" ] && mv "$AHA/$sub/$KEY" "$DST/aha_$sub"
  done
  echo "$ARM $SID seed $SEED：运行结束了，但 Codex 图像审查因为额度一次都没成功（$LIM 次额度失败），$STAMP 由 supervise.sh 归档，整次重跑；分数留在 run/score_sim3.json，不进主表。" > "$DST/README.txt"
  say "审查没跑成，归档 $RUN → $DST，重跑"; LEFT=$((LEFT + 1))
done < <(grep -v -E '^\s*(#|$)' "$JOBS")
if (( LEFT == 0 )); then
  DONE="$PROJ/runs/.jobs-done-$(md5sum < "$JOBS" | cut -c1-12)"
  [ -f "$DONE" ] && exit 0
  say "任务表全部跑完，出汇总表"
  "$PY" scripts/report_rooms.py > /dev/null && "$PY" scripts/test_checks.py > /dev/null && date > "$DONE" && say "汇总表在 results/test_opus_6rooms/"
  exit 0
fi
FREE=0
for h in $CODEX_HOMES; do
  (( NOW >= $(cat "runs/.codex_blocked/$(echo "$h" | tr '/' '_')" 2>/dev/null || echo 0) )) && FREE=1
done
(( FREE )) || { say "Codex 账户都还在额度封禁期，先不启动（还有 $LEFT 次运行没跑）"; exit 0; }
bash scripts/resume_runs.sh "$JOBS"
