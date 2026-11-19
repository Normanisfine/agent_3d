#!/usr/bin/env bash
# P0 无 agent 流水线：bash scripts/run_p0.sh <scene_id> [P0|P0c] [seed]
# P0 用 Boxer 清单（inventory.json），P0c 用干净对照清单（inventory_clean.json）。跑完自动打分。
set -euo pipefail
source "$(dirname "$0")/env.sh"
SID="$1"; ARM="${2:-P0}"; SEED="${3:-0}"
INV=inventory.json; [ "$ARM" = P0c ] && INV=inventory_clean.json
RUN="$PROJ/runs/$ARM/$SID/$SEED"
[ -e "$RUN/run_log.json" ] && { echo "!! $RUN 已经跑过" >&2; exit 2; }
MDIR="$PROJ/perception/$SID/item_masks"; [ "$INV" != inventory.json ] && MDIR="${MDIR}_${INV%.json}"
[ -f "$MDIR/index.json" ] || bash "$PROJ/scripts/masks_for_items.sh" "$SID" "$INV"
"$PY" -c "
from smallobj import p0
print(p0.run_p0('$SID', '$INV', '$RUN'))"
bash "$PROJ/scripts/score_run.sh" "$RUN"
