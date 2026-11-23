#!/usr/bin/env bash
# 无人值守跑一次 AHa-3D agent（Codex CLI + gpt-6.1-sol medium）。
# 用法：bash scripts/run_agent.sh <arm: A0|A1|A2|A3r|A3v|A5> <scene_id> <seed> [墙钟上限秒，默认读 configs/run_caps.json，0 = 不限]
# A2/A3 开跑前准备：清单裁图（perception/<id>/inventory_crops/），A3 还要生成用的物体掩码（item_masks/）、
#   A3r 的必须生成名单（$RUN/route_generate.json）；生成次数按这次运行单独计数（SMALLOBJ_BUDGET）。
# 工具调用次数上限读 configs/run_caps.json 的 tool_calls，到了由 scripts/watch_tool_cap.sh 停掉，状态记为 tool_cap。
# 10-27 起 run_caps.json 两项都是 0：按 AHa-3D 原版跑，不限时间和工具调用次数。
# 输出：runs/<arm>/<scene>/<seed>/{prompt.md, request.json, events.jsonl, scene.blend, SUMMARY.md, run_log.json}
# 护栏（触发时退出码 3，queue_runs.sh 整批停下）：每天最多 12 次 agent 运行（按 runs/A*/*/*/run_log.json 的日期数，满了退出码 5）；
#   每周额度单次涨超过 15 个百分点；开跑前缺 codex、感知结果或输入视频；运行记录写不出来；
#   基础设施问题（infra）或撞了额度上限（rate_limited）；agent 命令里碰到真值路径（run_log 标 leak_suspect）。
set -uo pipefail
source "$(dirname "$0")/env.sh"
ARM="$1"; SID="$2"; SEED="$3"
case "$ARM" in A0|A1|A2|A3r|A3v|A5) ;; *) echo "!! 不认识的实验组 $ARM" >&2; exit 2;; esac
CAP="${4:-$(python3 -c "import json;print(json.load(open('$PROJ/configs/run_caps.json'))['wall_s'])" 2>/dev/null || echo 3600)}"   # 0 = 不限（timeout 0 不计时）
# 工具调用次数上限（codex exec 整次只有一个 turn，用完成的命令执行次数当"轮数"）；没有 run_caps.json 就不限
TOOL_CAP="$(python3 -c "import json;print(json.load(open('$PROJ/configs/run_caps.json')).get('tool_calls',0))" 2>/dev/null || echo 0)"
DRIVER="${DRIVER:-codex}"   # claude（10-27 起的主实验：Opus 5.5，原版规则；输出放 runs/<arm>-claude/）或 codex（旧规则的对照组）
case "$DRIVER" in codex) RUNARM="$ARM";; claude) RUNARM="$ARM-claude";; *) echo "!! 不认识的驱动 $DRIVER" >&2; exit 2;; esac
# PERCEPTION=betty（11-20 起的对照）：用 Betty 上 25.5 万像素的感知（perception_betty/，先跑 scripts/betty/localize_bundle.py），
# 输出放 runs/<arm>-claude-betty/。清单和生成用的掩码是按笔记本那份感知的坐标做的，所以只支持不带清单的 A0、A1。
PERCEPTION="${PERCEPTION:-laptop}"
case "$PERCEPTION" in
  laptop) PDIR=perception;;
  betty) PDIR=perception_betty; RUNARM="$RUNARM-betty"
    [[ "$ARM" == A0 || "$ARM" == A1 ]] || { echo "!! PERCEPTION=betty 只支持 A0、A1" >&2; exit 2; };;
  *) echo "!! 不认识的感知 $PERCEPTION" >&2; exit 2;;
esac
RUN="$PROJ/runs/$RUNARM/$SID/$SEED"
[ -e "$RUN/run_log.json" ] && { echo "!! $RUN 已经跑过" >&2; exit 2; }
TODAY=$(date +%F)
# 只数 Codex 驱动的 agent 组（A*，不含 -claude）；P0、P0c 不调大模型。Claude 驱动由队列按订阅的每周额度（85%）管，不数次数
N_TODAY=$(find "$PROJ"/runs/A* -path "*-claude*/*" -prune -o -name run_log.json -newermt "$TODAY" -print 2>/dev/null | wc -l)
DAILY_CAP="${DAILY_CAP:-12}"   # 10-27 Yifan 从 6 提到 12
[ "$DRIVER" = codex ] && ! (( N_TODAY < DAILY_CAP )) && { echo "!! 今天已经跑了 $N_TODAY 次，到上限 $DAILY_CAP 次" >&2; exit 5; }   # 5 = 只是今天满了，队列等到明天

