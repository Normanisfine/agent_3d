#!/usr/bin/env bash
# 第 3 步：下载 Pi3X（约 5.4 GB）和 SAM 3（facebook/sam3，要审批，约 3.5 GB）的权重。
# 运行前先登录 Hugging Face（只需一次，token 存在 ~/.cache/huggingface/，不进仓库）：
#   "$AHA/.runtime/pi3x-inference/venv/bin/hf" auth login
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$AHA"

"$PI3X_PY" -c 'from huggingface_hub import get_token; assert get_token(), "还没登录 HF：先运行 $AHA/.runtime/pi3x-inference/venv/bin/hf auth login"'

if [[ ! -f "$PI3X_CHECKPOINT" ]]; then
  echo ">> 下载 Pi3X（固定到 AHa-3D 验证过的版本）"
  mkdir -p "$PI3X_ROOT"
  HF_HUB_CACHE="$PI3X_ROOT/cache/huggingface" "$PI3X_PY" - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="yyfz233/Pi3X",
    revision="bb1deea4d7423de5b30691739cb451a3f57dc1d5",
    allow_patterns=["model.safetensors", "config.json", "README.md"],
    local_dir=os.path.join(os.environ["PI3X_ROOT"], "checkpoint"),
)
PY
fi
ls -lh "$PI3X_CHECKPOINT"

if [[ ! -f "$AHA/.runtime/sam3-segmentation/checkpoints/sam3.pt" ]]; then
  echo ">> 下载并登记 SAM 3"
  "$SAM3_PY" tools/object_pilot/segmentation/prepare_runtime.py --runtime .runtime/sam3-segmentation
fi
ls -lh "$AHA/.runtime/sam3-segmentation/checkpoints/sam3.pt"
echo ">> 第 3 步完成"
