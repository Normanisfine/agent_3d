"""物体清单（设计 §5 A2/A3/P0，§15b `perception/<id>/inventory*.json`）。

每条是 boxes.record 加上 item_id、score、best_frame、bbox2d_xyxy（最好那一帧的高清像素）、n_views，
干净对照的还有 n_frames（合并了几帧的检测）。坐标是流程的房间世界坐标（z 朝上，Pi3X 米制）。
"""
import csv
import json
from pathlib import Path

import numpy as np

from smallobj import boxes, ca1m, evaluate


def fuse(per_frame: list, iou_min: float = 0.25) -> list:
    """多帧检测合并：按置信度从高到低，和已有簇同类别且 3D IoU ≥ iou_min 的并进去（跟簇里最高分的那个比）。
    中心、尺寸按置信度加权平均，yaw 取最高分的，best_frame 取最高分检测所在的帧。"""
    clusters = []
    for d in sorted(per_frame, key=lambda r: -r.get("score", r.get("confidence", 0.0))):
        for c in clusters:
            if c[0]["category"] == d["category"] and evaluate.iou3d(c[0], d) >= iou_min:
                c.append(d)
                break
        else:
            clusters.append([d])
    out = []
    for k, c in enumerate(clusters):
        w = np.array([d.get("score", d.get("confidence", 1.0)) for d in c], float)
        center = (w[:, None] * np.array([d["center"] for d in c])).sum(0) / w.sum()
        sizes = []
        for d in c:  # 同一物体在不同帧可能拟成 (θ, [l, w]) 或 (θ+90°, [w, l])：先换到簇首的朝向再平均
            q = int(round(boxes.wrap(d["yaw"] - c[0]["yaw"]) / (np.pi / 2))) % 2
            sizes.append([d["size"][1], d["size"][0], d["size"][2]] if q else list(d["size"]))
        size = (w[:, None] * np.array(sizes)).sum(0) / w.sum()
        top = c[0]
        rec = boxes.record(f"{top.get('source', 'det')[:1]}{k:03d}", top["category"], center, top["yaw"], size,
                           confidence=float(w.max()), source=top.get("source", "det"))
        rec.update(item_id=rec["object_id"], score=float(w.max()), best_frame=top.get("frame"),
                   bbox2d_xyxy=top.get("bbox2d_xyxy"), n_frames=len(c))
        out.append(rec)
    return out


def _R_from_wxyz(w, x, y, z):
    from scipy.spatial.transform import Rotation
    return Rotation.from_quat([x, y, z, w]).as_matrix()


def from_boxer(raw_dir: Path) -> list:
    """读 Boxer 融合后的 `<raw_dir>/ca1m-hd/boxer_3dbbs_fused.csv`，转成清单记录（source="boxer"）。"""
    path = Path(raw_dir) / "ca1m-hd" / "boxer_3dbbs_fused.csv"
    items = []
    with open(path) as f:
        for k, row in enumerate(csv.DictReader(f)):
            R = _R_from_wxyz(*(float(row[c]) for c in ("qw_world_object", "qx_world_object", "qy_world_object", "qz_world_object")))
            inst = {"id": f"b{k:03d}", "category": row["name"].strip(),
                    "position": [float(row[c]) for c in ("tx_world_object", "ty_world_object", "tz_world_object")],
                    "scale": [float(row[c]) for c in ("scale_x", "scale_y", "scale_z")], "R": R.tolist()}
            rec = ca1m._record_from_world(inst)  # 和真值同一套"有向框 → 重力对齐 yaw 框"的转换
            rec.update(source="boxer", confidence=float(row["prob"]), item_id=inst["id"], score=float(row["prob"]))
            items.append(rec)
    return items


def annotate_views(items: list, cams: dict) -> list:
    """给每条补上 best_frame、bbox2d_xyxy、n_views（按高清帧投影算）。"""
    from smallobj import hd
    for it in items:
        it["best_frame"], it["bbox2d_xyxy"], it["n_views"] = hd.best_view(it, cams)
    return items


def save(items: list, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(items, indent=1) + "\n")


def load(path: Path) -> list:
    return json.loads(Path(path).read_text())


def route_rule(items: list, max_longest_m: float = 0.5) -> list:
    """A3r：估计最长边 < max_longest_m（XS、S 两档）的物体走生成。"""
    return [it["item_id"] for it in items if max(it["size"]) < max_longest_m]


def export_crops(scene_id: str, inventory_name: str = "inventory.json", root: Path = None) -> Path:
    """每个物体在最好那一帧的投影框（四周留 15%）裁一张图：perception/<id>/inventory_crops/<item>.jpg。"""
    from PIL import Image
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    P = root / "perception" / scene_id
    out = P / "inventory_crops"
    out.mkdir(exist_ok=True)
    for it in load(P / inventory_name):
        if it.get("best_frame") is None or not it.get("bbox2d_xyxy"):
            continue
        im = Image.open(P / "hd" / "frames" / f"{int(it['best_frame']):06d}.png")
        x0, y0, x1, y1 = it["bbox2d_xyxy"]
        mx, my = 0.15 * (x1 - x0), 0.15 * (y1 - y0)
        box = (max(0, int(x0 - mx)), max(0, int(y0 - my)), min(im.width, int(x1 + mx) + 1), min(im.height, int(y1 + my) + 1))
        if box[2] - box[0] >= 2 and box[3] - box[1] >= 2:
            im.crop(box).convert("RGB").save(out / f"{it['item_id']}.jpg", quality=90)
    return out
