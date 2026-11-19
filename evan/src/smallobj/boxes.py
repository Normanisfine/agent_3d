"""Object records (runbook section 3.4): one JSON object per furniture item.

{"object_id", "category", "center": [x, y, z], "yaw": rad, "size": [l, w, h],
 "confidence", "source"}

Metres, world z up. `size` is length/width/height in the object's own frame:
l along the yaw direction, w perpendicular to it in the floor plane, h vertical.
"""
import json
from pathlib import Path

import numpy as np


def record(object_id, category, center, yaw, size, confidence=1.0, source='gt'):
    return {'object_id': str(object_id), 'category': str(category),
            'center': [float(v) for v in center], 'yaw': float(wrap(yaw)),
            'size': [float(v) for v in size], 'confidence': float(confidence), 'source': source}


def is_shell(rec, max_thickness, min_length):
    """薄壳件：最薄的一边 < max_thickness 且最长的一边 ≥ min_length（踢脚线、墙板、大地毯这类）。
    真值和预测都用这一条去掉，保证两边对称。"""
    return min(rec['size']) < max_thickness and max(rec['size']) >= min_length


def wrap(angle):
    """Wrap to [-pi, pi)."""
    return (float(angle) + np.pi) % (2 * np.pi) - np.pi


def rot_z(yaw):
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def corners(rec):
    """8 x 3 corners; bottom face first (0-3), then top face (4-7), counter-clockwise."""
    l, w, h = np.asarray(rec['size']) / 2
    local = np.array([[l, w, -h], [-l, w, -h], [-l, -w, -h], [l, -w, -h],
                      [l, w, h], [-l, w, h], [-l, -w, h], [l, -w, h]])
    return local @ rot_z(rec['yaw']).T + np.asarray(rec['center'])


EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
         (0, 4), (1, 5), (2, 6), (3, 7)]


def to_local(rec, points):
    """World points -> box frame (box centre at origin, axes l, w, h)."""
    return (np.asarray(points) - np.asarray(rec['center'])) @ rot_z(rec['yaw'])


def contains(rec, points, margin=0.0):
    half = np.asarray(rec['size']) / 2 + margin
    return np.all(np.abs(to_local(rec, points)) <= half, axis=1)


def transform(rec, yaw, translation, scale=1.0, source=None):
    """Apply x -> scale * Rz(yaw) x + translation to a record."""
    out = dict(rec)
    out['center'] = (scale * rot_z(yaw) @ np.asarray(rec['center']) + np.asarray(translation)).tolist()
    out['yaw'] = wrap(rec['yaw'] + yaw)
    out['size'] = (scale * np.asarray(rec['size'])).tolist()
    if source:
        out['source'] = source
    return out


def from_obb(object_id, category, centroid, axes_lengths, normalized_axes, source='gt'):
    """ARKitScenes obbAligned (rows of normalizedAxes are the box axes) -> record."""
    rows = np.asarray(normalized_axes, float).reshape(3, 3)
    lengths = np.asarray(axes_lengths, float)
    v = int(np.argmax(np.abs(rows[:, 2])))
    if abs(rows[v, 2]) < 0.95:
        raise ValueError(f'{object_id}: box is not gravity aligned ({rows[v, 2]:.3f})')
    a, b = [i for i in range(3) if i != v]
    yaw = np.arctan2(rows[a, 1], rows[a, 0])
    return record(object_id, category, centroid, yaw, [lengths[a], lengths[b], lengths[v]], 1.0, source)


def save(records, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(records, indent=1) + '\n')


def load(path):
    return json.loads(Path(path).read_text())


def min_area_rect(xy):
    """凸包每条边的方向各试一次，取外包矩形面积最小的。返回 (yaw, 长, 宽, 中心 xy)。"""
    try:
        from scipy.spatial import ConvexHull
        hull = xy[ConvexHull(xy).vertices]
    except Exception:  # 共线、点太少：退回坐标轴对齐
        hull = xy
    best = None
    for i in range(len(hull)):
        d = hull[(i + 1) % len(hull)] - hull[i]
        if np.allclose(d, 0):
            continue
        yaw = float(np.arctan2(d[1], d[0]))
        local = xy @ rot_z(yaw)[:2, :2]
        lo, hi = local.min(0), local.max(0)
        area = float(np.prod(hi - lo))
        if best is None or area < best[0] - 1e-12:
            best = (area, yaw, lo, hi)
    if best is None:
        lo, hi = xy.min(0), xy.max(0)
        best = (0.0, 0.0, lo, hi)
    _, yaw, lo, hi = best
    mid_local = (lo + hi) / 2
    mid = rot_z(yaw)[:2, :2] @ mid_local
    return yaw, float(hi[0] - lo[0]), float(hi[1] - lo[1]), mid


def fit_obb(points, object_id="obb", category="object", source="fit", min_thickness=0.01):
    """一团点的重力对齐有向框：水平面上取最小面积外包矩形，竖直方向取 z 的范围；每边至少 min_thickness。"""
    pts = np.asarray(points, float)
    yaw, l, w, mid = min_area_rect(pts[:, :2])
    z0, z1 = pts[:, 2].min(), pts[:, 2].max()
    size = [max(v, min_thickness) for v in (l, w, z1 - z0)]
    return record(object_id, category, (mid[0], mid[1], (z0 + z1) / 2), yaw, size, source=source)
