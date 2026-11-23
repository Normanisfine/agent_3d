#!/usr/bin/env bash
# 给一次 agent 运行打分。用法：bash scripts/score_run.sh runs/<arm>/<scene>/<seed>
# 组名以 -betty 结尾的运行用的是 perception_betty/ 的感知，对齐也用那一份的相机。
set -euo pipefail
source "$(dirname "$0")/env.sh"
RUN="$(realpath "$1")"; SCENE_ID="$(basename "$(dirname "$RUN")")"
case "$(basename "$(dirname "$(dirname "$RUN")")")" in *-betty) PDIR=perception_betty;; *) PDIR=perception;; esac
cd "$PROJ"
"$PY" - "$RUN" "$SCENE_ID" "$PDIR" <<'PYEOF'
import json, sys
from pathlib import Path
from smallobj import score
run, sid = Path(sys.argv[1]), sys.argv[2]
th = json.loads(Path("configs/thresholds.json").read_text())
res = score.score_run(run, Path("scenes") / sid, Path(sys.argv[3]) / sid / "bundle", th)
for name, r in res.items():
    print(name, "s=%.3f" % r["alignment"]["s"], {b: round(v["recall_D"], 2) for b, v in r["summary"].items()})
PYEOF
