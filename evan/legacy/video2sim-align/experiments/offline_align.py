"""Mini offline aligner test (runbook 7.4, one scene): perturb each GT box, let the aligner fix it.

Observation = points near the GT box (box grown by 10 cm sideways/up, floor excluded),
from two sources in the GT (ARKit) world:
  lidar - fused ARKit LiDAR depth;
  pi3x  - Pi3X points of the 32 reference frames, moved into the GT world with the
          camera-centre rigid alignment (scale 1), so Pi3X's scale error stays in.
Perturbation: horizontal shift 5-60 cm in a random direction, vertical +-5 cm, yaw 5-90 deg.
Size is not perturbed because ICP does not change size; success = centre error < 0.1 m
and symmetric yaw error < 10 deg.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'eval'))
from v2s import arkit, boxes  # noqa: E402
from aligners import icp  # noqa: E402
from perception.lift import load_reference  # noqa: E402
import score  # noqa: E402


def observation(cloud, gt, margin=0.10, floor_gap=0.03):
    local = boxes.to_local(gt, cloud)
    half = np.asarray(gt['size']) / 2
    keep = (np.abs(local[:, 0]) <= half[0] + margin) & (np.abs(local[:, 1]) <= half[1] + margin)
    keep &= (local[:, 2] >= -half[2] + floor_gap) & (local[:, 2] <= half[2] + margin)
    return cloud[keep]


def perturb(gt, rng):
    ang = rng.uniform(0, 2 * np.pi)
    mag = rng.uniform(0.05, 0.60)
    shift = [mag * np.cos(ang), mag * np.sin(ang), rng.uniform(-0.05, 0.05)]
    dyaw = np.radians(rng.uniform(5, 90)) * rng.choice([-1, 1])
    out = dict(gt, source='perturbed')
    out['center'] = (np.asarray(gt['center']) + shift).tolist()
    out['yaw'] = boxes.wrap(gt['yaw'] + dyaw)
    return out, mag, abs(np.degrees(dyaw))


def ok(rec, gt):
    return bool(np.linalg.norm(np.subtract(rec["center"], gt["center"])) < 0.10
            and score.yaw_error_deg(rec, gt) < 10.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', type=Path, required=True)
    ap.add_argument('--raw', type=Path, required=True)
    ap.add_argument('--reference', type=Path, required=True)
    ap.add_argument('--cams', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--trials', type=int, default=10)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    gts = boxes.load(a.scene / 'gt_boxes.json')

    lidar = arkit.lidar_cloud(a.raw)
    ref = load_reference(a.reference)
    cams = json.loads(a.cams.read_text())
    al = score.align_gravity(cams['pred'], cams['gt'])
    keep = ref['conf'] >= np.percentile(ref['conf'], 20)
    pi3 = ref['points'][keep]
    R = boxes.rot_z(al['yaw'])
    pi3 = pi3 @ R.T + np.asarray(al['translation'])
    sources = {'lidar': lidar, 'pi3x': pi3}

    rows = []
    rng = np.random.default_rng(0)
    for gt in gts:
        trials = [perturb(gt, rng) for _ in range(a.trials)]
        for src, cloud in sources.items():
            obs = observation(cloud, gt)
            for k, (start, mag, dyaw) in enumerate(trials):
                if len(obs) < 50:
                    rows.append({'object': gt['object_id'], 'source': src, 'trial': k, 'n_obs': len(obs),
                                 'shift_m': mag, 'dyaw_deg': dyaw, 'before_ok': ok(start, gt), 'after_ok': False,
                                 'skipped': True})
                    continue
                out, info = icp.align(start, obs)
                rows.append({'object': gt['object_id'], 'source': src, 'trial': k, 'n_obs': len(obs),
                             'shift_m': mag, 'dyaw_deg': dyaw, 'before_ok': ok(start, gt), 'after_ok': ok(out, gt),
                             'after_center_err_m': float(np.linalg.norm(np.subtract(out['center'], gt['center']))),
                             'after_yaw_err_deg': score.yaw_error_deg(out, gt), 'skipped': False})
    (a.out / 'trials.json').write_text(json.dumps(rows, indent=1) + '\n')

    def rate(sel, key):
        return round(float(np.mean([r[key] for r in sel])), 3) if sel else None
    table = {}
    for src in sources:
        sel = [r for r in rows if r['source'] == src]
        small = [r for r in sel if r['shift_m'] < 0.2 and r['dyaw_deg'] < 30]
        large = [r for r in sel if not (r['shift_m'] < 0.2 and r['dyaw_deg'] < 30)]
        table[src] = {'trials': len(sel), 'skipped_few_points': sum(r['skipped'] for r in sel),
                      'before': rate(sel, 'before_ok'), 'after': rate(sel, 'after_ok'),
                      'small_perturb_after': rate(small, 'after_ok'), 'n_small': len(small),
                      'large_perturb_after': rate(large, 'after_ok'), 'n_large': len(large)}
    table['pi3x_alignment'] = {k: al[k] for k in ('yaw', 'rmse_m')}
    table['lidar_points'] = int(len(lidar))
    (a.out / 'table.json').write_text(json.dumps(table, indent=1) + '\n')
    print(json.dumps(table, indent=1))


if __name__ == '__main__':
    main()
