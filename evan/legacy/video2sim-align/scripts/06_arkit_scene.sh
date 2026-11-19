#!/usr/bin/env bash
# 第 6 步：一个 ARKitScenes 场景从头走到打分（手册阶段一到三 + ICP + 离线对齐测试）。
# 用法：bash scripts/06_arkit_scene.sh <video_id> [pixel_limit，默认 100000]
#   场景要在 BVB 的 150 个 ARKitScenes 场景里（全是 Validation）。每个场景下载约 1.2 GB。
#   已有的下载和预处理会跳过；参考几何、分割、打分每次都写新目录。
set -euo pipefail
source "$(dirname "$0")/env.sh"
VID="$1"; PIXEL_LIMIT="${2:-100000}"
RAW="$V2S_ROOT/data/arkitscenes/raw/Validation/$VID"
SCENE="$V2S_ROOT/data/arkitscenes/scenes/$VID"
STAMP="$(date +%Y%m%d-%H%M%S)"
PERC="$V2S_ROOT/runs/arkit-$VID-perception-$STAMP"
LOG="$V2S_ROOT/runs/logs/arkit-$VID-$STAMP"
mkdir -p "$LOG"
export PYTHONPATH="$V2S_ROOT"

echo ">> 1/7 下载（标注、轨迹、vga 帧、LiDAR 深度）"
mkdir -p "$RAW"; cd "$RAW"
B="https://docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1/raw/Validation/$VID"
[ -f "$V2S_ROOT/data/arkitscenes/metadata.csv" ] || curl -sSf -o "$V2S_ROOT/data/arkitscenes/metadata.csv" \
  https://docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1/raw/metadata.csv
for f in "${VID}_3dod_annotation.json" lowres_wide.traj vga_wide_intrinsics.zip lowres_wide_intrinsics.zip lowres_depth.zip vga_wide.zip; do
  d="${f%.zip}"
  if [[ "$f" == *.zip && -d "$d" ]] || [[ "$f" != *.zip && -f "$f" ]]; then continue; fi
  curl -sSf -C - -o "$f.part" "$B/$f" && mv "$f.part" "$f"
  if [[ "$f" == *.zip ]]; then unzip -q "$f" -d . && rm -f "$f"; fi
done
cd "$V2S_ROOT"

echo ">> 2/7 预处理（按位姿转正、10 fps 视频、真值框、投影检查图）"
[ -f "$SCENE/video.mp4" ] || "$PI3X_MESH_PY" -m v2s.arkit "$RAW" --metadata data/arkitscenes/metadata.csv --out "$SCENE"

echo ">> 3/7 参考几何（Pi3X + SAM 3 结构，pixel_limit=$PIXEL_LIMIT）"
bash scripts/run_reference.sh "$SCENE/video.mp4" "arkit-$VID" "$PIXEL_LIMIT" > "$LOG/reference.log" 2>&1
REF="$(grep '>> 完成：' "$LOG/reference.log" | tail -1 | sed 's/>> 完成：//')"
[ -f "$REF/reference_build.json" ] || { echo "!! 参考几何失败，见 $LOG/reference.log" >&2; exit 1; }

echo ">> 4/7 SAM 3 家具分割"
mkdir -p "$PERC"
(cd "$AHA" && "$SAM3_PY" "$V2S_ROOT/perception/sam3_furniture.py" --bundle "$REF/pi3x" --out "$PERC/sam3" \
  --runtime "$AHA/.runtime/sam3-segmentation") > "$LOG/sam3.log" 2>&1

echo ">> 5/7 提升到 3D，拟合 SAM3+PCA 框"
"$PI3X_MESH_PY" perception/lift.py --reference "$REF" --instances "$PERC/sam3" --out "$PERC/lift" \
  --frame-map "$SCENE/frame_map.json" > "$LOG/lift.log" 2>&1

echo ">> 6/7 打分（SAM3+PCA 和 +ICP）"
"$PI3X_MESH_PY" experiments/run_scene.py --scene "$SCENE" --raw "$RAW" --lift "$PERC/lift" --out "$PERC/eval" | tee "$LOG/eval.log"

echo ">> 7/7 离线对齐测试（LiDAR / Pi3X 观测）"
"$PI3X_MESH_PY" experiments/offline_align.py --scene "$SCENE" --raw "$RAW" --reference "$REF" \
  --cams "$PERC/lift/cams.json" --out "$PERC/offline-align" > "$LOG/offline.log" 2>&1
python3 -c "import json,sys; t=json.load(open(sys.argv[1])); print({k:(t[k]['after'] if isinstance(t[k],dict) and 'after' in t[k] else None) for k in ('lidar','pi3x')})" "$PERC/offline-align/table.json"
echo ">> 完成：参考几何 $REF；感知和打分 $PERC；日志 $LOG"
