#!/usr/bin/env bash
# 一个场景的感知结果：AHa-3D 的 build_reference（Pi3X 相机和点云 + SAM 3 结构掩码 + 地面墙面对齐）。
# 用法：bash scripts/run_reference.sh <scene_id> [pixel_limit，默认 150000]
# 笔记本显存不够（桌面占约 2 GB）时自动降到 100000；实际用的像素写进 perception/<id>/perf.json。
set -euo pipefail
source "$(dirname "$0")/env.sh"
VID="$1"; PIX="${2:-150000}"
VIDEO="$PROJ/scenes/$VID/input.mp4"
OUT="$PROJ/perception/$VID/bundle"
[ -f "$VIDEO" ] || { echo "!! 先跑 prepare_scene.sh $VID" >&2; exit 1; }
mkdir -p "$PROJ/perception/$VID"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
run() {
  rm -rf "$OUT"
  ( cd "$AHA" && "$PI3X_PY" -m tools.layout_inspection.build_reference \
      --video "$VIDEO" --upstream "$PI3X_UPSTREAM" --checkpoint "$PI3X_CHECKPOINT" \
      --mesh-python "$MESH_PY" --num-frames 32 --reference-views 5 --pixel-limit "$1" --out "$OUT" )
}
START=$(date +%s)
if ! run "$PIX" > "$PROJ/perception/$VID/reference.log" 2>&1; then
  echo ">> $PIX 像素失败（多半是显存），改用 100000"; PIX=100000
  run "$PIX" >> "$PROJ/perception/$VID/reference.log" 2>&1
fi
END=$(date +%s)
PEAK=$(python3 -c "import json,glob;f=glob.glob('$OUT/**/run_report.json',recursive=True);print(json.load(open(f[0])).get('peak_gpu_allocated_gib','?') if f else '?')")
printf '{"scene": "%s", "pixel_limit": %s, "seconds": %s, "peak_gpu_allocated_gib": "%s", "device": "laptop RTX 5070 Ti 12GB"}\n' "$VID" "$PIX" "$((END-START))" "$PEAK" > "$PROJ/perception/$VID/perf.json"
cat "$PROJ/perception/$VID/perf.json"