if [ "$SID" = office48 ]; then REF="$(ls -d "$PROJ"/runs/legacy/office48-reference-*/ | tail -1)"; VIDEO="$PROJ/scenes/office48/source.mp4"
else REF="$PROJ/$PDIR/$SID/bundle"; VIDEO="$PROJ/scenes/$SID/input.mp4"; fi
# 开跑前检查：缺东西就别开跑，免得白烧额度、还把这个名额记成跑过
if [ "$DRIVER" = codex ]; then
  [ -x "$CODEX" ] || { echo "!! 找不到 codex：$CODEX（VS Code 的 Codex 扩展没装？）" >&2; exit 3; }
else
  [ -n "$CLAUDE" ] && [ -x "$CLAUDE" ] || { echo "!! 找不到 claude：$CLAUDE" >&2; exit 3; }
fi
# AHa-3D 内部的审查步骤用 PATH 上的 .runtime/bin/codex（两种驱动都要）：指到 scripts/codex_review.sh（10-27 起），
# 它调 env.sh 找到的最新版 codex，固定模型和推理强度（不随账户的 config.toml 变），某个账户额度用完就换下一个
ln -sfn "$PROJ/scripts/codex_review.sh" "$PROJ/.runtime/bin/codex"
[ -n "$REF" ] && [ -d "$REF" ] || { echo "!! 缺感知结果：$REF" >&2; exit 3; }
[ -f "$VIDEO" ] || { echo "!! 缺输入视频：$VIDEO" >&2; exit 3; }
INV="$PROJ/perception/$SID/inventory.json"; CROPS_DIR="$PROJ/perception/$SID/inventory_crops"
# A5（11-20 起）：清单 v2 去重后的逐项清单（smallobj.checklist；开发集由 scripts/inventory_v2_checklist_dev.py 写出），裁图单独放一个目录
if [ "$ARM" = A5 ]; then
  INV="$PROJ/perception/$SID/inventory_v2_list.json"; CROPS_DIR="$PROJ/perception/$SID/inventory_v2_crops"
  [ -f "$INV" ] || { echo "!! 缺逐项清单：$INV" >&2; exit 3; }
  [ -d "$CROPS_DIR" ] || "$PY" -c "from smallobj import checklist; checklist.export_crops('$SID')"
fi
if [[ "$ARM" == A2 || "$ARM" == A3* ]]; then
  [ -f "$INV" ] || { echo "!! 缺清单：$INV（先跑 scripts/run_boxer.sh）" >&2; exit 3; }
  [ -d "$PROJ/perception/$SID/inventory_crops" ] || "$PY" -c "from smallobj import inventory; inventory.export_crops('$SID')"
fi
if [[ "$ARM" == A3* ]]; then
  [ -f "$PROJ/perception/$SID/item_masks/index.json" ] || bash "$PROJ/scripts/masks_for_items.sh" "$SID" \
    || { echo "!! 生成用的物体掩码没做出来" >&2; exit 3; }
fi
export SMALLOBJ_BUDGET="budget_${RUNARM}_s${SEED}"
REF="$(cd "$REF" && pwd -P)"
SCENE_RUN="${SID}_${RUNARM,,}_s${SEED}"   # AHa-3D 的场景 ID 只许小写字母、数字、_ 和 -（src/aha3d/config.py）
mkdir -p "$RUN" "$AHA/scenes/$SCENE_RUN/references"
cp --update=none "$VIDEO" "$AHA/scenes/$SCENE_RUN/references/input.mp4"
[ "$ARM" = A3r ] && "$PY" -c "
import json; from smallobj import inventory
json.dump(inventory.route_rule(inventory.load('$INV')), open('$RUN/route_generate.json', 'w'))"
"$PY" -m smallobj.prompts "$ARM" "$RUN/prompt.md" "$RUN/request.json" \
  AHA="$AHA" SCENE_RUN="$SCENE_RUN" REQUEST="$RUN/request.json" REF_DIR="$REF" OUT="$RUN" SCENE_ID="$SID" \
  INVENTORY="$INV" CROPS="$CROPS_DIR" ROUTE="$RUN/route_generate.json" \
  TOOLS="$PROJ/scripts/agent_tools" || { echo "!! 提示词没渲染出来" >&2; exit 3; }

