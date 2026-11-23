#!/usr/bin/env bash
# 材质版跑完之后把它接进论文的图：同机位渲染 → 小图 → 架构图 → 拷进组里的稿子 → 试编译。可以重复跑，缺的房间自动用白膜图占位。
# 用法：bash scripts/paper/finish_materials.sh
set -uo pipefail
source "$(dirname "$0")/../env.sh"
cd "$PROJ" || exit 1
PYTHONPATH=src "$PY" scripts/paper/materials_views.py
"$PY" scripts/paper/assemble_panels.py
"$PY" scripts/paper/pipeline_assets.py
( cd paper/smallobj/pipeline && "$PROJ/.runtime/tex/tectonic" system.tex 2>&1 | grep -E "^error|Writing" )
"$PY" scripts/paper/assemble_panels.py
mkdir -p /tmp/paper-build
( cd third_party/agent_3d/paper/paper_file && "$PROJ/.runtime/tex/tectonic" --outdir /tmp/paper-build main.tex 2>&1 | grep -E "^error|Writing" )
