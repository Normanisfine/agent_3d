#!/usr/bin/env bash
# 第 1 步：装 AHa-3D 第 1 级（Static）：Pi3X、SAM 3、Open3D 三个独立环境。
# 免费；要下载约 10 GB 的 pip 包（两份 torch 2.7.1+cu128），大约 20–30 分钟。
# 全部装在 video2sim-align/ 里面，不碰 conda base 和 env_isaaclab。
set -euo pipefail
source "$(dirname "$0")/env.sh"

if [[ ! -x "$PY311" ]]; then
  echo ">> 用 miniconda 建 Python 3.11：$V2S_ROOT/.runtime/py311"
  ~/miniconda3/bin/conda create -y -p "$V2S_ROOT/.runtime/py311" python=3.11
fi
"$PY311" --version

cd "$AHA"
bash tools/setup.sh --level static --python "$PY311"

echo ">> 检查 GPU 能不能被 torch 看到"
"$PI3X_PY" -c 'import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))'
echo ">> 第 1 步完成"
