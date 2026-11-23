"""清单 v2 的效果图（一个开发场景）：旧干净对照漏掉、v2 找到了的 XS/S 真值物体，从 v2 检测到它的那一帧裁出来拼一张图。

每格标：真值类别 | v2 的类别 | 建对还是建了没摆准。只用开发集。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/inventory_v2_gallery.py <scene_id> [清单文件名，默认 inventory_v2.json]
输出 results/inventory_v2/<scene>_new_finds.jpg（换了清单文件名就是 <scene>_<文件名>_new_finds.jpg）。
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from smallobj import align, boxes, inventory, score

PROJ = Path(__file__).resolve().parent.parent


def main(sid, inv="inventory_v2.json", cols=6, cell=260):
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    P = PROJ / "perception" / sid
    gts = boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")
    tf = align.pipeline_to_gt(P / "bundle", PROJ / "scenes" / sid, with_scale=True)
    old = {r["gt_id"]: r for r in score.score_inventory(inventory.load(P / "inventory_clean.json"), gts, tf, th)}
    v2_items = {it["object_id"]: it for it in inventory.load(P / inv)}
    new = [r for r in score.score_inventory(list(v2_items.values()), gts, tf, th)
           if r["bin"] in ("XS", "S") and r["D"] != "missed" and old[r["gt_id"]]["D"] == "missed"]
    new.sort(key=lambda r: (r["bin"] != "XS", r["D"] != "correct", r["category"]))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    rows = max(1, (len(new) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 40)), "white")
    d = ImageDraw.Draw(sheet)
    for k, r in enumerate(new):
        it = v2_items[r["pred_id"]]
        im = Image.open(P / "hd" / "frames" / f"{int(it['best_frame']):06d}.png").convert("RGB")
        x0, y0, x1, y1 = it["bbox2d_xyxy"]
        side = max(x1 - x0, y1 - y0) * 2.2 + 20          # 物体周围多留一圈，看得出它在哪
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        box = (int(max(0, cx - side / 2)), int(max(0, cy - side / 2)), int(min(im.width, cx + side / 2)), int(min(im.height, cy + side / 2)))
        crop = im.crop(box)
        ImageDraw.Draw(crop).rectangle([x0 - box[0], y0 - box[1], x1 - box[0], y1 - box[1]],
                                       outline=(0, 200, 0) if r["D"] == "correct" else (255, 160, 0), width=3)
        crop.thumbnail((cell, cell))
        gx, gy = (k % cols) * cell, (k // cols) * (cell + 40)
        sheet.paste(crop, (gx + (cell - crop.width) // 2, gy))
        d.text((gx + 4, gy + cell + 2), f"{r['bin']} GT: {r['category']}", fill="black", font=font)
        d.text((gx + 4, gy + cell + 20), f"v2: {it['category']} · {'correct' if r['D'] == 'correct' else 'misplaced'}",
               fill=(0, 130, 0) if r["D"] == "correct" else (200, 110, 0), font=font)
    tag = "" if inv == "inventory_v2.json" else f"_{Path(inv).stem}"
    out = PROJ / "results" / "inventory_v2" / f"{sid}{tag}_new_finds.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    print(out, len(new), "个旧清单漏掉、v2 找到的 XS/S 物体")


if __name__ == "__main__":
    main(*sys.argv[1:3])
