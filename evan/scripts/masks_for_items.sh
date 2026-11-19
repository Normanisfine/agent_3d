#!/usr/bin/env bash
# 生成前的物体掩码：每个清单物体在最好的 3 帧（投影框大、没被截断、清楚）用框提示 + 文本提示跑 SAM 3。
# 用法：bash scripts/masks_for_items.sh <scene_id> [清单文件名，默认 inventory.json]
# 输出 perception/<id>/item_masks/{<item>/<frame>.png, index.json}（gen3d.request 只读这里）。
set -euo pipefail
source "$(dirname "$0")/env.sh"
SID="$1"; INV="${2:-inventory.json}"; P="$PROJ/perception/$SID"
OUT="$P/item_masks"; [ "$INV" != inventory.json ] && OUT="$P/item_masks_${INV%.json}"
"$PY" -m smallobj.gen3d jobs "$SID" "$P/item_mask_jobs.json" "$INV"
rm -rf "$OUT"
"$SAM3_PY" "$PROJ/scripts/sam3_objects.py" box "$P/hd" "$P/item_mask_jobs.json" "$OUT" > "$OUT.log" 2>&1
"$PY" -c "
import json; d=json.load(open('$OUT/index.json'))
print('$SID', len(d), '条，ok', sum(x['status']=='ok' for x in d))"
