#!/usr/bin/env bash
# 论文图里的材质版：按顺序对若干次已跑完的运行各做一次材质修订（scripts/showcase_materials.sh），已经有结果的跳过。
# 用法：bash scripts/paper/run_materials.sh runs/A5-claude/42898849/0 [更多运行目录 ...]
set -uo pipefail
source "$(dirname "$0")/../env.sh"
cd "$PROJ" || exit 1
for BASE in "$@"; do
  SID="$(basename "$(dirname "$BASE")")"; ARM="$(basename "$(dirname "$(dirname "$BASE")")")"
  OUT="runs/showcase/${SID}_${ARM%-claude}_materials"
  if [ -f "$OUT/run_log.json" ]; then echo ">> $(date '+%m-%d %H:%M') $OUT 已有，跳过"; continue; fi
  [ -e "$OUT" ] && mv "$OUT" "$OUT.partial-$(date +%H%M)"
  echo ">> $(date '+%m-%d %H:%M') 开始 $OUT"
  bash scripts/showcase_materials.sh "$BASE"
  echo ">> $(date '+%m-%d %H:%M') 结束 $OUT（$( [ -f "$OUT/scene.blend" ] && echo 有 scene.blend || echo 没有 scene.blend)）"
done
