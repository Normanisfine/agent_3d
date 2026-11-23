#!/usr/bin/env bash
# 展示用的材质版（10-28 Yifan 要，给 TA 汇报用，不进实验结果）：拿一次已跑完运行的最终 scene.blend，
# 让 AHa-3D 按原版的 appearance=materials 做一次只改材质和灯光的修订（几何不动），出带材质和光影的渲染图。
# 驱动和隔离方式同 run_agent.sh 的 Claude 驱动（Opus 5.5、medium、不读用户设置、PID 命名空间）。
# 用法：bash scripts/showcase_materials.sh <已跑完的运行目录，如 runs/A1-claude/47331262/0>
# 输出：runs/showcase/<场景>_<组>_materials/{prompt.md, request.json, events.jsonl, scene.blend, stills/, compare/, SUMMARY.md, run_log.json}
set -uo pipefail
source "$(dirname "$0")/env.sh"
BASE="$(cd "$1" && pwd -P)"
SID="$(basename "$(dirname "$BASE")")"; ARM="$(basename "$(dirname "$(dirname "$BASE")")")"
[ -f "$BASE/scene.blend" ] || { echo "!! $BASE 没有 scene.blend" >&2; exit 2; }
NAME="${SID}_${ARM%-claude}_materials"
SCENE_RUN="${SID}_showcase_mat_${ARM%-claude}"; SCENE_RUN="${SCENE_RUN,,}"
RUN="$PROJ/runs/showcase/$NAME"
[ -e "$RUN" ] && { echo "!! $RUN 已经有了，不覆盖" >&2; exit 2; }
[ -e "$AHA/scenes/$SCENE_RUN" ] && { echo "!! $AHA/scenes/$SCENE_RUN 已经有了，不覆盖" >&2; exit 2; }
REF="$(cd "$PROJ/perception/$SID/bundle" && pwd -P)"
# 底子运行的白膜图目录名不统一（stills/、final_stills/、final_views/、renders/stills_v014/），往下找三层，取版本最新的；
# 有的运行没存白膜图（11-22），那就不给，让 agent 自己从源视频机位里挑
STILLS="$(find "$BASE" -maxdepth 3 -type d \( -name 'stills' -o -name 'final_stills' -o -name 'final_views' -o -name 'stills_v*' \) 2>/dev/null | sort -V | tail -1)"
if [ -n "$STILLS" ]; then
  STILLS_NOTE="and its whitebox stills in \`$STILLS/\`"
  STILLS_RULE="matching the
  base run's whitebox stills where possible; at least 1600 px wide. For every
  whitebox render in \`$STILLS/\` that was made from a source-video camera (its file
  name carries the frame number), also render the material scene from that same
  camera at the same resolution, keeping the frame number in the file name."
else
  STILLS_NOTE="(the base run saved no whitebox stills)"
  STILLS_RULE="at least 1600 px wide. Also render the material scene from at least
  six source-video cameras spread across the video (\`$REF/source_views/\`), keeping
  the frame number in each file name."
fi
mkdir -p "$RUN" "$AHA/scenes/$SCENE_RUN/references"
cp "$PROJ/scenes/$SID/input.mp4" "$AHA/scenes/$SCENE_RUN/references/input.mp4"
cat > "$RUN/request.json" <<EOF
{
  "schema_version": 1,
  "scene": "$SCENE_RUN",
  "inputs": {"video": "scenes/$SCENE_RUN/references/input.mp4"},
  "preset": "materials",
  "appearance": "materials",
  "delivery": "stills",
  "fidelity": {"mode": "approximate"},
  "interactive_demo": false,
  "camera": "inspection",
  "people": "none",
  "cabinets": "none",
  "objects": "none",
  "reuse": "reuse_allowed",
  "variants": {"models": false, "materials": false},
  "details": {"appearance": "Furnished materials approximating the visible colors and finishes in the source video. Geometry is final: it comes from the reviewed base scene and is not edited."}
}
EOF
cat > "$RUN/prompt.md" <<EOF
You are running AHa-3D (this repository) unattended. No human is available during
the run: never wait for answers. When the workflow says to ask the user, take the
answer from the prefilled request below, record the decision, and continue.

## Task

Your working directory is the AHa-3D repository root, \`$AHA\`. Relative paths in
its docs and in this prompt are relative to that root.

This is a narrow **material revision** of an existing room, for presentation.
The base scene \`$BASE/scene.blend\` was built and reviewed in an earlier task
from the video \`$AHA/scenes/$SCENE_RUN/references/input.mp4\`; its notes are in
\`$BASE/SUMMARY.md\` $STILLS_NOTE. The base scene is
read-only: copy it into \`scenes/$SCENE_RUN/\` and work on the copy.

Give the copy furnished materials and lighting that approximate what the source
video shows, then render presentation stills.

Scope is already decided and prefilled in \`$RUN/request.json\`. Run
\`bash tools/indoor intake --request $RUN/request.json --out $RUN/intake\` to record it.

- **Geometry is final.** Do not move, add, delete, rescale or reshape any object.
  Only assign materials, and add lights and world lighting. Keep object names,
  semantic roots and \`instance_id\`s.
- **Materials.** Search the asset library (\`assets/INDEX.md\`) for registered
  materials first; author Principled BSDF materials where nothing fits. Approximate
  colors and finishes seen in the video: wall paint, floor, wooden furniture,
  leather and fabric, metal, glass, screens, plants, pictures and the small objects.
  Close texture matching is not required. Every visible object should get a
  plausible material; small objects should not stay grey.
- **Lighting.** Daylight through the windows plus soft interior fill, so the room
  reads like the video; avoid blown-out or very dark renders.
- Read \`AGENTS.md\`, \`docs/INDEX.md\`, \`docs/SCENE_REQUESTS.md\`,
  \`docs/SCENE_VARIANTS.md\` and \`.agents/skills/blender-roomkit/SKILL.md\` as needed.
- The reference geometry and source cameras are already built; reuse them and do
  not rerun Pi3X inference: \`$REF\` (contains \`pi3x/\`, \`masks/\`, \`alignment/\`,
  \`mesh/\`, \`source_views/\`, \`reference_build.json\`).

## Deliverables (in \`$RUN\`)

- \`scene.blend\`: the material scene (a copy of your final \`.blend\`).
- \`stills/\`: overview, front, side and two or three interior views, $STILLS_RULE
- \`compare/\`: at least 6 side-by-side images, source video frame on the left and
  the material render from the matched source camera on the right, for frames
  spread across the video.
- \`SUMMARY.md\`: what you changed, the material choices, the render settings, which
  reviews ran and their verdicts, problems and how you handled them.

## Environment (already exported in your shell)

\`KIMODO_ENV\`, \`PI3X_PY\`, \`PI3X_MESH_PY\`, \`PI3X_UPSTREAM\`, \`PI3X_CHECKPOINT\`,
\`BLENDER_BIN\` (Blender 5.2.1, also on PATH as \`blender\`), and \`codex\` on PATH for
\`acceptance review-images\` and \`tools/review_images.py\`.

## Rules

- Work only inside this repository and \`$RUN\`. Do not modify files elsewhere,
  install packages, or change Python environments. Never modify \`$BASE\`.
- Other AHa-3D tasks run on this machine at the same time in other scene
  directories; do not touch them.
- The GPU is shared. Check free memory with \`nvidia-smi\` before any GPU job; run
  one GPU job at a time; never kill a process you did not start.
- Never overwrite earlier outputs; always write to new directories.
- Do not commit or push with git.
EOF
( cd "$AHA" && bash tools/indoor intake --request "$RUN/request.json" --out "$RUN/intake_check" > "$RUN/intake_check.log" 2>&1 ) \
  || { echo "!! 请求没通过 AHa-3D 的 intake 检查，见 $RUN/intake_check.log" >&2; exit 3; }
rm -rf "$RUN/intake_check"
ln -sfn "$PROJ/scripts/codex_review.sh" "$PROJ/.runtime/bin/codex"
ISOLATE=(unshare --user --map-current-user --pid --fork --mount-proc --kill-child)
"${ISOLATE[@]}" true 2>/dev/null || ISOLATE=()
echo ">> 材质版 $NAME（底子 $BASE）→ $RUN"
START=$(date +%s.%N)
( cd "$AHA" && CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_ARTIFACT=1 exec "${ISOLATE[@]}" "$CLAUDE" \
    -p "$(cat "$RUN/prompt.md")" --output-format stream-json --verbose \
    --model "$CLAUDE_MODEL" --effort "$CLAUDE_EFFORT" --dangerously-skip-permissions \
    --setting-sources project,local --disable-slash-commands --strict-mcp-config \
    < /dev/null > "$RUN/events.jsonl" 2> "$RUN/stderr.log" )
CODE=$?
END=$(date +%s.%N)
"$PY" - "$RUN" "$CODE" "$START" "$END" <<'PYEOF'
import sys
from smallobj import runlog
run, code, t0, t1 = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
usage, limits = runlog.parse_claude_stream(f"{run}/events.jsonl"), runlog.claude_rate_limits(f"{run}/events.jsonl")
print(runlog.write_run_log(run, code, t1 - t0, usage, limits, account="claude"))
PYEOF
[ -f "$RUN/scene.blend" ] || echo "!! 没有得到 .blend"
