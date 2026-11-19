#!/usr/bin/env bash
# 任意视频 → AHa-3D 参考几何（Pi3X + SAM 3 结构掩码 + 地板墙面对齐）。脚本 04 的通用版。
# 用法：bash scripts/run_reference.sh <视频> <输出名前缀> [pixel_limit，默认 150000]
#   12 GB 显卡上 255000 会爆显存（见 README 的 A 段实跑记录）
set -euo pipefail
source "$(dirname "$0")/env.sh"
VIDEO="$(realpath "$1")"; NAME="$2"; PIXEL_LIMIT="${3:-150000}"

FREE_MB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
echo ">> 显存剩余 ${FREE_MB} MiB"
(( FREE_MB >= 9000 )) || { echo "!! 显存不足 9 GB，先等其他 GPU 任务结束" >&2; exit 1; }

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
OUT="$V2S_ROOT/runs/$NAME-reference-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$V2S_ROOT/runs"
cd "$AHA"
"$PI3X_PY" -m tools.layout_inspection.build_reference \
  --video "$VIDEO" \
  --upstream "$PI3X_UPSTREAM" --checkpoint "$PI3X_CHECKPOINT" \
  --mesh-python "$PI3X_MESH_PY" \
  --num-frames 32 --reference-views 5 --pixel-limit "$PIXEL_LIMIT" \
  --out "$OUT"
echo ">> 完成：$OUT"
