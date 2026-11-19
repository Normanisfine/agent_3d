"""Score reconstructed furniture against ground-truth boxes (runbook section 6).

1. Align: move the prediction into the GT world using camera centres of the same
   frames. Main table: rotation about z + translation, scale fixed at 1 (both
   worlds are z-up), so the predicted-scale error stays in the score. Secondary:
   the same plus one global scale (Sim(3) with gravity).
2. Match: Hungarian assignment on centre distance (+ a small size term); pairs
   farther apart than the threshold are not allowed. Class-agnostic by default.
3. Metrics: F1 at 0.5 m and 1.0 m; median size log-ratio of matched pairs;
   recall, with misses split into "not detected" (no match even at 1.0 m) and
   "misaligned" (matched at 1.0 m but not at 0.5 m); median yaw error with
   box symmetry; optional dollars per room.

Writes one CSV row per call.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2s import boxes  # noqa: E402

THRESHOLDS = (0.5, 1.0)


def align_gravity(src, dst, with_scale=False):
    """Least-squares x_dst ~ s Rz(theta) x_src + t over corresponding points (N x 3)."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    ms, md = src.mean(0), dst.mean(0)
    a, b = src - ms, dst - md
    # 2D Procrustes in the floor plane: maximise sum of dot products after rotation.
    num = np.sum(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])
    den = np.sum(a[:, 0] * b[:, 0] + a[:, 1] * b[:, 1])
    theta = np.arctan2(num, den)
    R = boxes.rot_z(theta)
    ra = a @ R.T
    s = float(np.sum(ra * b) / np.sum(ra * ra)) if with_scale else 1.0
    t = md - s * R @ ms
    resid = np.linalg.norm(s * src @ R.T + t - dst, axis=1)
    return {'yaw': float(theta), 'scale': s, 'translation': t.tolist(),
            'rmse_m': float(np.sqrt(np.mean(resid ** 2))), 'log_scale': float(np.log(s))}


def size_log_ratio(pred, gt):
    """Mean log ratio over (sorted horizontal dims, height); 1.2x everywhere -> log 1.2."""
    p = np.r_[np.sort(pred['size'][:2]), pred['size'][2]]
    g = np.r_[np.sort(gt['size'][:2]), gt['size'][2]]
    return float(np.mean(np.log(np.maximum(p, 1e-6) / np.maximum(g, 1e-6))))


def yaw_error_deg(pred, gt, square_tol=0.1):
    """Boxes look the same after 180 deg; near-square ones also after 90 deg."""
    period = np.pi
    l, w = gt['size'][:2]
    if abs(np.log(max(l, 1e-6) / max(w, 1e-6))) < square_tol:
        period = np.pi / 2
    d = (pred['yaw'] - gt['yaw']) % period
    return float(np.degrees(min(d, period - d)))


def match(preds, gts, threshold, class_aware=False):
    if not preds or not gts:
        return []
    P = np.array([p['center'] for p in preds])
    G = np.array([g['center'] for g in gts])
    dist = np.linalg.norm(P[:, None] - G[None], axis=2)
    size = np.array([[abs(size_log_ratio(p, g)) for g in gts] for p in preds])
    cost = dist + 0.1 * size
    big = 1e6
    cost[dist > threshold] = big
    if class_aware:
        same = np.array([[p['category'] == g['category'] for g in gts] for p in preds])
        cost[~same] = big
    rows, cols = linear_sum_assignment(cost)
    return [(int(r), int(c), float(dist[r, c])) for r, c in zip(rows, cols) if cost[r, c] < big]


def score(preds, gts, *, class_aware=False, dollars=None):
    out = {'n_pred': len(preds), 'n_gt': len(gts)}
    matches = {}
    for thr in THRESHOLDS:
        m = match(preds, gts, thr, class_aware)
        matches[thr] = m
        tp = len(m)
        prec = tp / len(preds) if preds else 0.0
        rec = tp / len(gts) if gts else 0.0
        out[f'f1@{thr}'] = 2 * prec * rec / (prec + rec) if tp else 0.0
        out[f'precision@{thr}'] = prec
        out[f'recall@{thr}'] = rec
    m = matches[0.5]
    out['size_log_ratio_median'] = float(np.median([size_log_ratio(preds[r], gts[c]) for r, c, _ in m])) if m else None
    out['yaw_err_deg_median'] = float(np.median([yaw_error_deg(preds[r], gts[c]) for r, c, _ in m])) if m else None
    out['center_err_m_median'] = float(np.median([d for _, _, d in m])) if m else None
    hit05 = {c for _, c, _ in matches[0.5]}
    hit10 = {c for _, c, _ in matches[1.0]}
    out['missed_not_detected'] = sum(1 for i in range(len(gts)) if i not in hit10)
    out['missed_misaligned'] = sum(1 for i in range(len(gts)) if i in hit10 and i not in hit05)
    out['dollars'] = dollars
    out['pairs@0.5'] = [{'pred': preds[r]['object_id'], 'gt': gts[c]['object_id'], 'dist_m': round(d, 3)}
                        for r, c, d in m]
    return out


def run(pred_path, gt_path, pred_cams=None, gt_cams=None, *, mode='rigid', class_aware=False, dollars=None):
    preds, gts = boxes.load(pred_path), boxes.load(gt_path)
    align = {'yaw': 0.0, 'scale': 1.0, 'translation': [0, 0, 0], 'rmse_m': None, 'log_scale': 0.0}
    if mode != 'none':
        align = align_gravity(pred_cams, gt_cams, with_scale=(mode == 'sim3'))
        preds = [boxes.transform(p, align['yaw'], align['translation'], align['scale']) for p in preds]
    res = score(preds, gts, class_aware=class_aware, dollars=dollars)
    res.update({'align_mode': mode, 'class_aware': class_aware, 'align_rmse_m': align['rmse_m'],
                'align_scale': align['scale']})
    return res, preds


CSV_FIELDS = ['run', 'pred', 'align_mode', 'class_aware', 'n_pred', 'n_gt', 'f1@0.5', 'f1@1.0',
              'precision@0.5', 'recall@0.5', 'recall@1.0', 'center_err_m_median', 'size_log_ratio_median',
              'yaw_err_deg_median', 'missed_not_detected', 'missed_misaligned', 'align_rmse_m',
              'align_scale', 'dollars']


def append_csv(path, run_name, pred_path, res):
    path = Path(path)
    new = not path.exists()
    with path.open('a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
        if new:
            w.writeheader()
        row = dict(res, run=run_name, pred=str(pred_path))
        w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items() if k in CSV_FIELDS})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pred', type=Path)
    ap.add_argument('gt', type=Path)
    ap.add_argument('--cams', type=Path, help='JSON {"pred": [[x,y,z],...], "gt": [[x,y,z],...]} same frames')
    ap.add_argument('--mode', choices=['rigid', 'sim3', 'none'], default='rigid')
    ap.add_argument('--class-aware', action='store_true')
    ap.add_argument('--dollars', type=float)
    ap.add_argument('--csv', type=Path)
    ap.add_argument('--run', default='')
    a = ap.parse_args()
    cams = json.loads(a.cams.read_text()) if a.cams else {}
    res, _ = run(a.pred, a.gt, cams.get('pred'), cams.get('gt'), mode=a.mode, class_aware=a.class_aware,
                 dollars=a.dollars)
    if a.csv:
        append_csv(a.csv, a.run, a.pred, res)
    print(json.dumps({k: v for k, v in res.items() if k != 'pairs@0.5'}, indent=1))


if __name__ == '__main__':
    main()
