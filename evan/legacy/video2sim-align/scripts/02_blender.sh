#!/usr/bin/env bash
# 第 2 步：下载官方 Blender 5.2.1（约 384 MB），解压到 .runtime/，再做一次无界面自检。
set -euo pipefail
source "$(dirname "$0")/env.sh"

mkdir -p "$V2S_ROOT/.runtime"
cd "$V2S_ROOT/.runtime"
TARBALL=blender-5.2.1-linux-x64.tar.xz
if [[ ! -x "$RENDER_BLENDER" ]]; then
  [[ -f "$TARBALL" ]] || curl -L -o "$TARBALL" "https://download.blender.org/release/Blender5.2/$TARBALL"
  tar -xf "$TARBALL"
  rm -f "$TARBALL"
fi

"$RENDER_BLENDER" --version | head -1
"$RENDER_BLENDER" --background --factory-startup --python-exit-code 1 --python-expr \
  "import bpy; print(bpy.app.version_string); assert hasattr(bpy.types, 'ShaderNodeBsdfPrincipled'); print('BLENDER_API_OK')"
echo ">> 第 2 步完成。看作者的成品：\"\$RENDER_BLENDER\" \"\$AHA/examples/office48/whitebox.blend\""
