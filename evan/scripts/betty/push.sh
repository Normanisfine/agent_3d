#!/usr/bin/env bash
# 在笔记本上运行：把要处理的场景视频（和可选的权重、脚本）推到 Betty。
# 用法：bash scripts/betty/push.sh <PennKey> [--weights] [scene_id ...]（不给场景就推 splits.json 里全部 20 个开发+测试场景）
# 要先连 Penn VPN 并 kinit <PennKey>@UPENN.EDU。
set -euo pipefail
source "$(dirname "$0")/../env.sh"
USER_PK="$1"; shift
HOST="$USER_PK@login.betty.parcc.upenn.edu"
DEST="smallobj"
WEIGHTS=0; SCENES=()
for a in "$@"; do [ "$a" = --weights ] && WEIGHTS=1 || SCENES+=("$a"); done
if [ ${#SCENES[@]} -eq 0 ]; then
  mapfile -t SCENES < <(python3 -c "import json;d=json.load(open('$PROJ/configs/splits.json'));print('\n'.join(d['dev']+d['test']))")
fi
ssh "$HOST" "mkdir -p $DEST/scenes $DEST/scripts"
rsync -av "$PROJ/scripts/betty/" "$HOST:$DEST/scripts/betty/"
for s in "${SCENES[@]}"; do
  [ -f "$PROJ/scenes/$s/input.mp4" ] || { echo "!! 先在笔记本上跑 prepare_scene.sh $s"; continue; }
  rsync -av --relative "$PROJ/./scenes/$s/input.mp4" "$HOST:$DEST/"
done
if [ "$WEIGHTS" = 1 ]; then
  # 要在 setup_betty.sh 克隆完 aha-3d 之后再推（先建目录会让 git clone 因为目录非空而失败）；rsync 不建多级目录，先 mkdir
  ssh "$HOST" "mkdir -p $DEST/aha-3d/.runtime/pi3x/checkpoint $DEST/aha-3d/.runtime/sam3-segmentation/checkpoints"
  rsync -av "$AHA/.runtime/pi3x/checkpoint/" "$HOST:$DEST/aha-3d/.runtime/pi3x/checkpoint/"
  rsync -av "$AHA/.runtime/sam3-segmentation/checkpoints/" "$HOST:$DEST/aha-3d/.runtime/sam3-segmentation/checkpoints/"
  # SAM 3 的 runtime.json（版本和权重路径的说明，build_reference 会读）：权重是拷过去的，没在 Betty 上跑下载步骤，
  # 所以把笔记本那份的路径换成 Betty 上的再推过去（10-27 第一次跑感知时因为缺这个文件失败）
  REMOTE_HOME=$(ssh "$HOST" 'echo $HOME')
  python3 - "$AHA/.runtime/sam3-segmentation/runtime.json" "$AHA" "$REMOTE_HOME/$DEST/aha-3d" <<'PYEOF' | ssh "$HOST" "cat > $DEST/aha-3d/.runtime/sam3-segmentation/runtime.json"
import json, sys
d = json.load(open(sys.argv[1]))
d["files"] = {k: v.replace(sys.argv[2], sys.argv[3]) for k, v in d["files"].items()}
d["copied_from_laptop"] = "checkpoints copied by scripts/betty/push.sh; same revision as the laptop download"
print(json.dumps(d, indent=2))
PYEOF
fi
printf '%s\n' "${SCENES[@]}" | ssh "$HOST" "cat > $DEST/scenes.txt"
echo ">> 推完了。到 Betty 上：cd ~/smallobj && sbatch --array=1-$(printf '%s\n' "${SCENES[@]}" | wc -l) scripts/betty/reference.sbatch"
