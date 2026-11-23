"""对比图最后一列：材质版场景（runs/showcase/<房间>_<组>_materials/scene.blend）从和其他列同一个视频机位渲染。

机位取 paper/smallobj/figures/qual/<房间>/meta.json 里记下的帧（和 qualitative.py 的第 k 个机位一致）。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/paper/materials_views.py [--arm A5] [--rooms ...]
输出 paper/smallobj/figures/qual/<房间>/MAT_<k>.png；没有材质版场景的房间跳过。环境变量 QUAL_DIR 换目录（和 qualitative.py 一样）。
"""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from smallobj.export_blend import BLENDER

PROJ = Path(__file__).resolve().parents[2]
ROOMS = ["42897538", "42898849", "42899617", "42899712", "42899729", "44358442"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="A5")
    ap.add_argument("--rooms", nargs="*", default=ROOMS)
    a = ap.parse_args()
    for sid in a.rooms:
        blend = PROJ / "runs" / "showcase" / f"{sid}_{a.arm}_materials" / "scene.blend"
        out = PROJ / "paper" / "smallobj" / "figures" / os.environ.get("QUAL_DIR", "qual") / sid
        if not blend.exists() or not (out / "meta.json").exists():
            print(sid, "没有材质版场景或没有机位记录，跳过", flush=True)
            continue
        cams = json.loads((PROJ / "perception" / sid / "hd" / "cameras.json").read_text())
        by_frame = {int(f["source_frame"]): f for f in cams["frames"]}
        frames = json.loads((out / "meta.json").read_text())["frames"]
        with tempfile.TemporaryDirectory() as tmp:
            spec = {"views": [{"name": f"MAT_{f['k']}", "c2w": by_frame[f["source_frame"]]["c2w"], "K": by_frame[f["source_frame"]]["K"],
                               "size_wh": cams["size_wh"]} for f in frames], "out_dir": tmp, "overview": True}
            Path(tmp, "spec.json").write_text(json.dumps(spec))
            cp = subprocess.run([str(BLENDER), "-b", str(blend), "--python", str(Path(__file__).with_name("blender_material_view.py")),
                                 "--", str(Path(tmp, "spec.json"))], capture_output=True, text=True)
            if cp.returncode != 0 or "rendered" not in cp.stdout:
                print(sid, "渲染失败", cp.stderr[-500:], cp.stdout[-300:], flush=True)
                continue
            for p in Path(tmp).glob("MAT_*.png"):
                Image.open(p).convert("RGB").save(out / p.name)
            if Path(tmp, "overview.png").exists():  # 透明底：裁到房间范围，垫白
                im = Image.open(Path(tmp, "overview.png"))
                box = im.getchannel("A").point(lambda x: 255 if x > 8 else 0).getbbox()
                im = im.crop((max(0, box[0] - 20), max(0, box[1] - 20), min(im.width, box[2] + 20), min(im.height, box[3] + 20)))
                bg = Image.new("RGBA", im.size, "white")
                bg.alpha_composite(im)
                bg.convert("RGB").save(out / "MAT_overview.png")
        print(sid, [l for l in cp.stdout.splitlines() if l.startswith("engine")], [f["source_frame"] for f in frames], flush=True)


if __name__ == "__main__":
    main()
