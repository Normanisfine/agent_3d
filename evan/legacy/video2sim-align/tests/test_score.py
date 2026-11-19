"""Runbook 6.2 unit tests for eval/score.py, plus one alignment test."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'eval'))
from v2s import boxes  # noqa: E402
import score  # noqa: E402

GT = [boxes.record('sofa', 'sofa', [0.7, 3.2, -0.1], 0.3, [2.3, 1.0, 0.8]),
      boxes.record('table', 'table', [1.9, 2.8, -0.4], 0.0, [1.2, 0.5, 0.4]),
      boxes.record('chair_a', 'chair', [-1.4, 3.1, 0.0], 1.2, [0.5, 0.5, 1.0]),
      boxes.record('chair_b', 'chair', [-0.7, 2.3, 0.0], -0.4, [0.5, 0.5, 1.0]),
      boxes.record('cabinet', 'cabinet', [3.4, 1.1, 0.6], 1.57, [1.0, 0.6, 2.2])]


class ScoreTests(unittest.TestCase):
    def test_gt_vs_gt_is_perfect(self):
        r = score.score(GT, GT)
        self.assertEqual(r['f1@0.5'], 1.0)
        self.assertEqual(r['f1@1.0'], 1.0)
        self.assertAlmostEqual(r['size_log_ratio_median'], 0.0)
        self.assertAlmostEqual(r['yaw_err_deg_median'], 0.0)

    def test_shift_03m_still_matches(self):
        shifted = [boxes.transform(g, 0.0, [0.3, 0.0, 0.0]) for g in GT]
        r = score.score(shifted, GT)
        self.assertEqual(r['f1@0.5'], 1.0)
        self.assertEqual({p['pred'] for p in r['pairs@0.5']}, {g['object_id'] for g in GT})
        self.assertTrue(all(p['pred'] == p['gt'] for p in r['pairs@0.5']))

    def test_scale_12_gives_log_ratio_018(self):
        bigger = [dict(g, size=(1.2 * np.asarray(g['size'])).tolist()) for g in GT]
        r = score.score(bigger, GT)
        self.assertAlmostEqual(r['size_log_ratio_median'], np.log(1.2), places=6)
        self.assertAlmostEqual(r['size_log_ratio_median'], 0.18, places=2)

    def test_delete_one_lowers_recall(self):
        full = score.score(GT, GT)
        r = score.score(GT[1:], GT)
        self.assertLess(r['recall@0.5'], full['recall@0.5'])
        self.assertEqual(r['missed_not_detected'], full['missed_not_detected'] + 1)

    def test_camera_alignment_undoes_global_rigid_motion(self):
        rng = np.random.default_rng(0)
        cams_gt = rng.uniform(-2, 2, (32, 3)) + [0, 0, 1.5]
        yaw, t = 0.9, np.array([4.0, -2.0, 0.7])
        moved = [boxes.transform(g, yaw, t) for g in GT]
        cams_pred = cams_gt @ boxes.rot_z(yaw).T + t
        al = score.align_gravity(cams_pred, cams_gt)
        back = [boxes.transform(p, al['yaw'], al['translation'], al['scale']) for p in moved]
        r = score.score(back, GT)
        self.assertEqual(r['f1@0.5'], 1.0)
        self.assertLess(r['center_err_m_median'], 1e-6)
        al3 = score.align_gravity(cams_pred * 0.8, cams_gt, with_scale=True)
        self.assertAlmostEqual(al3['scale'], 1 / 0.8, places=6)


if __name__ == '__main__':
    unittest.main()
