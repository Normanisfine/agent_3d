"""干净对照清单（设计 §6）：SAM 3 文本提示的实例掩码 + Pi3X 深度反投影 → 每帧拟框 → 多帧合并。

检测部分没用 CA-1M 的标注训练过（Boxer 用过 CA-1M 训练集）；点来自 Pi3X，仍受设计 §13 的 π³ 同源风险影响。
掩码由 scripts/sam3_objects.py（在 AHa-3D 的 sam3 venv 里跑）写到 perception/<id>/sam3_objects/：
index.json 是 [{frame, label, score, mask（相对路径）, box_xyxy}]。
"""
import json
from pathlib import Path

import numpy as np

from smallobj import boxes, hd, inventory


def points_from_mask(mask, depth, K, c2w) -> np.ndarray:
    """掩码内像素用深度反投影到世界坐标；NaN 深度丢掉，再丢掉离中位点超过 2.5 倍中位距离的离群点。"""
    K, c2w = np.asarray(K, float), np.asarray(c2w, float)
    vs, us = np.nonzero(np.asarray(mask, bool) & np.isfinite(depth))
    if len(us) == 0:
        return np.zeros((0, 3))
    z = depth[vs, us].astype(float)
    cam = np.stack([(us - K[0, 2]) / K[0, 0] * z, (vs - K[1, 2]) / K[1, 1] * z, z], -1)
    pts = cam @ c2w[:3, :3].T + c2w[:3, 3]
    d = np.linalg.norm(pts - np.median(pts, 0), axis=1)
    med = np.median(d)
    return pts[d <= 2.5 * med] if med > 0 else pts


def build(hd_dir, masks_dir, min_points: int = 30, iou_min: float = 0.25) -> list:
    """每个掩码拟一个框（点少于 min_points 的跳过），多帧按类别和 3D IoU 合并，补上 n_views。"""
    from PIL import Image
    hd_dir, masks_dir = Path(hd_dir), Path(masks_dir)
    cams = hd.load(hd_dir)
    by_frame = {int(f["source_frame"]): f for f in cams["frames"]}
    dets = []
    for k, m in enumerate(json.loads((masks_dir / "index.json").read_text())):
        f = by_frame[int(m["frame"])]
        depth = np.load(hd_dir / "depth" / f"{int(m['frame']):06d}.npy")
        mask = np.asarray(Image.open(masks_dir / m["mask"])) > 0
        pts = points_from_mask(mask, depth, f["K"], f["c2w"])
        if len(pts) < min_points:
            continue
        r = boxes.fit_obb(pts, object_id=f"d{k}", category=m["label"], source="clean")
        r.update(confidence=float(m["score"]), score=float(m["score"]), frame=int(m["frame"]),
                 bbox2d_xyxy=m.get("box_xyxy"), mask_px=int(mask.sum()))
        dets.append(r)
    items = inventory.fuse(dets, iou_min=iou_min)
    for it in items:
        it["n_views"] = hd.best_view(it, cams)[2]
    return items
