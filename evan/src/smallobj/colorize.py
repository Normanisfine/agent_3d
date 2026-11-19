"""给白膜场景上色：把每个零件表面的采样点投到高清帧上，深度对得上（没被挡住）的像素取中位数当它的颜色。

AHa-3D 搭出来的场景全是灰色材质（clay、soft、inset、glass、floor），颜色只能从视频里取。
零件自己取不到颜色（被挡住、或摆的位置和视频对不上）时，用同一个根节点下所有零件的颜色；还没有就不给（渲染时留灰）。
"""
import numpy as np


def sample_surface(tris: np.ndarray, n: int, seed: int = 0) -> np.ndarray:
    """三角形 (T, 3, 3) 上按面积均匀撒 n 个点。"""
    tris = np.asarray(tris, float)
    rng = np.random.default_rng(seed)
    area = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    if len(tris) == 0 or area.sum() <= 0:
        return np.zeros((0, 3))
    k = rng.choice(len(tris), size=n, p=area / area.sum())
    r1, r2 = np.sqrt(rng.random(n))[:, None], rng.random(n)[:, None]
    a, b, c = tris[k, 0], tris[k, 1], tris[k, 2]
    return (1 - r1) * a + r1 * (1 - r2) * b + r1 * r2 * c


def srgb_to_linear(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def object_colors(points: dict, root_of: dict, views, min_samples: int = 20,
                  tol_abs: float = 0.10, tol_rel: float = 0.05) -> dict:
    """points：{零件名: (N, 3) 世界坐标点}；root_of：{零件名: 根节点名}；views：[(相机 {K, c2w}, RGB 图 uint8, 深度图（米，NaN = 无效）)]。

    一个点算"看得到"：投在画面内、在相机前面、深度图在那个像素有效，且和点的深度相差不超过 max(tol_abs, tol_rel × 深度)。
    返回 {零件名: {"rgb": sRGB 0–1 的中位数, "n": 样本数, "source": "own" 或 "root"}}；样本不到 min_samples 的零件不出现。
    """
    names = [k for k, v in points.items() if len(v)]
    if not names:
        return {}
    allp = np.concatenate([np.asarray(points[k], float) for k in names])
    owner = np.concatenate([np.full(len(points[k]), i) for i, k in enumerate(names)])
    samples = [[] for _ in names]
    for cam, img, depth in views:
        K = np.asarray(cam["K"], float)
        w2c = np.linalg.inv(np.asarray(cam["c2w"], float))
        pc = allp @ w2c[:3, :3].T + w2c[:3, 3]
        z = pc[:, 2]
        front = z > 0.05
        u = np.full(len(z), -1)
        v = np.full(len(z), -1)
        u[front] = np.floor(pc[front, 0] / z[front] * K[0, 0] + K[0, 2]).astype(int)
        v[front] = np.floor(pc[front, 1] / z[front] * K[1, 1] + K[1, 2]).astype(int)
        H, W = depth.shape
        ok = front & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        idx = np.nonzero(ok)[0]
        d = depth[v[idx], u[idx]]
        keep = np.isfinite(d) & (np.abs(z[idx] - d) <= np.maximum(tol_abs, tol_rel * z[idx]))
        idx = idx[keep]
        rgb = img[v[idx], u[idx], :3]
        for i in np.unique(owner[idx]):
            samples[i].append(rgb[owner[idx] == i])
    own = {k: np.concatenate(s) for k, s in zip(names, samples) if s}
    by_root = {}
    for k, s in own.items():
        by_root.setdefault(root_of.get(k, k), []).append(s)
    by_root = {r: np.concatenate(s) for r, s in by_root.items()}
    out = {}
    for k in points:
        s, src = own.get(k), "own"
        if s is None or len(s) < min_samples:
            s, src = by_root.get(root_of.get(k, k)), "root"
        if s is not None and len(s) >= min_samples:
            out[k] = {"rgb": (np.median(s, axis=0) / 255.0).tolist(), "n": int(len(s)), "source": src}
    return out
