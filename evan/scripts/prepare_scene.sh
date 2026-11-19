#!/usr/bin/env bash
# 准备一个 CA-1M 场景：下载 → 解包 → 去掉结构件的真值框 → 10 fps 输入视频 → 真值投影检查图。
# 用法：bash scripts/prepare_scene.sh <video_id>
set -euo pipefail
source "$(dirname "$0")/env.sh"
VID="$1"
cd "$PROJ"
"$PY" - "$VID" <<'PYEOF'
import json, sys
from pathlib import Path
from smallobj import ca1m
vid = sys.argv[1]
scene = Path("scenes") / vid
tar = ca1m.download(vid, "val", Path("scenes"))
if not (scene / "frames").exists():
    ca1m.extract(tar, scene)
th = json.loads(Path("configs/thresholds.json").read_text())
recs = ca1m.world_boxes(scene, set(th["structural_categories"]), shell=(th["shell_max_thickness_m"], th["shell_min_length_m"]),
                        shell_keep=set(th.get("shell_keep_categories", [])))
mp4 = ca1m.make_video(scene, fps=10)
for w in (0.25, 0.5, 0.75):
    ca1m.draw_check(scene, scene / "checks" / f"gt_proj_{int(w*100)}.png", where=w)
print(f"{vid}: {len(recs)} 个真值框（已去结构件），视频 {mp4}，检查图在 {scene/'checks'}")
PYEOF
