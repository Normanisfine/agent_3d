#!/usr/bin/env bash
# 把一张任务表里还没跑完的 agent 运行接着排上，可以重复执行（开机后由用户服务 smallobj-resume 自动调一次，也可以手动调）。
# 用法：bash scripts/resume_runs.sh <任务表>     任务表每行：<线 a|b|d|…> <组> <场景> <种子>，# 开头的行不算
# 做的事：1）已经有线在跑就什么都不做；2）没写出 run_log.json 的残留运行（关机、重启打断的）连同 AHa-3D 的工作目录
#   归档到 runs/_interrupted/，整次重跑；3）A5 要用的清单 v2 和逐项清单缺了就先补（占显卡，所以排在 agent 之前）；
#   4）每条线一个后台服务（systemd-run --user，aa-exec -p vscode 让进程隔离能用），只排还没有 run_log.json 的运行。
# 已经有 run_log.json 的运行不管状态如何都不重跑（rate_limited、infra 之类要人看过再定）。
set -uo pipefail
source "$(dirname "$0")/env.sh"
cd "$PROJ" || exit 1
JOBS="$(realpath "$1")"; STAMP=$(date +%Y%m%d-%H%M)
say() { echo ">> $(date '+%m-%d %H:%M') $*"; }
if systemctl --user list-units 'smallobj-lane-*' --state=active --no-legend | grep -q .; then say "已经有线在跑，不动"; exit 0; fi
mapfile -t LINES < <(grep -v -E '^\s*(#|$)' "$JOBS")
declare -A TODO; NEED_V2=()
for line in "${LINES[@]}"; do
  read -r LANE ARM SID SEED <<< "$line"
  RUN="runs/$ARM-claude/$SID/$SEED"
  [ -f "$RUN/run_log.json" ] && continue
  if [ -d "$RUN" ]; then
    low="${ARM,,}"; DST="runs/_interrupted/$ARM-claude/$SID/$SEED-interrupted-$STAMP"; mkdir -p "$DST"
    mv "$RUN" "$DST/run"; rmdir "runs/$ARM-claude/$SID" 2>/dev/null
    for sub in scenes deliveries runs; do
      [ -e "$AHA/$sub/${SID}_${low}-claude_s$SEED" ] && mv "$AHA/$sub/${SID}_${low}-claude_s$SEED" "$DST/aha_$sub"
    done
    echo "$ARM $SID seed $SEED：没写出 run_log.json 的残留（关机或重启打断），$STAMP 由 resume_runs.sh 归档，整次重跑，不打分。" > "$DST/README.txt"
    say "归档残留 $RUN → $DST"
  fi
  TODO[$LANE]+="\"$ARM $SID $SEED\" "
  [ "$ARM" = A5 ] && NEED_V2+=("$SID")
done
[ ${#TODO[@]} -eq 0 ] && { say "任务表里的运行都跑完了"; exit 0; }
if [ ${#NEED_V2[@]} -gt 0 ]; then
  MISSING=(); for s in "${NEED_V2[@]}"; do [ -f "perception/$s/inventory_v2.json" ] || MISSING+=("$s"); done
  if [ ${#MISSING[@]} -gt 0 ]; then say "先补清单 v2：${MISSING[*]}"; bash scripts/build_inventory_v2.sh "${MISSING[@]}" || { say "!! 清单 v2 没补出来，不启动"; exit 1; }; fi
  LISTS=(); for s in "${NEED_V2[@]}"; do [ -f "perception/$s/inventory_v2_list.json" ] && [ -d "perception/$s/inventory_v2_crops" ] || LISTS+=("$s"); done
  [ ${#LISTS[@]} -gt 0 ] && { "$PY" scripts/build_checklist.py "${LISTS[@]}" || { say "!! 逐项清单没建出来，不启动"; exit 1; }; }
fi
for LANE in "${!TODO[@]}"; do
  LOG="$PROJ/runs/queue-$LANE-$STAMP.log"; ENV=(--setenv=DRIVER=claude); [ "$LANE" = a ] || ENV+=(--setenv=LANE="$LANE")
  eval "systemd-run --user --unit=smallobj-lane-$LANE --collect --quiet -p WorkingDirectory=\"$PROJ\" -p StandardOutput=append:\"$LOG\" -p StandardError=append:\"$LOG\" ${ENV[*]} aa-exec -p vscode -- bash scripts/queue_runs.sh ${TODO[$LANE]}" \
    && say "线 $LANE：${TODO[$LANE]}→ $(basename "$LOG")" || say "!! 线 $LANE 没启动"
done
