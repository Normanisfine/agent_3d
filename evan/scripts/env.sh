#!/usr/bin/env bash
# 项目路径常量。其他脚本用 `source "$(dirname "$0")/env.sh"` 引入。
export PROJ="/home/user/6220/Project/ubuntu_final_project"
export AHA="$PROJ/third_party/aha-3d"
export BLENDER="$PROJ/third_party/blender-5.2.1/blender"
export PI3X_PY="$AHA/.runtime/pi3x-inference/venv/bin/python"
export SAM3_PY="$AHA/.runtime/sam3-segmentation/venv/bin/python"
export MESH_PY="$AHA/.runtime/pi3x-mesh/venv/bin/python"
export PY="$PROJ/.runtime/venv/bin/python"
# VS Code 扩展升级后旧目录会被删：取最新的那个（10-27 起 0.164.0-alpha.11.1；之前的运行是 0.162.0-alpha.17.2，版本记在各次 rollout 的 cli_version 里）
export CODEX="$(ls -d /home/user/.vscode/extensions/openai.chatgpt-*-linux-x64/bin/linux-x86_64/codex 2>/dev/null | sort -V | tail -1)"
export CODEX_MODEL="gpt-6.1-sol"
export CODEX_EFFORT="medium"
# Codex 账户（两个 ChatGPT Plus，各自的 CODEX_HOME；queue_runs.sh 每次挑有额度的那个，没登录的自动跳过）
export CODEX_HOMES="${CODEX_HOMES:-$HOME/.codex $HOME/.codex-b}"
# headless Claude Code（DRIVER=claude 时用；VS Code 扩展升级后路径会变）
export CLAUDE="$(ls -d /home/user/.vscode/extensions/anthropic.claude-code-*-linux-x64/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)"
export CLAUDE_MODEL="claude-opus-5-5"
export CLAUDE_EFFORT="medium"   # 和 Codex 的 medium 对齐；不读用户设置里的 xhigh
# Claude 队列：每周额度用完（100%）才停（Yifan 11-20："额度直接跑完就行"；10-27 到 11-20 是 85%）；5 小时窗口用完（100%）才等重置（Yifan 10-28："直接用完，不要有限制"）
export CLAUDE_WEEKLY_MAX="${CLAUDE_WEEKLY_MAX:-100}"
export CLAUDE_PRIMARY_MAX="${CLAUDE_PRIMARY_MAX:-100}"
export PYTHONPATH="$PROJ/src${PYTHONPATH:+:$PYTHONPATH}"
export PI3X_UPSTREAM="$AHA/external/Pi3"
export PI3X_CHECKPOINT="$AHA/.runtime/pi3x/checkpoint/model.safetensors"
# agent 运行（AHa-3D 的 tools/indoor 和审查步骤要用）
export PI3X_MESH_PY="$MESH_PY"
export KIMODO_ENV="$AHA/.runtime/pi3x-inference/venv"
export BLENDER_BIN="$BLENDER"
export PATH="$PROJ/.runtime/bin:$PATH"   # codex（真的，不是 shim）和 blender
export PYTHONDONTWRITEBYTECODE=1
export XFORMERS_DISABLED=1
