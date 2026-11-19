#!/usr/bin/env bash
# 第 4 步：在 office48 的 10 秒源视频上跑 AHa-3D 的「参考几何」阶段（不调用任何大模型 API，免费）。
# Pi3X 估相机和点云 → SAM 3 分割每一帧 → 定地板和墙 → 网格 → 源相机视角的叠图。
# 用法：bash scripts/04_office48_reference.sh [pixel_limit]
#   默认 pixel_limit=255000；12 GB 显卡爆显存就改小，例如 150000（结果里要记下这个改动）。
set -euo pipefail
source "$(dirname "$0")/env.sh"
PIXEL_LIMIT="${1:-255000}"

VIDEO="$V2S_ROOT/data/office48/source.mp4"
if [[ ! -f "$VIDEO" ]]; then
  mkdir -p "$(dirname "$VIDEO")"
  # 项目主页上托管的源视频（网页压缩版，约 2 MB）
  curl -L -o "$VIDEO" "https://kevinxu02.github.io/real2sim-indoor-site/media/motivation-office48/source.mp4"
fi

# 显卡上可能还有别的任务（比如 IsaacLab 训练），先看剩多少；不够就别跑，也不要杀别人的进程
FREE_MB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
echo ">> 显存剩余 ${FREE_MB} MiB"
if (( FREE_MB < 9000 )); then
  echo "!! 显存不足 9 GB，先等其他 GPU 任务结束再跑" >&2
  exit 1
fi

# 输出目录必须是新的（AHa-3D 拒绝覆盖）
OUT="$V2S_ROOT/runs/office48-reference-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$V2S_ROOT/runs"
cd "$AHA"
"$PI3X_PY" -m tools.layout_inspection.build_reference \
  --video "$VIDEO" \
  --upstream "$PI3X_UPSTREAM" --checkpoint "$PI3X_CHECKPOINT" \
  --mesh-python "$PI3X_MESH_PY" \
  --num-frames 32 --reference-views 5 --pixel-limit "$PIXEL_LIMIT" \
  --out "$OUT" 2>&1 | tee "$V2S_ROOT/runs/$(basename "$OUT").log"

echo ">> 第 4 步完成，结果在 $OUT"
echo "   要看的：source_views/（叠图）、reference_build.json、pi3x/run_report.json"
