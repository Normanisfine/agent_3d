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
