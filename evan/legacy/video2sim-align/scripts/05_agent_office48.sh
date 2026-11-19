#!/usr/bin/env bash
# 第 5 步（B 段）：用 Claude Code + Haiku 5.5 无人值守地驱动 AHa-3D，把 office48 搭成可编辑白模。
# 走你自己账号的额度；会话会保存，事后可以在 VSCode 的 Claude Code 里 resume 接着看。
# 用法：bash scripts/05_agent_office48.sh [参考几何目录]
#   默认用 runs/ 下最新的 office48-reference-*（脚本 04 的输出）
set -euo pipefail
source "$(dirname "$0")/env.sh"

REF_DIR="${1:-$(ls -d "$V2S_ROOT"/runs/office48-reference-*/ 2>/dev/null | sort | tail -1)}"
[[ -f "$REF_DIR/reference_build.json" ]] || { echo "!! 没找到参考几何，先跑脚本 04" >&2; exit 1; }
REF_DIR="$(cd "$REF_DIR" && pwd -P)"   # agent 在 AHa-3D 目录里工作，必须给绝对路径
[[ -x "$CLAUDE_BIN" ]] || { echo "!! 没找到 Claude Code 程序" >&2; exit 1; }

# 视频放进 AHa-3D 约定的位置 scenes/<场景>/references/
mkdir -p "$AHA/scenes/office48_v2s/references"
cp --update=none "$V2S_ROOT/data/office48/source.mp4" "$AHA/scenes/office48_v2s/references/office48.mp4"

OUT="$V2S_ROOT/runs/agent-office48-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
REQUEST="$V2S_ROOT/configs/office48_whitebox_request.json"
sed -e "s#{{REQUEST}}#$REQUEST#g" -e "s#{{REF_DIR}}#$REF_DIR#g" \
    -e "s#{{V2S_ROOT}}#$V2S_ROOT#g" -e "s#{{OUT}}#$OUT#g" -e "s#{{AHA}}#$AHA#g" \
    "$V2S_ROOT/configs/agent_office48_prompt.md" > "$OUT/prompt.md"

echo ">> 参考几何：$REF_DIR"
echo ">> 输出和日志：$OUT"
cd "$AHA"
# 文件编辑只放行 AHa-3D 和 video2sim-align 两个目录；Bash 不限（要跑 Blender 和 Python）
"$CLAUDE_BIN" -p "$(cat "$OUT/prompt.md")" \
  --model claude-haiku-5-5 \
  --permission-mode acceptEdits \
  --allowedTools "Bash Read Write Edit Glob Grep" \
  --add-dir "$V2S_ROOT" \
  --output-format stream-json --verbose \
  > "$OUT/session.jsonl" 2> "$OUT/stderr.log"
echo "EXIT=$?" >> "$OUT/stderr.log"
echo ">> 第 5 步结束，先看 $OUT/SUMMARY.md"
