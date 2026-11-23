#!/usr/bin/env bash
# 清单 v2 的掩码（慢的那一步，只占显卡）：开放词表（没有就先跑 propose_labels.sh）+ SAM 3 整帧和 3×3 放大窗口。
# 用法：bash scripts/run_sam3_v2.sh <scene_id> ...   输出 perception/<id>/sam3_objects_v2/（index.json 的 source 记 full 或 tile）
set -euo pipefail
source "$(dirname "$0")/env.sh"
for SID in "$@"; do
  P="$PROJ/perception/$SID"
  [ -f "$P/labels_v2.json" ] || bash "$PROJ/scripts/propose_labels.sh" "$SID"
  [ -f "$P/sam3_objects_v2/index.json" ] && { echo ">> $SID 已有 sam3_objects_v2，跳过"; continue; }
  rm -rf "$P/sam3_objects_v2"
  echo ">> $(date +%H:%M) $SID SAM 3（$(python3 -c "import json;print(len(json.load(open('$P/labels_v2.json'))['labels']))") 类 × 整帧 + 9 个窗口）"
  "$SAM3_PY" "$PROJ/scripts/sam3_objects.py" text "$P/hd" "$P/labels_v2.json" "$P/sam3_objects_v2" --tiles 3 > "$P/sam3_objects_v2.log" 2>&1
  echo ">> $(date +%H:%M) $SID 完成：$(python3 -c "import json;print(len(json.load(open('$P/sam3_objects_v2/index.json'))))") 个掩码"
done
