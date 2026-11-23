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


def build(hd_dir, masks_dir, min_points: int = 30, iou_min: float = 0.25, depth_name: str = "depth",
          min_frames_tile: int = 1, keep=None) -> list:
    """每个掩码拟一个框（点少于 min_points 的跳过），多帧按类别和 3D IoU 合并，补上 n_views。
    清单 v2：depth_name="depth_moge" 用对齐到 Pi3X 尺度的 MoGe-2 深度；min_frames_tile=2 时，只在放大窗口里
    检测到（index 的 source 都是 tile）的物体要合并了 ≥ 2 帧才收。keep：只用 keep(index 条目) 为真的掩码（消融用）。"""
    from PIL import Image
    hd_dir, masks_dir = Path(hd_dir), Path(masks_dir)
    cams = hd.load(hd_dir)
    by_frame = {int(f["source_frame"]): f for f in cams["frames"]}
    dets = []
    for k, m in enumerate(json.loads((masks_dir / "index.json").read_text())):
        if keep is not None and not keep(m):
            continue
        f = by_frame[int(m["frame"])]
        depth = np.load(hd_dir / depth_name / f"{int(m['frame']):06d}.npy")
        mask = np.asarray(Image.open(masks_dir / m["mask"])) > 0
        pts = points_from_mask(mask, depth, f["K"], f["c2w"])
        if len(pts) < min_points:
            continue
        r = boxes.fit_obb(pts, object_id=f"d{k}", category=m["label"], source="clean")
        r.update(confidence=float(m["score"]), score=float(m["score"]), frame=int(m["frame"]),
                 bbox2d_xyxy=m.get("box_xyxy"), mask_px=int(mask.sum()), det_source=m.get("source", "full"))
        dets.append(r)
    items = inventory.fuse(dets, iou_min=iou_min)
    items = [it for it in items if it["det_sources"] != ["tile"] or it["n_frames"] >= min_frames_tile]
    for it in items:
        it["n_views"] = hd.best_view(it, cams)[2]
    return items


def build_v2(scene_id: str, root: Path = None, tiles: bool = True, open_vocab: bool = True,
             depth_name: str = "depth_moge", post: bool = True, min_frames_tile: int = 2) -> list:
    """清单 v2（借 SceneRig，docs/plans/2026-10-29-scenerig-detection.md）：perception/<id>/sam3_objects_v2/ 的掩码
    （整帧 + 3×3 放大窗口，固定类别表 + 开放词表）→ 反投影拟框、多帧合并 → 同类同尺寸 → 贴支撑面。
    关掉某一项就是对应的消融：tiles=False 只用整帧检测，open_vocab=False 只用固定类别表，
    depth_name="depth" 用 Pi3X 上采样深度，post=False 不做同尺寸和贴支撑面。"""
    from smallobj import settle
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    P = root / "perception" / scene_id
    fixed = set(json.loads((root / "configs" / "inventory_labels.json").read_text())["labels"])

    def keep(m):
        return (tiles or m.get("source", "full") == "full") and (open_vocab or m["label"] in fixed)
    items = build(P / "hd", P / "sam3_objects_v2", depth_name=depth_name,
                  min_frames_tile=min_frames_tile if tiles else 1, keep=keep)
    return settle.settle(settle.same_size(items)) if post else items
