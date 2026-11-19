"""把流程坐标系对齐到真值坐标系：只用相机轨迹（不用被评测的物体），带重力约束的 Sim(3)。"""
import numpy as np

from smallobj import boxes


def align_sim3(src, dst, gravity=True, with_scale=True):
    """最小二乘 dst ≈ s·R·src + t。gravity=True 时 R 只绕 z 轴转。返回 (s, R, t)。"""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    ms, md = src.mean(0), dst.mean(0)
    a, b = src - ms, dst - md
    if gravity:
        num = np.sum(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])
        den = np.sum(a[:, 0] * b[:, 0] + a[:, 1] * b[:, 1])
        R = boxes.rot_z(np.arctan2(num, den))
    else:  # Umeyama
        U, _, Vt = np.linalg.svd(b.T @ a)
        D = np.diag([1.0, 1.0, np.sign(np.linalg.det(U @ Vt))])
        R = U @ D @ Vt
    ra = a @ R.T
    s = float(np.sum(ra * b) / np.sum(ra * ra)) if with_scale else 1.0
    t = md - s * R @ ms
    return s, R, t


def apply(rec, s, R, t):
    """把一个 boxes.record 变换到真值坐标系（R 只绕 z 轴）。"""
    yaw = float(np.arctan2(R[1, 0], R[0, 0]))
    return boxes.transform(rec, yaw=yaw, translation=t, scale=s)


def pipeline_to_gt(bundle_dir, scene_dir, with_scale=True):
    """流程（AHa-3D 对齐后坐标系）的 32 帧相机中心 → 同一时刻 CA-1M 真值相机中心，求 Sim(3)。

    帧号经 `alignment/cameras.json` 的 source_frame（输入视频帧号）和 `frame_map.json` 的真实时间戳对应。
    返回 {"s", "R", "t", "residual_median_m", "n"}，R、t 是 numpy 数组。
    """
    import json
    from pathlib import Path

    from smallobj import ca1m

    bundle_dir, scene_dir = Path(bundle_dir), Path(scene_dir)
    frames = json.loads((bundle_dir / "alignment" / "cameras.json").read_text())["frames"]
    stamps = json.loads((scene_dir / "frame_map.json").read_text())["timestamps_ns"]
    track = ca1m.camera_track(scene_dir)
    src = np.array([np.asarray(f["c2w"], float)[:3, 3] for f in frames])
    dst = np.array([track[stamps[int(f["source_frame"])]][:3, 3] for f in frames])
    s, R, t = align_sim3(src, dst, gravity=True, with_scale=with_scale)
    resid = np.linalg.norm(s * src @ R.T + t - dst, axis=1)
    return {"s": s, "R": R, "t": t, "residual_median_m": float(np.median(resid)), "n": len(frames)}
