"""对比图换机位用的挑选页：每个房间一张图，每行一个候选机位，六列和论文里那张图一样（视频帧、四个组、材质版）。

候选机位先用 QUAL_DIR=qual_cand 跑 qualitative.py --top 0 --extra <房间:帧> ... 和 materials_views.py 渲染好。
用法：.runtime/venv/bin/python scripts/paper/candidate_sheets.py [--src qual_cand2 --tag more --first E]
输出 docs/report/figure5-candidates/room<N>.jpg 和 all-rooms.pdf；带 --tag 时是 room<N>-<tag>.jpg 和 all-rooms-<tag>.pdf，
只出 --src 目录里有的房间，行的字母从 --first 起（第二批候选接着第一批往下排）。
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJ = Path(__file__).resolve().parents[2]
FIGS = PROJ / "paper" / "smallobj" / "figures"
OUT = PROJ / "docs" / "report" / "figure5-candidates"
ROOMS = ["42897538", "42898849", "42899617", "42899712", "42899729", "44358442"]
COLS = [("frame", "Video frame"), ("A0", "AHa-3D baseline"), ("A1", "All objects"), ("A2", "Inventory"), ("A5", "Checklist (ours)"), ("MAT", "Checklist + materials")]
CURRENT = {"42897538": 123, "42898849": 835, "42899617": 37, "42899712": 277, "42899729": 476, "44358442": 437}  # 论文里现在用的帧
# 竖拍房间：每个候选帧裁 4:3 的位置（0 顶、1 底），手调到小物体在画面里
CROP = {"42898849": {835: 0.42, 1021: 0.25, 186: 0.75, 510: 0.40}}
PW, PH, GAP, LEFT, TOP, ROWLAB = 480, 360, 6, 20, 54, 40
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def panel(path, frac):
    im = Image.open(path).convert("RGB")
    if im.height > im.width:
        h = im.width * 3 // 4
        top = int((im.height - h) * frac)
        im = im.crop((0, top, im.width, top + h))
    return im.resize((PW, PH), Image.LANCZOS)


def sheet(n, sid, SRC, first):
    frames = json.loads((SRC / sid / "meta.json").read_text())["frames"]
    W = LEFT * 2 + len(COLS) * PW + (len(COLS) - 1) * GAP
    H = TOP + len(frames) * (ROWLAB + PH) + LEFT
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    head, lab, bold = ImageFont.truetype(FONT, 22), ImageFont.truetype(FONT, 24), ImageFont.truetype(BOLD, 24)
    for c, (_, name) in enumerate(COLS):
        d.text((LEFT + c * (PW + GAP) + PW / 2, 30), name, fill=(60, 60, 60), font=head, anchor="mm")
    for r, f in enumerate(frames):
        y = TOP + r * (ROWLAB + PH)
        cur = f["source_frame"] == CURRENT[sid]
        tag = f"Room {n} – {chr(ord(first) + r)}"
        d.text((LEFT, y + ROWLAB / 2), tag, fill=(20, 33, 61), font=bold, anchor="lm")
        rest = f"   video frame {f['source_frame']}  ·  {f['small_targets_in_view']} annotated objects < 50 cm in view" + ("  ·  CURRENT" if cur else "")
        d.text((LEFT + d.textlength(tag, font=bold), y + ROWLAB / 2), rest, fill=(42, 120, 214) if cur else (90, 90, 90), font=lab, anchor="lm")
        frac = CROP.get(sid, {}).get(f["source_frame"], 0.5)
        for c, (key, _) in enumerate(COLS):
            p = SRC / sid / (f"frame_{f['k']}.jpg" if key == "frame" else f"{key}_{f['k']}.png")
            if p.exists():
                im.paste(panel(p, frac), (LEFT + c * (PW + GAP), y + ROWLAB))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="qual_cand")
    ap.add_argument("--tag", default="")
    ap.add_argument("--first", default="A")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    pages, suffix = [], f"-{a.tag}" if a.tag else ""
    for n, sid in enumerate(ROOMS, 1):
        if not (FIGS / a.src / sid / "meta.json").exists():
            continue
        im = sheet(n, sid, FIGS / a.src, a.first)
        im.save(OUT / f"room{n}{suffix}.jpg", quality=90)
        pages.append(im)
    pages[0].save(OUT / f"all-rooms{suffix}.pdf", save_all=True, append_images=pages[1:], resolution=200)
    print("wrote", OUT, [p.size for p in pages])


if __name__ == "__main__":
    main()
