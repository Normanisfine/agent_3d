#!/usr/bin/env bash
# Betty 上批量算感知结果（AHa-3D build_reference，作者默认 255000 像素、32 帧），每个场景一个数组任务。
# 用法（在 Betty 的 ~/smallobj 里）：sbatch --array=1-<场景数> scripts/betty/reference.sbatch
# 场景清单在 ~/smallobj/scenes.txt（push.sh 写的）。结果在 ~/smallobj/perception/<id>/bundle。
#SBATCH --job-name=smallobj-ref
#SBATCH --partition=b200-mig45
#SBATCH --gpus=1
# Betty 的作业过滤器（2026-08 起强制）：GPU 分区只写 GPU 数，CPU 和内存由过滤器按比例补（mig45：每 GPU 6 个 CPU）
#SBATCH --time=00:30:00
#SBATCH --output=logs/ref-%A_%a.out
set -euo pipefail
ROOT="$HOME/smallobj"; AHA="$ROOT/aha-3d"
SID=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$ROOT/scenes.txt")
OUT="$ROOT/perception/$SID/bundle"
SCRATCH="/tmp/$USER/ref-$SID"            # 计算节点本地盘，跑完再拷回 home，省 inode
mkdir -p "$ROOT/perception/$SID" "$SCRATCH" "$ROOT/logs"
export HF_HUB_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True XFORMERS_DISABLED=1
cd "$AHA"
START=$(date +%s)
"$AHA/.runtime/pi3x-inference/venv/bin/python" -m tools.layout_inspection.build_reference \
  --video "$ROOT/scenes/$SID/input.mp4" --upstream "$AHA/external/Pi3" \
  --checkpoint "$AHA/.runtime/pi3x/checkpoint/model.safetensors" \
  --mesh-python "$AHA/.runtime/pi3x-mesh/venv/bin/python" \
  --num-frames 32 --reference-views 5 --pixel-limit 255000 --out "$SCRATCH/bundle"
rm -rf "$OUT"; cp -r "$SCRATCH/bundle" "$OUT"; rm -rf "$SCRATCH"
printf '{"scene": "%s", "pixel_limit": 255000, "seconds": %s, "device": "Betty B200 (%s)", "job": "%s"}\n' \
  "$SID" "$(( $(date +%s) - START ))" "$SLURM_JOB_PARTITION" "$SLURM_JOB_ID" > "$ROOT/perception/$SID/perf.json"
echo ">> $SID 完成"
