#!/usr/bin/env bash
# Boxer 清单（设计 §5 A2/A3/P0）：在高清帧上跑 Boxer，转成 perception/<id>/inventory.json。
# 用法：bash scripts/run_boxer.sh <scene_id>   先要有 perception/<id>/hd/（scripts/extract_hd.sh）
set -euo pipefail
source "$(dirname "$0")/env.sh"
SID="$1"
P="$PROJ/perception/$SID"
LABELS=$(python3 -c "import json;print(','.join(json.load(open('$PROJ/configs/inventory_labels.json'))['labels']))")
PYTHONHASHSEED=0 "$PROJ/.runtime/boxer/venv/bin/python" "$PROJ/scripts/boxer_hd/run_hd.py" "$P/hd" "$P/boxer_raw" "$LABELS" > "$P/boxer_raw.log" 2>&1
"$PY" -c "
from smallobj import hd, inventory
items = inventory.annotate_views(inventory.from_boxer('$P/boxer_raw'), hd.load('$P/hd'))
inventory.save(items, '$P/inventory.json')
print('$SID', len(items), '个清单物体，', sum(it['best_frame'] is not None for it in items), '个在高清帧里看得到')
"
