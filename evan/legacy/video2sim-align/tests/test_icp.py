"""ICP aligner on synthetic box-surface points (visible faces only)."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2s import boxes  # noqa: E402
from aligners import icp  # noqa: E402


def surface_points(rec, n=1500, faces=('+x', '-y', '+z'), noise=0.005, seed=0):
    rng = np.random.default_rng(seed)
    half = np.asarray(rec['size']) / 2
    pts = []
    for f in faces:
        axis = 'xyz'.index(f[1])
        p = rng.uniform(-half, half, (n // len(faces), 3))
        p[:, axis] = half[axis] * (1 if f[0] == '+' else -1)
        pts.append(p)
    local = np.concatenate(pts) + rng.normal(0, noise, (n // len(faces) * len(faces), 3))
    return local @ boxes.rot_z(rec['yaw']).T + np.asarray(rec['center'])


class ICPTests(unittest.TestCase):
    def setUp(self):
        self.gt = boxes.record('table', 'table', [1.0, 2.0, 0.4], 0.4, [1.2, 0.6, 0.8])
        self.pts = surface_points(self.gt)

    def test_identity_stays(self):
        out, info = icp.align(self.gt, self.pts)
        self.assertLess(np.linalg.norm(np.subtract(out['center'], self.gt['center'])), 0.01)
        self.assertGreater(info['inlier_fraction_3cm'], 0.95)

    def test_recovers_moderate_perturbation(self):
        start = boxes.transform(self.gt, 0.0, [0.0, 0.0, 0.0])
        start['center'] = (np.asarray(self.gt['center']) + [0.15, -0.10, 0.05]).tolist()
        start['yaw'] = self.gt['yaw'] + np.radians(12)
        out, _ = icp.align(start, self.pts)
        self.assertLess(np.linalg.norm(np.subtract(out['center'], self.gt['center'])), 0.03)
        self.assertLess(abs(np.degrees(boxes.wrap(out['yaw'] - self.gt['yaw']))), 2.0)

    def test_size_unchanged(self):
        start = dict(self.gt, center=(np.asarray(self.gt['center']) + 0.1).tolist())
        out, _ = icp.align(start, self.pts)
        self.assertEqual(out['size'], self.gt['size'])


if __name__ == '__main__':
    unittest.main()
