#!/usr/bin/env bash
# Betty 上跑 SAM 3D Objects（**未测试**；HF 权限 10-26 已批）。一个作业处理一个 gen3d.prepare_sam3d_job 目录。
# 用法（在 Betty 的 ~/smallobj 里）：sbatch scripts/betty/sam3d.sbatch <场景>/<任务目录名>
#   先把笔记本上的 gen/<场景>/sam3d_jobs/<任务目录名>/ 推到 ~/smallobj/gen/ 下，跑完再拉回。
# 环境：~/smallobj/sam-3d-objects（官方仓库，权重在 checkpoints/hf/）和它的 venv ~/envs/sam3d（官方要 32 GB 显存，用 mig45）。
# 注意：Slurm 在脚本运行前就要打开 --output 的文件，~/smallobj/logs 要事先建好（setup_betty.sh 会建）。
#SBATCH --job-name=smallobj-sam3d
#SBATCH --partition=b200-mig45
#SBATCH --gpus=1
# Betty 的作业过滤器（2026-08 起强制）：GPU 分区只写 GPU 数，CPU 和内存由过滤器按比例补（mig45：每 GPU 6 个 CPU）
#SBATCH --time=01:00:00
#SBATCH --output=logs/sam3d-%j.out
set -euo pipefail
ROOT="$HOME/smallobj"
JOB="$ROOT/gen/$1"
[ -f "$JOB/inputs.json" ] || { echo "!! 没有 $JOB/inputs.json" >&2; exit 1; }
export HF_HUB_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
"$HOME/envs/sam3d/bin/python" "$ROOT/scripts/gen_backends/sam3d_job.py" "$JOB" "$ROOT/sam-3d-objects" --seed 7
echo ">> $1 完成"
