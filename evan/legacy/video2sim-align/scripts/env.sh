# 每个新终端先运行：source scripts/env.sh
# 只设路径变量，不安装、不下载任何东西。

export V2S_ROOT="/home/user/6220/Project/Ubuntu_project/video2sim-align"
export AHA="$V2S_ROOT/third_party/aha-3d"

# Python 3.11 底座（本机系统没有 python3.11，用 miniconda 单独建一个，不动 base 和 env_isaaclab）
export PY311="$V2S_ROOT/.runtime/py311/bin/python3.11"

# AHa-3D 第 1 级（Static）安装后的三个环境
export PI3X_PY="$AHA/.runtime/pi3x-inference/venv/bin/python"
export PI3X_MESH_PY="$AHA/.runtime/pi3x-mesh/venv/bin/python"
export SAM3_PY="$AHA/.runtime/sam3-segmentation/venv/bin/python"
export PI3X_UPSTREAM="$AHA/external/Pi3"

# 模型权重
export PI3X_ROOT="$AHA/.runtime/pi3x"
export PI3X_CHECKPOINT="$PI3X_ROOT/checkpoint/model.safetensors"

# Blender 5.2.1（AHa-3D 的资产库是用这个版本存的）
export RENDER_BLENDER="$V2S_ROOT/.runtime/blender-5.2.1-linux-x64/blender"

export BLENDER_BIN="$RENDER_BLENDER"

# tools/indoor 用 KIMODO_ENV 里的 Python 跑 aha3d；Static 级别下它就是 Pi3X 环境
export KIMODO_ENV="$AHA/.runtime/pi3x-inference/venv"

# B 段：agent 和视觉审查都用 VSCode 插件里最新的 Claude Code，模型 Haiku 5.5
CLAUDE_BIN="$(ls -d "$HOME"/.vscode/extensions/anthropic.claude-code-*-linux-x64/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)"
export CLAUDE_BIN
export AHA_REVIEW_CLAUDE_BIN="$CLAUDE_BIN"
export AHA_REVIEW_MODEL="claude-haiku-5-5"
# codex 转接脚本（把 AHa-3D 写死的 codex exec 审查转给 Claude）和 blender 放进 PATH
export PATH="$V2S_ROOT/tools/codex-shim:$(dirname "$RENDER_BLENDER"):$PATH"

export PYTHONDONTWRITEBYTECODE=1
export XFORMERS_DISABLED=1
