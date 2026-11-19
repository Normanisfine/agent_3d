#!/usr/bin/env bash
# 干净对照清单：SAM 3 文本提示掩码（sam3 venv）→ Pi3X 深度反投影拟框、多帧合并（项目 venv）。
# 用法：bash scripts/run_clean_inventory.sh <scene_id>   输出 perception/<id>/inventory_clean.json
set -euo pipefail
source "$(dirname "$0")/env.sh"
SID="$1"; P="$PROJ/perception/$SID"
rm -rf "$P/sam3_objects"
"$SAM3_PY" "$PROJ/scripts/sam3_objects.py" text "$P/hd" "$PROJ/configs/inventory_labels.json" "$P/sam3_objects" > "$P/sam3_objects.log" 2>&1
"$PY" -c "
from smallobj import clean_inventory, inventory
items = clean_inventory.build('$P/hd', '$P/sam3_objects')
inventory.save(items, '$P/inventory_clean.json')
print('$SID', len(items), '个干净对照清单物体')
"