echo ">> $RUNARM $SID seed=$SEED cap=$( (( CAP > 0 )) && echo "${CAP}s" || echo 不限) tool_calls≤$( (( TOOL_CAP > 0 )) && echo "$TOOL_CAP" || echo 不限) → $RUN"
# 每次运行的 agent 放进自己的 PID 命名空间（10-27 起，两条队列同时跑）：agent 的 pkill/pgrep 只看得到自己的进程。
# 10-27 测试集 A1 42897538 的 agent 用过 pkill -f "codex exec --ephemeral"，会连另一条线正在跑的审查一起杀掉。
# 同一个 uid（不是 root），文件、GPU、网络照旧；agent 结束时它留下的后台进程一起结束。用不了就照旧跑并留个标记。
ISOLATE=(unshare --user --map-current-user --pid --fork --mount-proc --kill-child)
"${ISOLATE[@]}" true 2>/dev/null || { ISOLATE=(); echo "!! unshare 用不了，这次不隔离进程" >&2; touch "$RUN/no_pid_isolation"; }
START=$(date +%s.%N)
# --dangerously-bypass-approvals-and-sandbox：agent 要跑无界面 Blender（GPU/EGL）和 codex 审查（联网），
# 沙箱会挡住；范围由提示词限制在 AHa-3D 目录和本次输出目录。
if [ "$DRIVER" = codex ]; then
  "${ISOLATE[@]}" timeout -k 60 "$CAP" "$CODEX" exec -m "$CODEX_MODEL" -c model_reasoning_effort="\"$CODEX_EFFORT\"" \
    --json --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox -C "$AHA" \
    "$(cat "$RUN/prompt.md")" < /dev/null > "$RUN/events.jsonl" 2> "$RUN/stderr.log" &
  PAT=""
else
  # Claude 驱动：同样关掉权限确认（理由同上）；AHa-3D 内部的审查步骤仍调 codex exec，会用掉少量 Codex 额度。
  # 和我们自己的 Claude 环境隔开：不读用户设置（里面的 xhigh 推理强度、技能、连接器），不用技能和 MCP，
  # 关掉自动记忆（否则上一次运行记下的东西会带进下一次）和 Artifact（不往外发布）；推理强度固定为 CLAUDE_EFFORT
  CLAUDE_FLAGS=(--output-format stream-json --verbose --model "$CLAUDE_MODEL" --effort "$CLAUDE_EFFORT" --dangerously-skip-permissions
                --setting-sources project,local --disable-slash-commands --strict-mcp-config)
  ( cd "$AHA" && CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_ARTIFACT=1 exec "${ISOLATE[@]}" timeout -k 60 "$CAP" "$CLAUDE" \
      -p "$(cat "$RUN/prompt.md")" "${CLAUDE_FLAGS[@]}" < /dev/null > "$RUN/events.jsonl" 2> "$RUN/stderr.log" ) &
  PAT='"type":"tool_use"'
fi
AGENT=$!
WATCH=""
if (( TOOL_CAP > 0 )); then
  bash "$PROJ/scripts/watch_tool_cap.sh" "$AGENT" "$RUN/events.jsonl" "$TOOL_CAP" "$RUN/tool_cap_hit" 10 ${PAT:+"$PAT"} & WATCH=$!
