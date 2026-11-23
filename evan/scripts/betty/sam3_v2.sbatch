#!/usr/bin/env bash
# Betty 上跑清单 v2 最慢的一步：SAM 3 整帧 + 3×3 放大窗口（scripts/sam3_objects.py text ... --tiles 3），每个场景一个数组任务。
# 用法（在 Betty 的 ~/smallobj 里）：sbatch --array=1-<场景数> scripts/betty/sam3_v2.sbatch
# 场景清单在 ~/smallobj/scenes_v2.txt。输入是笔记本推上来的 perception/<id>/hd/{frames,cameras.json} 和 labels_v2.json（都来自输入视频，不含真值）。
# 结果在 ~/smallobj/perception/<id>/sam3_objects_v2/；拉回笔记本的 perception/<id>/ 后，scripts/build_inventory_v2.sh 会跳过这一步，接着做 MoGe 深度和拟框。
# 分区很挤时可以再投一份到别的分区：sbatch --partition=b200-mig45 --qos=mig --array=...（mig 分区要 mig 这个 QOS）。
# sam3_objects.py 按 <仓库>/third_party/aha-3d 找权重，Betty 上要有 ~/smallobj/third_party/aha-3d → ../aha-3d 的链接。
#SBATCH --job-name=smallobj-sam3v2
#SBATCH --partition=dgx-b200
#SBATCH --gpus=1
#SBATCH --time=01:00:00
#SBATCH --output=logs/sam3v2-%A_%a.out
set -euo pipefail
ROOT="$HOME/smallobj"; AHA="$ROOT/aha-3d"
SID=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$ROOT/scenes_v2.txt")
P="$ROOT/perception/$SID"; OUT="$P/sam3_objects_v2"
export HF_HUB_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True XFORMERS_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
# 同一批场景可以同时投到几个分区（哪个先有空哪个跑）：已经有结果、或者另一个任务正在做这个场景，就直接退出
[ -f "$OUT/index.json" ] && { echo ">> $SID 已有结果，跳过"; exit 0; }
mkdir "$P/.sam3v2.lock" 2>/dev/null || { echo ">> $SID 另一个任务在做，跳过"; exit 0; }
trap 'rmdir "$P/.sam3v2.lock" 2>/dev/null' EXIT
START=$(date +%s)
rm -rf "$OUT"
"$AHA/.runtime/sam3-segmentation/venv/bin/python" "$ROOT/scripts/sam3_objects.py" text "$P/hd" "$P/labels_v2.json" "$OUT" --tiles 3
echo ">> $SID 完成：$(python3 -c "import json;print(len(json.load(open('$OUT/index.json'))))") 个掩码，$(( $(date +%s) - START )) 秒"
