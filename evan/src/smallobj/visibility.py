"""漏斗第 ① 关"看得见"：真值框投影到流程实际用到的帧上，用激光深度判断遮挡，数可见像素。

剪影 = 8 个角投影后的凸包（所有角都在相机前方时）。像素 (u, v) 被挡住的判据：激光深度图在这条视线上
比框最近的点还近 5 cm 以上。深度为 0（激光没扫到）按可见算。
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from smallobj import boxes, ca1m

OCCLUSION_MARGIN_M = 0.05


def scale_K(K, from_wh, to_wh):
    K = np.asarray(K, float).copy()
    K[0] *= to_wh[0] / from_wh[0]
    K[1] *= to_wh[1] / from_wh[1]
    return K


def visible_pixels(box, c2w, K, wh, depth=None, depth_K=None):
    corners = boxes.corners(box)
    uv, z = ca1m.project(corners, np.asarray(c2w, float), np.asarray(K, float))
    if np.any(z <= 0.05):  # 有角在相机后面：小物体基本是出画了，按看不见算
        return 0
    from scipy.spatial import ConvexHull
    try:
        hull = uv[ConvexHull(uv).vertices]
    except Exception:
        return 0
    w, h = wh
    mask_img = Image.new("1", (w, h), 0)
    ImageDraw.Draw(mask_img).polygon([tuple(p) for p in hull], fill=1)
    mask = np.asarray(mask_img, bool)
    if depth is None:
        return int(mask.sum())
    vs, us = np.nonzero(mask)
    if us.size == 0:
        return 0
    rays = np.linalg.inv(np.asarray(K, float)) @ np.vstack([us + 0.5, vs + 0.5, np.ones_like(us)])
    pd = np.asarray(depth_K, float) @ rays
    ud = np.clip((pd[0] / pd[2]).astype(int), 0, depth.shape[1] - 1)
    vd = np.clip((pd[1] / pd[2]).astype(int), 0, depth.shape[0] - 1)
    d = depth[vd, ud]
    z_near = float(z.min())
    visible = (d == 0) | (d >= z_near - OCCLUSION_MARGIN_M)
    return int(visible.sum())


def visible_flags(gts, scene_dir, bundle_dir, wh, min_px):
    """每个真值物体：在流程用到的那几帧里（按 wh 分辨率），最多能看到多少像素、是否 ≥ min_px。

    帧集合来自 bundle 的 alignment/cameras.json（source_frame → frame_map 时间戳）；位姿、内参、深度用 CA-1M 真值。
    返回 {gt_id: {"max_px": int, "visible": bool}}。
    """
    scene_dir, bundle_dir = Path(scene_dir), Path(bundle_dir)
    frames = json.loads((bundle_dir / "alignment" / "cameras.json").read_text())["frames"]
    stamps = json.loads((scene_dir / "frame_map.json").read_text())["timestamps_ns"]
    track = ca1m.camera_track(scene_dir)
    best = {g["object_id"]: 0 for g in gts}
    for f in frames:
        s = stamps[int(f["source_frame"])]
        fdir = scene_dir / "frames" / str(s)
        img_wh = Image.open(fdir / "image.png").size
        K = scale_K(json.loads((fdir / "K.json").read_text()), img_wh, wh)
        depth = np.asarray(Image.open(fdir / "depth.png"), float) / 1000.0
        dK = np.asarray(json.loads((fdir / "depth_K.json").read_text()), float)
        for g in gts:
            px = visible_pixels(g, track[s], K, wh, depth=depth, depth_K=dK)
            if px > best[g["object_id"]]:
                best[g["object_id"]] = px
    return {k: {"max_px": v, "visible": v >= min_px} for k, v in best.items()}
