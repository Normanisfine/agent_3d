#!/usr/bin/env bash
# 在 Betty 上一次性装好 AHa-3D 的感知环境（Pi3X、SAM 3、Open3D），装在 $HOME 下。
# 在 Betty 上运行，最好在一个短的 CPU 交互作业里（能上网、不占登录节点）：
#   salloc -p genoa-std-mem --cpus-per-task=8 --mem=32G -t 2:00:00
#   bash ~/smallobj/scripts/betty/setup_betty.sh
# 约 15 GB、7.5 万个文件（home 上限 50 GB、25 万个文件）。权重不在这里下载，用 push.sh 从笔记本拷。
# 状态：10-27 第一次在 Betty 上跑（作业 9584191 因为没有 module 命令失败，已修）。
# 作为 CPU 批处理作业提交（计算节点能上网，10-27 测过）：
#   sbatch -p genoa-std-mem -c 8 -t 02:00:00 -o logs/setup-%j.out --wrap "bash -l ~/smallobj/scripts/betty/setup_betty.sh"
set -euo pipefail
AHA_COMMIT=82f4b11
ROOT="$HOME/smallobj"
mkdir -p "$ROOT" "$ROOT/logs" "$HOME/envs"   # logs/ 要在 sbatch 之前就有（Slurm 先开 --output 文件）
# 批处理作业里是非登录 shell，没有 module 命令：先加载系统环境（10-27 第一次提交时踩到）
type module >/dev/null 2>&1 || source /etc/profile
module load anaconda3
source "$(conda info --base)/etc/profile.d/conda.sh"
[ -x "$HOME/envs/py311/bin/python3.11" ] || conda create -y -p "$HOME/envs/py311" python=3.11
if [ ! -d "$ROOT/aha-3d/.git" ]; then
  git clone https://github.com/KevinXu02/aha-3d.git "$ROOT/aha-3d"
  git -C "$ROOT/aha-3d" checkout "$AHA_COMMIT"
fi
cd "$ROOT/aha-3d"
# AHa-3D 自己的安装在最后的 pip check 会因为 decord 的轮子平台标签报"not supported on this platform"而退出
# （笔记本上同样报，decord 实际能导入；10-27 在 Betty 上踩到）。所以失败了也接着把剩下的步骤补完，
# 是否装好以最后的导入检查为准。整个脚本可以重复跑。
bash tools/setup.sh --level static --python "$HOME/envs/py311/bin/python3.11" \
  || echo ">> AHa-3D 的 setup.sh 返回非零（多半是 decord 的 pip check 误报），继续补完剩下的步骤"
SAM_PY=.runtime/sam3-segmentation/venv/bin/python
"$SAM_PY" -c 'import decord; from sam3.model_builder import build_sam3_image_model; from sam3.model.sam3_image_processor import Sam3Processor; print("SAM3_IMAGE_API_IMPORT_OK")'
MESH=.runtime/pi3x-mesh/venv
[ -x "$MESH/bin/python" ] || "$HOME/envs/py311/bin/python3.11" -m venv "$MESH"
"$MESH/bin/python" -m pip install -q -e ".[reference]"
"$MESH/bin/python" -c 'import open3d, numpy, scipy, cv2; from tools.layout_inspection import reference_views, object_outline, source_fit, agent_review; print("REFERENCE_MESH_IMPORT_OK")'
.runtime/pi3x-inference/venv/bin/python -c 'import torch; print("PI3X_TORCH", torch.__version__)'
rm -rf .runtime/*/pip-cache   # 省 home 空间（上限 50 GB）
echo ">> 环境装好了。检查文件数和空间："
find "$ROOT/aha-3d/.runtime" -type f | wc -l
du -sh "$ROOT/aha-3d/.runtime"
echo ">> 下一步：在笔记本上运行 scripts/betty/push.sh <PennKey> --weights 拷权重，然后在 GPU 上检查："
echo "   srun -p b200-mig45 --gpus=1 -t 5 $ROOT/aha-3d/.runtime/pi3x-inference/venv/bin/python -c 'import torch;print(torch.cuda.get_device_name(0))'"
