#!/usr/bin/env bash
# 给 Colab A100 上的 SAM 3D 打一个包（notebooks/sam3d_colab.ipynb 读它）。
# 用法：bash scripts/pack_sam3d_colab.sh <scene_id> [清单文件名，默认 inventory_v2.json] [最多几个物体，默认 40]
#   挑最长边 < 0.5 m、有掩码的物体，按掩码像素数从大到小取前 N 个；点图用对齐过的 MoGe-2 深度（hd/depth_moge/）。
#   没有这份清单的物体掩码就先跑 masks_for_items.sh。
# 输出 gen/colab/<scene>_<清单>_<时间>.tar.gz：里面是 job/（inputs.json、整帧 RGBA、掩码、点图）和 sam3d_job.py。
#   把它上传到 Google Drive 的 MyDrive/smallobj_colab/，在 Colab 里跑完会在同一个文件夹写回 *_out.tar.gz。
set -euo pipefail
source "$(dirname "$0")/env.sh"
SID="$1"; INV="${2:-inventory_v2.json}"; N="${3:-40}"
P="$PROJ/perception/$SID"
MDIR="$P/item_masks"; [ "$INV" != inventory.json ] && MDIR="${MDIR}_${INV%.json}"
[ -f "$MDIR/index.json" ] || bash "$PROJ/scripts/masks_for_items.sh" "$SID" "$INV"
JOB=$("$PY" - "$SID" "$INV" "$N" <<'PYEOF'
import json, sys
from pathlib import Path
from smallobj import gen3d, inventory
sid, inv, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
P = gen3d.PROJ / "perception" / sid
masks = gen3d._load_masks(P, inv)
best = {iid: max((m.get("mask_px", 0) for m in ms if m.get("status") == "ok"), default=0) for iid, ms in masks.items()}
small = [it["item_id"] for it in inventory.load(P / inv) if max(it["size"]) < 0.5 and best.get(it["item_id"], 0) >= gen3d.MIN_MASK_PX]
pick = sorted(small, key=lambda i: -best[i])[:n]
print(gen3d.prepare_sam3d_job(sid, pick, inventory=inv, depth_name="depth_moge"))
PYEOF
)
STAMP=$(basename "$JOB")
OUT="$PROJ/gen/colab/${SID}_${INV%.json}_${STAMP}.tar.gz"
mkdir -p "$PROJ/gen/colab"
STAGE=$(mktemp -d)
cp -r "$JOB" "$STAGE/job"
cp "$PROJ/scripts/gen_backends/sam3d_job.py" "$STAGE/"
printf '{"scene": "%s", "inventory": "%s", "job_dir": "%s"}\n' "$SID" "$INV" "${JOB#$PROJ/}" > "$STAGE/pack.json"
tar -czf "$OUT" -C "$STAGE" job sam3d_job.py pack.json
rm -rf "$STAGE"
echo ">> $(python3 -c "import json;print(len(json.load(open('$JOB/inputs.json'))))") 个物体 → $OUT（$(du -h "$OUT" | cut -f1)）"
