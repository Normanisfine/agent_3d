"""每个最终场景出一张对比图：三行（原视频的 3 帧高清图、同机位的白膜渲染、两者叠加），右边一张整体图。

用法：PYTHONPATH=src .runtime/venv/bin/python scripts/render_compare.py [--color] [runs/A1/47331262/0 ...]（不给就全部）
输出 results/renders/<组>_<场景>.jpg。--color：每个零件的颜色取自视频（smallobj.colorize），
输出 results/renders/color/<组>_<场景>.jpg。机位用 Pi3X 的位姿（perception/<id>/hd/cameras.json），和 .blend 同一个房间坐标。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from smallobj.export_blend import BLENDER

PROJ = Path(__file__).resolve().parent.parent
OUT = PROJ / "results" / "renders"


LEGEND = [("XS < 0.2 m", (230, 77, 69)), ("S 0.2–0.5 m", (245, 158, 51)), ("M 0.5–1.5 m", (69, 135, 209)),
          ("L ≥ 1.5 m", (92, 168, 107)), ("墙 / 地面", (219, 217, 212))]
TITLE = {"A0": "A0 原版 agent", "A1": "A1 认真版 agent", "A2": "A2 agent + 清单", "A3r": "A3r 按规则生成",
         "A3v": "A3v agent 决定生成", "P0": "P0 不用大模型（Boxer 清单）", "P0c": "P0c 不用大模型（干净对照清单）"}
COLOR_LEGEND = [("颜色取自视频里对应的像素", None), ("灰：和视频对不上，取不到颜色", (140, 140, 140))]


def _font(size):
    from PIL import ImageFont
    for f in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose(arm, sid, src_paths, render_paths, overview_path, out, legend=LEGEND):
    """三行：原视频 / 同机位渲染 / 两者半透明叠加；右边整体图；上方标题和颜色图例。"""
    renders = [Image.open(p).convert("RGB") for p in render_paths]
    w, h = renders[0].size
    srcs = [Image.open(p).convert("RGB").resize((w, h), Image.LANCZOS) for p in src_paths]
    overlays = [Image.blend(a, b, 0.5) for a, b in zip(srcs, renders)]
    ov = Image.open(overview_path).convert("RGB")
    import numpy as np
    a = np.asarray(ov).astype(int)
    fg = np.abs(a - a[0, 0]).sum(-1) > 12  # 和背景色不同的像素：裁掉四周空白，让房间填满整体图
    if fg.any():
        ys, xs = np.nonzero(fg)
        m = 30
        ov = ov.crop((max(0, xs.min() - m), max(0, ys.min() - m), min(ov.width, xs.max() + m), min(ov.height, ys.max() + m)))
    ov_w = min(int(ov.width * 3 * h / ov.height), int(1.6 * 3 * h))
    ov_h = min(3 * h, int(ov.height * ov_w / ov.width))
    ov = ov.resize((ov_w, ov_h), Image.LANCZOS)
    label_w, head = 150, 96
    sheet = Image.new("RGB", (label_w + 3 * w + ov_w, head + 3 * h), "white")
    draw = ImageDraw.Draw(sheet)
    for row, imgs in enumerate((srcs, renders, overlays)):
        for k, im in enumerate(imgs):
            sheet.paste(im, (label_w + k * w, head + row * h))
        draw.text((16, head + row * h + h // 2 - 24), ("原视频", "渲染", "叠加")[row], fill=(40, 40, 40), font=_font(44))
    sheet.paste(ov, (label_w + 3 * w, head + (3 * h - ov_h) // 2))
    draw.text((16, 16), f"{TITLE.get(arm, arm)}    场景 {sid}", fill=(20, 20, 20), font=_font(56))
    x = label_w + 3 * w + 20
    for name, rgb in legend:
        if rgb is not None:
            draw.rectangle([x, 30, x + 40, 70], fill=rgb, outline=(80, 80, 80))
            x += 52
        draw.text((x, 22), name, fill=(40, 40, 40), font=_font(40))
        x += int(draw.textlength(name, font=_font(40))) + 44
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out


def part_colors(run: Path, hd: Path, cams: dict, tmp: str) -> dict:
    """每个零件的线性 RGB（Blender 用）：表面撒点，投到全部高清帧上，按深度去掉被挡住的。"""
    import numpy as np
    from smallobj import colorize
    npz = Path(tmp, "parts.npz")
    subprocess.run([str(BLENDER), "-b", str(run / "scene.blend"), "--python", str(PROJ / "scripts" / "blender_dump_parts.py"),
                    "--", str(npz)], capture_output=True, text=True, check=True)
    d = np.load(npz)
    points, root_of = {}, {}
    for i, (name, root) in enumerate(zip(d["names"].tolist(), d["roots"].tolist())):
        tris = d["tris"][d["offsets"][i]:d["offsets"][i + 1]]
        area = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1).sum()
        points[name] = colorize.sample_surface(tris, int(np.clip(area * 3000, 60, 600)), seed=i)
        root_of[name] = root
    views = [(f, np.asarray(Image.open(hd / "frames" / f"{int(f['source_frame']):06d}.png").convert("RGB")),
              np.load(hd / "depth" / f"{int(f['source_frame']):06d}.npy")) for f in cams["frames"]]
    got = colorize.object_colors(points, root_of, views)
    n_own = sum(v["source"] == "own" for v in got.values())
    print(f"{run.parts[-3]} {run.parts[-2]}：{len(points)} 个零件，自己取到颜色 {n_own}，跟根节点 {len(got) - n_own}，"
          f"没取到 {len(points) - len(got)}", flush=True)
    return {k: colorize.srgb_to_linear(v["rgb"]).tolist() for k, v in got.items()}


def render(run: Path, color: bool = False):
    arm, sid = run.parts[-3], run.parts[-2]
    hd = PROJ / "perception" / sid / "hd"
    if not (hd / "cameras.json").exists() or not (run / "scene.blend").exists():
        return None
    cams = json.loads((hd / "cameras.json").read_text())
    frames = cams["frames"]
    pick = [frames[i] for i in (4, len(frames) // 2, len(frames) - 5)]
    with tempfile.TemporaryDirectory() as tmp:
        spec = {"views": [{"name": f"v{k}", "c2w": f["c2w"], "K": f["K"], "size_wh": cams["size_wh"]} for k, f in enumerate(pick)],
                "out_dir": tmp, "scale": 0.75}
        if color:
            spec["colors"] = part_colors(run, hd, cams, tmp)
        Path(tmp, "spec.json").write_text(json.dumps(spec))
        cp = subprocess.run([str(BLENDER), "-b", str(run / "scene.blend"), "--python", str(PROJ / "scripts" / "blender_render_views.py"),
                             "--", str(Path(tmp, "spec.json"))], capture_output=True, text=True)
        if cp.returncode != 0:
            print(arm, sid, "渲染失败", cp.stderr[-300:])
            return None
        out = compose(arm, sid, [hd / "frames" / f"{int(f['source_frame']):06d}.png" for f in pick],
                      [Path(tmp, f"v{k}.png") for k in range(len(pick))], Path(tmp, "overview.png"),
                      OUT / "color" / f"{arm}_{sid}.jpg" if color else OUT / f"{arm}_{sid}.jpg",
                      COLOR_LEGEND if color else LEGEND)
        return out


if __name__ == "__main__":
    color = "--color" in sys.argv[1:]
    runs = [Path(a).resolve() for a in sys.argv[1:] if a != "--color"] or sorted(p for p in (PROJ / "runs").glob("*/*/0") if p.parts[-3] in
                                                                ("A0", "A1", "A2", "A3r", "A3v", "P0", "P0c"))
    for r in runs:
        print(render(r, color), flush=True)
