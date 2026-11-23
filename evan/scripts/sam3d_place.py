"""SAM 3D（Colab）结果接回一个场景：导入 → place_mesh（从 SAM 3D 自己的位姿起步）→ 验收统计 → 对比图。

只用开发集。地面附近的物体（底面离地 < 5 cm）放置时贴地，同 P0。观测点用 MoGe 深度（清单 v2）。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/sam3d_place.py gen/colab/<包>_out.tar.gz
输出 results/sam3d/<scene>/{placements.json, compare.jpg, README.md}。
对比图每个物体三格：原视频帧 | 清单方块（蓝） | SAM 3D 网格摆好后（绿，绿框 = 过验收，橙框 = 没过），
方块和网格都按 SAM 3D 输入的那一帧相机投影成剪影叠在原图上。
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

from smallobj import boxes, gen3d, hd, inventory, place, silhouette

PROJ = Path(__file__).resolve().parent.parent


def overlay(img, mask, color, alpha=0.5):
    out = img.copy()
    out[mask] = (1 - alpha) * out[mask] + alpha * np.asarray(color, float)
    return out


def main(out_tar):
    imported = gen3d.import_sam3d(out_tar, root=PROJ)
    pack_inv = imported[0]["inventory"]
    sid = Path(imported[0]["mesh_glb"]).parts[-4]
    P = PROJ / "perception" / sid
    items = {it["item_id"]: it for it in inventory.load(P / pack_inv)}
    cams = hd.load(P / "hd")
    by_frame = {int(f["source_frame"]): f for f in cams["frames"]}
    placements = {}
    for g in imported:
        if g["status"] != "ok":
            placements[g["item_id"]] = {"status": g["status"]}
            continue
        it = items[g["item_id"]]
        support = 0.0 if it["center"][2] - it["size"][2] / 2 < 0.05 else None
        placements[g["item_id"]] = place.place_mesh(sid, g["item_id"], gen3d.SAM3D_CANDIDATE, support_z=support,
                                                    inventory=pack_inv, root=PROJ, depth_name="depth_moge")
        p = placements[g["item_id"]]
        print(g["item_id"], it["category"], p["status"], round(p.get("fit", {}).get("sil_iou_mean", 0), 2), flush=True)
    outdir = PROJ / "results" / "sam3d" / sid
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "placements.json").write_text(json.dumps(placements, indent=1) + "\n")

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    cell, rows = 220, []
    for g in imported:
        p = placements[g["item_id"]]
        if "matrix_world" not in p:
            continue
        it, f = items[g["item_id"]], by_frame[int(g["frame"])]
        img = np.asarray(Image.open(P / "hd" / "frames" / f"{int(g['frame']):06d}.png").convert("RGB"), float)
        mesh = trimesh.load(g["mesh_glb"], force="mesh")
        pts = trimesh.transform_points(mesh.sample(20000, seed=0), np.asarray(p["matrix_world"]))
        box = trimesh.creation.box(extents=it["size"])
        box.apply_transform(np.block([[boxes.rot_z(it["yaw"]), np.asarray(it["center"], float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]]))
        m_mesh = silhouette.render_mask(pts, f["K"], f["c2w"], cams["size_wh"])
        m_box = silhouette.render_mask(box.sample(20000, seed=0), f["K"], f["c2w"], cams["size_wh"])
        ys, xs = np.nonzero(m_mesh | m_box)
        if len(xs) == 0:
            continue
        side = max(np.ptp(xs), np.ptp(ys)) * 1.6 + 30
        cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        W, H = cams["size_wh"]
        crop = (int(max(0, cx - side / 2)), int(max(0, cy - side / 2)), int(min(W, cx + side / 2)), int(min(H, cy + side / 2)))
        panels = [img, overlay(img, m_box, (60, 120, 255)), overlay(img, m_mesh, (40, 220, 60))]
        ok = p["status"] == "accepted"
        tiles = []
        for k, a in enumerate(panels):
            t = Image.fromarray(a.clip(0, 255).astype(np.uint8)).crop(crop).resize((cell, cell))
            if k == 2:
                ImageDraw.Draw(t).rectangle([0, 0, cell - 1, cell - 1], outline=(0, 200, 0) if ok else (255, 150, 0), width=4)
            tiles.append(t)
        row = Image.new("RGB", (3 * cell + 8, cell + 22), "white")
        for k, t in enumerate(tiles):
            row.paste(t, (k * (cell + 4), 22))
        ImageDraw.Draw(row).text((4, 3), f"{g['item_id']} {it['category']} · {p['status']} · sil IoU "
                                         f"{p['fit']['sil_iou_mean']:.2f} (box {p['fit']['primitive_sil_iou']:.2f})", fill="black", font=font)
        rows.append(row)
    if rows:
        cols = 2
        sheet = Image.new("RGB", (cols * (rows[0].width + 16), ((len(rows) + cols - 1) // cols) * (rows[0].height + 10)), "white")
        for k, r in enumerate(rows):
            sheet.paste(r, ((k % cols) * (r.width + 16), (k // cols) * (r.height + 10)))
        sheet.save(outdir / "compare.jpg", quality=88)
    st = {}
    for p in placements.values():
        st[p.get("status")] = st.get(p.get("status"), 0) + 1
    (outdir / "README.md").write_text(
        f"# SAM 3D 放进场景：{sid}（{pack_inv}）\n\n"
        f"- 包：`{Path(out_tar).name}`，{len(imported)} 个物体；SAM 3D 状态：" +
        "、".join(f"{k} {sum(1 for g in imported if g['status'] == k)}" for k in sorted({g['status'] for g in imported})) + "\n"
        f"- 放置结果：" + "、".join(f"{k} {v}" for k, v in sorted(st.items())) + "\n"
        "- 放置从 SAM 3D 自己的位姿起步（`place.fit(init=\"backend\")`），验收门同 Hunyuan（`configs/gen_gate.json`）。\n"
        "- `compare.jpg`：原视频帧 | 清单方块（蓝） | SAM 3D 网格摆好后（绿）；第三格绿框 = 过验收，橙框 = 没过。\n")
    print(outdir, st)


if __name__ == "__main__":
    main(sys.argv[1])
