"""剪影：把网格表面采样点投到图上再膨胀、填洞，代替可微渲染（不用 nvdiffrast，免得在 sm_120 上编译）。"""
import numpy as np


def project(points_world, K, c2w):
    """世界点 → 像素 (u, v) 和相机深度 z。"""
    K, c2w = np.asarray(K, float), np.asarray(c2w, float)
    w2c = np.linalg.inv(c2w)
    cam = np.asarray(points_world, float) @ w2c[:3, :3].T + w2c[:3, 3]
    z = cam[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        uv = cam[:, :2] / z[:, None] * [K[0, 0], K[1, 1]] + [K[0, 2], K[1, 2]]
    return uv, z


def render_mask(points_world, K, c2w, size_wh, dilate_px: int = 2, roi=None) -> np.ndarray:
    """投影点 → 像素格 → 膨胀 dilate_px → 填洞。roi=(x0, y0, x1, y1) 时只画这一块（返回 roi 大小的数组）。"""
    from scipy.ndimage import binary_dilation, binary_fill_holes
    W, H = size_wh
    x0, y0, x1, y1 = roi if roi is not None else (0, 0, W, H)
    uv, z = project(points_world, K, c2w)
    ok = z > 0.01
    u = np.floor(uv[ok, 0]).astype(int) - x0
    v = np.floor(uv[ok, 1]).astype(int) - y0
    inside = (u >= 0) & (u < x1 - x0) & (v >= 0) & (v < y1 - y0)
    m = np.zeros((y1 - y0, x1 - x0), bool)
    m[v[inside], u[inside]] = True
    if dilate_px > 0:
        m = binary_dilation(m, iterations=dilate_px)
    return binary_fill_holes(m)


def outside_fraction(points_world, K, c2w, roi) -> float:
    """投影落在 roi 外（或在相机后面）的点所占比例。"""
    uv, z = project(points_world, K, c2w)
    x0, y0, x1, y1 = roi
    ins = (z > 0.01) & (uv[:, 0] >= x0) & (uv[:, 0] < x1) & (uv[:, 1] >= y0) & (uv[:, 1] < y1)
    return float(1.0 - ins.mean()) if len(ins) else 1.0


def iou(a, b) -> float:
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0
