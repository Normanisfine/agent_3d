"""把 scripts/paper/qualitative.py 和 materials_views.py 的渲染图整理成论文里用的小图（JPG），放 paper/smallobj/figures/panels/，
再把论文用到的图一起拷到组里的稿子 third_party/agent_3d/paper/paper_file/figures/。

<房间>_frame.jpg、<房间>_<组>.jpg、<房间>_MAT.jpg：同机位对比。机位默认是第 0 个（能看到最多小目标的那一帧）；
房间 4、5 的第 0 个机位对着一面空墙，看不出差别，11-22 按 Yifan 的意思换掉：房间 4 用第 1 个，房间 5 用手挑的一帧（VIEW）。竖拍的房间裁中间一条 4:3，不压扁。
<房间><字母>_<列>.jpg：正文那张对比图里换了机位的房间（ALT），素材在 figures/qual_cand/ 和 qual_cand2/（scripts/paper/candidate_sheets.py 那两批候选）。
<房间>_<组>_ov.jpg：整体图垫白到同一个 4:3 画布；_ovtight.jpg 不垫白。<房间>_MAT_ov.jpg 是材质版的整体图（附录里六个房间那张）。
用法：.runtime/venv/bin/python scripts/paper/assemble_panels.py
"""
import shutil
from pathlib import Path

from PIL import Image

PROJ = Path(__file__).resolve().parents[2]
FIG = PROJ / "paper" / "smallobj" / "figures"
TEAM = PROJ / "third_party" / "agent_3d" / "paper" / "paper_file" / "figures"
ROOMS = ["42897538", "42898849", "42899617", "42899712", "42899729", "44358442"]
ARMS = ["A0", "A1", "A2", "A5"]
VIEW = {"42899712": 1, "42899729": 2}  # 房间 5 的第 2 个是手挑的帧 476（qualitative.py --extra 42899729:476）
CROP = {"42898849": 0.42}  # 竖拍房间的裁剪窗口位置（0 顶、1 底）
# 正文对比图里另换的机位：小图前缀 → (房间, 候选目录, 第几个机位)。房间 6 用 D（帧 453，明信片墙），11-24 Yifan 从候选页里选的。
# 房间 4、5 的候选（qual_cand2 里的 E）试过加进正文，Yifan 当天决定不加。
ALT = {"44358442d": ("44358442", "qual_cand", 3)}


def view(path, frac=0.5, size=(800, 600)):
    """统一成 4:3 横图：竖拍的视频（768×1024）裁一条 4:3，不压扁。"""
    im = Image.open(path).convert("RGB")
    if im.height > im.width:
        h = im.width * 3 // 4
        top = int((im.height - h) * frac)
        im = im.crop((0, top, im.width, top + h))
    return im.resize(size, Image.LANCZOS)


def main():
    out = FIG / "panels"
    out.mkdir(parents=True, exist_ok=True)
    for sid in ROOMS:
        src, k, frac = FIG / "qual" / sid, VIEW.get(sid, 0), CROP.get(sid, 0.5)
        view(src / f"frame_{k}.jpg", frac).save(out / f"{sid}_frame.jpg", quality=90)
        if (src / f"MAT_{k}.png").exists():
            view(src / f"MAT_{k}.png", frac).save(out / f"{sid}_MAT.jpg", quality=90)
        for arm in ARMS + ["MAT"]:
            if arm != "MAT":
                view(src / f"{arm}_{k}.png", frac).save(out / f"{sid}_{arm}.jpg", quality=90)
            elif not (src / "MAT_overview.png").exists():
                continue
            ov = Image.open(src / f"{arm}_overview.png").convert("RGB")
            W, H = 1000, 750
            ov.thumbnail((W, H), Image.LANCZOS)
            canvas = Image.new("RGB", (W, H), "white")
            canvas.paste(ov, ((W - ov.width) // 2, (H - ov.height) // 2))
            canvas.save(out / f"{sid}_{arm}_ov.jpg", quality=90)
            tight = Image.open(src / f"{arm}_overview.png").convert("RGB")
            tight.thumbnail((1100, 1100), Image.LANCZOS)
            tight.save(out / f"{sid}_{arm}_ovtight.jpg", quality=92)
    for key, (sid, cand, k) in ALT.items():
        src, frac = FIG / cand / sid, CROP.get(sid, 0.5)
        for col, name in [("frame", f"frame_{k}.jpg"), ("MAT", f"MAT_{k}.png")] + [(arm, f"{arm}_{k}.png") for arm in ARMS]:
            view(src / name, frac).save(out / f"{key}_{col}.jpg", quality=90)
    print(len(list(out.glob("*.jpg"))), "panels,", len(list(out.glob("*_MAT.jpg"))), "with materials")
    if TEAM.exists():  # 组里的稿子只收对比图用到的小图和两张 PDF
        (TEAM / "panels").mkdir(exist_ok=True)
        for p in out.glob("*.jpg"):
            if "_ov" not in p.name or p.name.endswith("_MAT_ov.jpg"):
                shutil.copy2(p, TEAM / "panels" / p.name)
        for name, dst in (("results.pdf", "small-object-results.pdf"), ("../pipeline/system.pdf", "system-pipeline.pdf")):
            if (FIG / name).exists():
                shutil.copy2(FIG / name, TEAM / dst)
        print("copied to", TEAM)


if __name__ == "__main__":
    main()
