#!/usr/bin/env bash
# 在笔记本上运行：把 Betty 上算好的感知结果拉回来，放 perception_betty/<id>/（不覆盖笔记本 10 万像素的结果）。
# 用法：bash scripts/betty/pull.sh <PennKey>
set -euo pipefail
source "$(dirname "$0")/../env.sh"
HOST="$1@login.betty.parcc.upenn.edu"
rsync -av "$HOST:smallobj/perception/" "$PROJ/perception_betty/"
echo ">> 拉回到 $PROJ/perception_betty/。正式实验切换到这份结果前，先用 align.pipeline_to_gt 检查残差。"
