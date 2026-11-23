#!/usr/bin/env bash
# 给场景生成清单 v2，只生成、不打分、不读真值：开放词表 + SAM 3 整帧和放大窗口 → MoGe-2 深度 → 拟框、同尺寸、贴支撑面。
# 用法：bash scripts/build_inventory_v2.sh <scene_id> ...   输出 perception/<id>/inventory_v2.json（已有就跳过）
# 开发集的消融和打分在 scripts/inventory_v2_dev.py。测试集只用这个脚本；打分等去重规则在开发集上定稿之后再做。
set -euo pipefail
source "$(dirname "$0")/env.sh"
for SID in "$@"; do
  P="$PROJ/perception/$SID"
  [ -f "$P/inventory_v2.json" ] && { echo ">> $SID 已有 inventory_v2.json，跳过"; continue; }
  bash "$PROJ/scripts/run_sam3_v2.sh" "$SID"
  [ -f "$P/hd/depth_moge/align.json" ] || "$PROJ/.runtime/moge/bin/python" "$PROJ/scripts/run_moge.py" "$SID"
  "$PY" -c "
from pathlib import Path
from smallobj import clean_inventory, inventory
items = clean_inventory.build_v2('$SID', root=Path('$PROJ'))
inventory.save(items, Path('$PROJ') / 'perception' / '$SID' / 'inventory_v2.json')
print('>> $SID 清单 v2：', len(items), '条')"
done
echo ">> 清单 v2 生成完"