fi
wait "$AGENT"; CODE=$?
[ -n "$WATCH" ] && kill "$WATCH" 2>/dev/null
# 10-28 起（Yifan："5 小时窗口直接用完，不要有限制"）：运行中途撞到 Claude 5 小时上限，等窗口重置后续跑同一个会话，
# 这次运行照算。等之前先在 events.jsonl 写一条 smallobj_resume（等待秒数），run_log 的 wall_s 不含等待。
# 每周额度用完、读不到额度时 claude_limit_pause 给 -1，照旧记 rate_limited 停下。
RESUME_MSG="The Claude usage limit paused this run until the 5-hour window reset. Background processes you started before the pause were stopped. Continue the same task from where you left off, under the same instructions."
while [ "$DRIVER" = claude ]; do
  read -r PAUSE SESS < <("$PY" -c "
from smallobj import runlog
p = runlog.claude_limit_pause('$RUN/events.jsonl')
print(p if p is not None else -1, runlog.parse_claude_stream('$RUN/events.jsonl')['thread_id'] or '-')")
  (( PAUSE > 0 )) && [ "$SESS" != - ] || break
  echo ">> $(date +%H:%M) 撞到 Claude 5 小时上限，等 ${PAUSE}s 到重置，再续跑同一个会话"
  sleep "$PAUSE"
  printf '{"type": "smallobj_resume", "paused_s": %s, "session_id": "%s"}\n' "$PAUSE" "$SESS" >> "$RUN/events.jsonl"
  ( cd "$AHA" && CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 CLAUDE_CODE_DISABLE_ARTIFACT=1 exec "${ISOLATE[@]}" timeout -k 60 "$CAP" "$CLAUDE" \
      -p "$RESUME_MSG" --resume "$SESS" "${CLAUDE_FLAGS[@]}" < /dev/null >> "$RUN/events.jsonl" 2>> "$RUN/stderr.log" ); CODE=$?
done
[ -f "$RUN/tool_cap_hit" ] && CODE=200   # = runlog.TOOL_CAP_EXIT
END=$(date +%s.%N)
# agent 没按要求另存时，取本次场景目录下最新的 .blend
if [ ! -f "$RUN/scene.blend" ]; then
  LAST=$(find "$AHA/scenes/$SCENE_RUN" "$RUN" -name "*.blend" -newer "$RUN/prompt.md" 2>/dev/null | xargs -r ls -t | head -1)
  [ -n "$LAST" ] && cp "$LAST" "$RUN/scene.blend"
fi
"$PY" - "$RUN" "$CODE" "$START" "$END" "$PROJ" "$DRIVER" <<'PYEOF'
import sys
from smallobj import runlog
run, code, t0, t1, proj, driver = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5], sys.argv[6]
if driver == "claude":
    # Claude 订阅：token、等价美元，外加 stream 里 rate_limit_event 的 5 小时和每周使用率（10-27 起能读到）
    usage, limits = runlog.parse_claude_stream(f"{run}/events.jsonl"), runlog.claude_rate_limits(f"{run}/events.jsonl")
else:
    usage = runlog.parse_codex_events(f"{run}/events.jsonl")
    roll = runlog.find_rollout(usage["thread_id"])
    limits = runlog.rate_limits(roll) if roll else {}
leaks = runlog.audit_gt_access(f"{run}/events.jsonl", proj)
# 10-28：同一个视频别的运行（别的组的场景、交付、输出）不许碰；碰了记 same_video_suspect，这次不算，归档后重跑（不停整批）
same = runlog.audit_same_video(f"{run}/events.jsonl", run)
import os
paused = runlog.claude_pauses(f"{run}/events.jsonl") if driver == "claude" else 0.0
log = runlog.write_run_log(run, code, t1 - t0 - paused, usage, limits, leak_hits=leaks,
                           account=os.environ.get("CODEX_HOME") if driver == "codex" else "claude", same_video_hits=same,
                           paused_s=paused)
print(log)
if same:
    print("!! agent 碰了同一个视频别的运行（same_video_suspect），这次不算，要归档后重跑：", same[:3], file=sys.stderr)
if leaks:
    print("!! agent 的命令碰到了真值路径（leak_suspect），这次运行作废，整批停下：", leaks[:3], file=sys.stderr)
    sys.exit(3)
if log["status"] in ("infra", "rate_limited"):
    print(f"!! 状态 {log['status']}：不是 agent 的问题，整批停下检查", file=sys.stderr)
    sys.exit(3)
# 单次涨超过 15 个百分点就停只管 Codex；Claude 的每周额度由队列按 85% 的总线管（单次运行不设上限）
sys.exit(3 if driver == "codex" and (log.get("weekly_delta") or 0) > 15 else 0)
PYEOF
GUARD=$?
[ -f "$RUN/scene.blend" ] || echo "!! 没有得到 .blend"
if (( GUARD != 0 && GUARD != 3 )); then
  # 记录脚本自己出错：留一份最小记录（这个名额算用掉），整批停下，护栏不能悄悄失效
  [ -f "$RUN/run_log.json" ] || printf '{"status": "log_error", "exit_code": %s, "wall_s": null}\n' "$CODE" > "$RUN/run_log.json"
  echo "!! 写运行记录出错（退出码 $GUARD），整批停下" >&2; exit 3
fi
(( GUARD == 3 )) && { echo "!! 护栏触发（每周额度单次涨超过 15 个百分点、infra / rate_limited、或碰到真值），停下来问 Yifan" >&2; exit 3; }
exit 0
