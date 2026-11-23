"""架构图里用的真实小图（都来自测试房间 42898849），写到 paper/smallobj/figures/pipeline/。

frame_<k>.jpg   输入视频的 3 帧
points.jpg      参考几何：Pi3X 的彩色点云（斜上方正交投影）和 32 个相机位置
detect.jpg      修订后的清单：某一帧上的检测框（清单里以该帧为最佳帧的条目，取条目最多的一帧）
boxes.png       逐项清单的 3D 框俯视图，按 agent 的表态上色（建了：蓝；重复、部件、跳过：灰）
用法：.runtime/venv/bin/python scripts/paper/pipeline_assets.py [房间号]
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

PROJ = Path(__file__).resolve().parents[2]
SID = sys.argv[1] if len(sys.argv) > 1 else "42898849"
P = PROJ / "perception" / SID
OUT = PROJ / "paper" / "smallobj" / "figures" / "pipeline"
OUT.mkdir(parents=True, exist_ok=True)


def frames():
    cams = json.loads((P / "hd" / "cameras.json").read_text())["frames"]
    for k, i in enumerate((3, len(cams) // 2 - 2, len(cams) - 8)):
        im = Image.open(P / "hd" / "frames" / f"{int(cams[i]['source_frame']):06d}.png").convert("RGB")
        im.resize((480, int(480 * im.height / im.width)), Image.LANCZOS).save(OUT / f"frame_{k}.jpg", quality=90)


def points(size=(1500, 1125), cut_z=1.75):
    """Pi3X 的彩色点云变到房间坐标（用 32 个相机中心拟合相似变换），按整体图同一个斜上方方向做正交投影；
    高于 cut_z 的点不画（相当于把房间削掉上半截），再画上每个相机的视锥。"""
    from smallobj import align
    d = np.load(P / "bundle" / "pi3x" / "reference_samples.npz")
    pts, col, raw = d["points"], d["colors"], d["camera_c2w"]
    cams = [np.asarray(f["c2w"], float) for f in json.loads((P / "bundle" / "alignment" / "cameras.json").read_text())["frames"]]
    s, R, tr = align.align_sim3(raw[:, :3, 3], np.array([c[:3, 3] for c in cams]), gravity=False)
    pts = s * pts @ R.T + tr
    keep = (pts[:, 2] < cut_z) & (pts[:, 2] > -0.3)
    pts, col = pts[keep], col[keep]
    direction = np.array([0.55, -0.75, 0.0]) / np.hypot(0.55, 0.75)
    fwd = -(direction * 0.85 + np.array([0, 0, 1.15])); fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    c = np.median(pts, 0)
    proj = lambda x: ((x - c) @ right, (x - c) @ up, (x - c) @ fwd)
    u, v, depth = proj(pts)
    ulo, uhi, vlo, vhi = np.percentile(u, 0.3), np.percentile(u, 99.7), np.percentile(v, 0.3), np.percentile(v, 99.7)
    sc = 0.9 * min(size[0] / (uhi - ulo), size[1] / (vhi - vlo))
    px = lambda uu, vv: (np.round((uu - (ulo + uhi) / 2) * sc + size[0] / 2).astype(int), np.round(size[1] / 2 - (vv - (vlo + vhi) / 2) * sc).astype(int))
    img = np.full((size[1], size[0], 3), 255, np.uint8)
    x, y = px(u, v)
    order = np.argsort(-depth)  # 远的先画
    for dx in range(3):
        for dy in range(3):
            xx, yy = x[order] + dx, y[order] + dy
            ok = (xx >= 0) & (xx < size[0]) & (yy >= 0) & (yy < size[1])
            img[yy[ok], xx[ok]] = col[order][ok]
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im)
    for c2w in cams:  # 视锥：相机中心到 0.28 m 处的四个角
        o = c2w[:3, 3]
        corners = [o + c2w[:3, :3] @ (0.28 * np.array([sx * 0.62, sy * 0.47, 1.0])) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        po = tuple(int(a[0]) for a in px(*proj(o[None])[:2]))
        pc = [tuple(int(a[0]) for a in px(*proj(k[None])[:2])) for k in corners]
        for k in pc:
            dr.line([po, k], fill=(15, 77, 146), width=3)
        dr.line(pc + [pc[0]], fill=(15, 77, 146), width=4)
    box = Image.fromarray((255 - img).max(-1)).point(lambda a: 255 if a > 10 else 0).getbbox()
    im.crop((max(0, box[0] - 30), max(0, box[1] - 30), min(size[0], box[2] + 30), min(size[1], box[3] + 30))).save(OUT / "points.jpg", quality=93)


def detect():
    items = json.loads((P / "inventory_v2_list.json").read_text())
    best = collections.Counter(int(it["best_frame"]) for it in items if it.get("bbox2d_xyxy") and max(it["size"]) < 0.5).most_common(1)[0][0]
    im = Image.open(P / "hd" / "frames" / f"{best:06d}.png").convert("RGB")
    dr = ImageDraw.Draw(im)
    n = 0
    for it in items:
        if int(it.get("best_frame", -1)) == best and it.get("bbox2d_xyxy"):
            small = max(it["size"]) < 0.5
            dr.rectangle(it["bbox2d_xyxy"], outline=(255, 214, 0) if small else (255, 255, 255), width=3 if small else 2)
            n += small
    im.resize((640, int(640 * im.height / im.width)), Image.LANCZOS).save(OUT / "detect.jpg", quality=90)
    print("detect frame", best, "small entries", n, im.size)


def boxes():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    items = json.loads((P / "inventory_v2_list.json").read_text())
    dec = json.loads((PROJ / "runs" / "A5-claude" / SID / "0" / "inventory_decisions.json").read_text())
    fig, ax = plt.subplots(figsize=(4, 3))
    for built in (False, True):
        for it in items:
            if (dec.get(it["item_id"], {}).get("action") == "built") != built or max(it["size"]) > 2.5:
                continue
            l, w = it["size"][0] / 2, it["size"][1] / 2
            c, s = np.cos(it["yaw"]), np.sin(it["yaw"])
            corners = [(it["center"][0] + c * x - s * y, it["center"][1] + s * x + c * y) for x, y in ((-l, -w), (l, -w), (l, w), (-l, w))]
            ax.add_patch(Polygon(corners, closed=True, fc=("#3775BA" if built else "#CFCECE"), ec=("#0F4D92" if built else "#9A9A9A"),
                                 lw=0.5, alpha=0.85 if built else 0.55))
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(OUT / "boxes.png", dpi=260, bbox_inches="tight", pad_inches=0.02)
    print("boxes", len(items), sum(v.get("action") == "built" for v in dec.values()))


frames(); points(); detect(); boxes()


def fit(src, dst, aspect, focus=(0.5, 0.5), width=700, pad=False):
    """裁成（或垫白成）指定宽高比的小图。focus 是裁剪窗口中心在原图里的相对位置。"""
    im = Image.open(src).convert("RGB")
    if pad:
        w = max(im.width, int(im.height * aspect)); h = int(w / aspect)
        canvas = Image.new("RGB", (w, max(h, im.height)), "white")
        canvas.paste(im, ((canvas.width - im.width) // 2, (canvas.height - im.height) // 2))
        im = canvas
    w, h = im.size
    cw, ch = (w, int(w / aspect)) if w / h < aspect else (int(h * aspect), h)
    x0 = int(min(max(focus[0] * w - cw / 2, 0), w - cw)); y0 = int(min(max(focus[1] * h - ch / 2, 0), h - ch))
    im.crop((x0, y0, x0 + cw, y0 + ch)).resize((width, int(width / aspect)), Image.LANCZOS).save(dst, quality=92)


PAN = OUT.parent / "panels"
QUAL = OUT.parent / "qual" / SID
TEAM = PROJ / "third_party" / "agent_3d" / "paper" / "paper_file" / "figures"
uniform = OUT.parent / "qual_uniform" / SID / "A5_overview.png"  # 小物体统一蓝色的整体图（qualitative.py --uniform）
fit(OUT / "points.jpg", OUT / "a2_points.jpg", 3.0 / 1.9, pad=True)
fit(uniform if uniform.exists() else QUAL / "A5_overview.png", OUT / "a3_doll.jpg", 2.75 / 2.15, pad=True, width=900)
mat = QUAL / "MAT_overview.png"  # 材质版整体图（materials_views.py），没有就先用白膜图占位
fit(mat if mat.exists() else QUAL / "A5_overview.png", OUT / "a5_mat.jpg", 2.75 / 2.15, pad=True, width=900)
fit(OUT / "detect.jpg", OUT / "b1_detect.jpg", 2.0 / 1.36, focus=(0.5, 0.40))
fit(OUT / "boxes.png", OUT / "b1_boxes.jpg", 1.9 / 1.5, pad=True)
fit(TEAM / "coffee-rest.png", OUT / "b3_phys.jpg", 2.7 / 1.36, focus=(0.45, 0.55))
fit(TEAM / "tissue-density.png", OUT / "b3_density.jpg", 1.2 / 1.3, focus=(0.5, 0.55))
for cid in ("c225", "c502", "c018", "c075"):  # 清单条目的裁图：建了、重复、部件、跳过各一个
    fit(P / "inventory_v2_crops" / f"{cid}.jpg", OUT / f"{cid}.jpg", 1.0, width=240)


def elevation(size=(820, 580)):
    """对齐之后的点云侧视图（沿房间长边方向看）：地面是一条水平线，配重力方向和 1 米比例尺，说明坐标是重力对齐、米制的。"""
    from smallobj import align
    d = np.load(P / "bundle" / "pi3x" / "reference_samples.npz")
    pts, col, raw = d["points"], d["colors"], d["camera_c2w"]
    cams = [np.asarray(f["c2w"], float) for f in json.loads((P / "bundle" / "alignment" / "cameras.json").read_text())["frames"]]
    s, R, tr = align.align_sim3(raw[:, :3, 3], np.array([c[:3, 3] for c in cams]), gravity=False)
    pts = s * pts @ R.T + tr
    xy = pts[:, :2] - pts[:, :2].mean(0)
    w, v = np.linalg.eigh(np.cov(xy.T))
    long_axis, short_axis = v[:, 1], v[:, 0]
    u, depth, z = xy @ short_axis, xy @ long_axis, pts[:, 2]
    keep = (z > -0.15) & (z < 2.9) & (depth > np.percentile(depth, 15)) & (depth < np.percentile(depth, 55))  # 只留靠后的一半，免得前排家具把后面全挡住
    u, depth, z, col = u[keep], depth[keep], z[keep], col[keep]
    ulo, uhi = np.percentile(u, 0.5), np.percentile(u, 99.5)
    sc = 0.80 * size[0] / (uhi - ulo)
    x = np.round((u - (ulo + uhi) / 2) * sc + size[0] / 2).astype(int)
    y0 = int(size[1] * 0.78)
    y = np.round(y0 - z * sc).astype(int)
    img = np.full((size[1], size[0], 3), 255, np.uint8)
    order = np.argsort(-depth)
    for dx in range(2):
        for dy in range(2):
            xx, yy = x[order] + dx, y[order] + dy
            ok = (xx >= 0) & (xx < size[0]) & (yy >= 0) & (yy < size[1])
            img[yy[ok], xx[ok]] = col[order][ok]
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im)
    navy = (20, 33, 61)
    dr.line([(int(size[0] * 0.03), y0), (int(size[0] * 0.97), y0)], fill=navy, width=5)  # 地面
    ax = int(size[0] * 0.055)
    dr.line([(ax, y0), (ax, y0 - int(1.9 * sc))], fill=navy, width=5)  # 重力方向
    dr.polygon([(ax - 13, y0 - int(1.9 * sc)), (ax + 13, y0 - int(1.9 * sc)), (ax, y0 - int(1.9 * sc) - 26)], fill=navy)
    bx = int(size[0] * 0.74)
    by = y0 + int(size[1] * 0.12)
    dr.line([(bx, by), (bx + int(sc), by)], fill=navy, width=6)  # 1 米比例尺
    for e in (bx, bx + int(sc)):
        dr.line([(e, by - 12), (e, by + 12)], fill=navy, width=5)
    from PIL import ImageFont
    dr.text((bx + int(sc) + 14, by - 22), "1 m", fill=navy, font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38))
    im.save(OUT / "align.jpg", quality=93)
    print("elevation: 1 m =", round(sc), "px of", size[0])


elevation()
INSP = PROJ / "third_party" / "aha-3d" / "scenes" / f"{SID}_a5-claude_s0" / "review" / "inspection_v4"  # agent 自己存的检查图
MASKS = P / "bundle" / "masks"


def mask_tiles(frame="000835"):
    """SAM 3 那张步骤卡的两张小图：左边原帧，右边同一帧去色后把几类掩码涂成不同颜色（墙蓝、地面金、玻璃绿）。
    流程存的掩码预览是原帧上涂一层黄，两类各放一张时看起来像同一张照片；这里从预览和原帧的差里取回掩码，合成一张。"""
    base = np.asarray(Image.open(MASKS / f"{frame}_person.jpg").convert("RGB"), float)  # 这一帧里没有人，等于原帧
    gray = base.mean(axis=2, keepdims=True)
    out = 0.35 * base + 0.65 * (0.55 * gray + 110)  # 去色、提亮，让颜色块读得出来
    for name, colour in (("wall", (55, 117, 186)), ("floor", (201, 150, 40)), ("glass", (27, 175, 122))):
        over = np.asarray(Image.open(MASKS / f"{frame}_{name}.jpg").convert("RGB"), float)
        m = np.abs(over - base).sum(axis=2) > 45
        out[m] = 0.38 * out[m] + 0.62 * np.array(colour, float)
    Image.fromarray(base.astype(np.uint8)).save(OUT / "_mask_src.png")
    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(OUT / "_mask_seg.png")
    fit(OUT / "_mask_src.png", OUT / "mask_wall.jpg", 0.66 / 0.93, width=320)   # 文件名沿用旧的：左图
    fit(OUT / "_mask_seg.png", OUT / "mask_floor.jpg", 0.66 / 0.93, width=320)  # 右图
    (OUT / "_mask_src.png").unlink(); (OUT / "_mask_seg.png").unlink()


mask_tiles()
if INSP.exists():
    fit(INSP / "source_000928_model.png", OUT / "insp_model.jpg", 0.66 / 0.93, width=320)
    fit(INSP / "source_000928_overlay.png", OUT / "insp_overlay.jpg", 0.66 / 0.93, width=320)
    fit(INSP / "source_000928_source.png", OUT / "insp_source.jpg", 0.66 / 0.93, width=320)
fit(OUT / "points.jpg", OUT / "t_points.jpg", 1.38 / 1.0, pad=True, width=520)
fit(OUT / "align.jpg", OUT / "t_align.jpg", 1.38 / 1.0, focus=(0.52, 0.6), width=520)
fit(PAN / f"{SID}_MAT.jpg" if (PAN / f"{SID}_MAT.jpg").exists() else PAN / f"{SID}_A5.jpg", OUT / "t_mat.jpg", 1.6 / 1.0, width=560)
for src, dst in ((OUT / "points.jpg", "hero_points.jpg"), (uniform if uniform.exists() else QUAL / "A5_overview.png", "hero_white.jpg"),
                 (mat if mat.exists() else QUAL / "A5_overview.png", "hero_mat.jpg")):
    fit(src, OUT / dst, 4.25 / 2.5, pad=True, width=1300)
fit(QUAL / "A0_overview.png", OUT / "hero_base.jpg", 1.38 / 0.88, pad=True, width=620)  # 不给清单的原版（37 个实例），白膜大图角上的小图
