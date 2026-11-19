#!/usr/bin/env bash
# 一个场景的高清帧（设计 §8）：从输入视频解码 Pi3X 那 32 帧的原图，配上放大的内参和 Pi3X 深度。
# 用法：bash scripts/extract_hd.sh <scene_id>   输出 perception/<id>/hd/
set -euo pipefail
source "$(dirname "$0")/env.sh"
SID="$1"
"$PY" -c "
from smallobj import hd
c = hd.extract_hd('$PROJ/scenes/$SID/input.mp4', '$PROJ/perception/$SID/bundle', '$PROJ/perception/$SID/hd')
print('$SID', c['size_wh'], len(c['frames']), '帧')
"
