"""ICP aligner (runbook 7.1): fit a box's pose to an object's points; size is not changed.

Only position (x, y, z) and yaw about the vertical axis move. The residual of each
point is its signed distance to the box surface, which equals the point-to-plane
distance near a face. Robust Gauss-Newton with Huber weights; Open3D's
registration_icp cannot restrict rotation to yaw, so this is a small custom solver.
It is meant as the weakest baseline, not a tuned method.
"""
import numpy as np

from v2s import boxes


def box_sdf(local, half):
    """Signed distance of box-frame points to an axis-aligned box with half extents `half`."""
    q = np.abs(local) - half
    outside = np.linalg.norm(np.maximum(q, 0.0), axis=1)
    inside = np.minimum(q.max(axis=1), 0.0)
    return outside + inside


def _residuals(params, base, points, half):
    rec = boxes.transform(base, 0.0, [0, 0, 0])
    rec['center'] = (np.asarray(base['center']) + params[:3]).tolist()
    rec['yaw'] = base['yaw'] + params[3]
    return box_sdf(boxes.to_local(rec, points), half)


def align(init, points, iters=40, huber=0.03, max_points=3000, seed=0, tol=1e-5):
    """Return (refined record, info). `points`: N x 3 in the same world as `init`."""
    pts = np.asarray(points, float)
    if len(pts) > max_points:
        pts = pts[np.random.default_rng(seed).choice(len(pts), max_points, replace=False)]
    half = np.asarray(init['size']) / 2
    params = np.zeros(4)
    eps = np.array([1e-4, 1e-4, 1e-4, 1e-4])
    r = _residuals(params, init, pts, half)
    start_cost = float(np.mean(np.minimum(np.abs(r), 0.1)))
    for it in range(iters):
        J = np.empty((len(pts), 4))
        for k in range(4):
            d = np.zeros(4)
            d[k] = eps[k]
            J[:, k] = (_residuals(params + d, init, pts, half) - _residuals(params - d, init, pts, half)) / (2 * eps[k])
        a = np.abs(r)
        w = np.where(a <= huber, 1.0, huber / np.maximum(a, 1e-12))
        H = J.T @ (J * w[:, None]) + 1e-6 * np.eye(4)
        step = -np.linalg.solve(H, J.T @ (w * r))
        step[3] = np.clip(step[3], -0.2, 0.2)
        step[:3] = np.clip(step[:3], -0.2, 0.2)
        params = params + step
        r = _residuals(params, init, pts, half)
        if np.linalg.norm(step) < tol:
            break
    out = dict(init)
    out['center'] = (np.asarray(init['center']) + params[:3]).tolist()
    out['yaw'] = boxes.wrap(init['yaw'] + params[3])
    out['source'] = 'icp'
    inlier = float(np.mean(np.abs(r) < 0.03))
    out['confidence'] = inlier
    info = {'iterations': it + 1, 'delta_center_m': params[:3].tolist(), 'delta_yaw_deg': float(np.degrees(params[3])),
            'inlier_fraction_3cm': inlier, 'median_abs_residual_m': float(np.median(np.abs(r))),
            'start_cost': start_cost, 'end_cost': float(np.mean(np.minimum(np.abs(r), 0.1))), 'n_points': len(pts)}
    return out, info
