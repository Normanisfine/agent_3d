#!/usr/bin/env bash
# 清单 v2 的开放词表（借 SceneRig）：让 Claude 看 8 张均匀取的高清帧，列出看到的物体类别，并进固定类别表。
# 用法：bash scripts/propose_labels.sh <scene_id>
# 输出 perception/<id>/labels_v2.json（{labels, proposed, frames, model, usage}）和 labels_v2_raw.json（原始回复）。
# 只给模型输入视频的帧（不碰真值）；只开放 Read 一个工具；不读用户设置、技能和 MCP，同 run_agent.sh 的 Claude 驱动。
set -euo pipefail
source "$(dirname "$0")/env.sh"
SID="$1"; P="$PROJ/perception/$SID"
FRAMES=$("$PY" -c "
import json
fs = [int(f['source_frame']) for f in json.load(open('$P/hd/cameras.json'))['frames']]
pick = [fs[round(i * (len(fs) - 1) / 7)] for i in range(8)]
print(' '.join('$P/hd/frames/%06d.png' % s for s in dict.fromkeys(pick)))")
PROMPT="Read each of these images with the Read tool: $FRAMES
They are frames from one video that walks through a single indoor room.
List every distinct kind of physical object you can see, and be thorough about small items: things on tables,
shelves, counters, sofas, beds, walls and the floor, and inside open containers.
Use short, common, singular nouns that work as open-vocabulary segmentation prompts (for example \"cup\",
\"power outlet\", \"sticky note\"). No brands, colors, materials, counts or positions. Do not list room
structure (wall, floor, ceiling, window, door, stairs).
Reply with only a JSON object: {\"labels\": [\"...\", ...]}"
( cd "$P" && CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_ARTIFACT=1 timeout 900 "$CLAUDE" -p "$PROMPT" \
    --output-format json --model "$CLAUDE_MODEL" --effort low --tools Read --allowedTools Read \
    --setting-sources project,local --disable-slash-commands --strict-mcp-config --no-session-persistence \
    < /dev/null > "$P/labels_v2_raw.json" )
"$PY" - "$P" "$PROJ/configs/inventory_labels.json" "$CLAUDE_MODEL" $FRAMES <<'PYEOF'
import json, sys
from pathlib import Path
from smallobj import labels
P, fixed_path, model, frames = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4:]
raw = json.loads((P / "labels_v2_raw.json").read_text())
proposed = labels.parse(raw.get("result", ""))
fixed = json.loads(Path(fixed_path).read_text())["labels"]
out = {"note": "清单 v2：固定类别表 + Claude 看 8 张高清帧提出的类别（scripts/propose_labels.sh）",
       "labels": labels.merge(fixed, proposed), "proposed": proposed, "frames": [Path(f).name for f in frames],
       "model": model, "usage": raw.get("usage"), "cost_usd_equiv": raw.get("total_cost_usd")}
(P / "labels_v2.json").write_text(json.dumps(out, indent=1) + "\n")
print(P.name, f"提出 {len(proposed)} 类，新增 {len(out['labels']) - len(fixed)} 类：",
      [l for l in out["labels"] if l not in fixed])
PYEOF
