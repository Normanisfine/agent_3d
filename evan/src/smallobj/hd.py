"""高清帧（设计 §8）：Pi3X 用的那 32 帧，从输入视频解码成原尺寸；位姿用 Pi3X 的，深度用 Pi3X 点图上采样。

CA-1M 的真值位姿和激光深度一律不碰；输出放在 `perception/<id>/hd/`，后面的清单、生成、放置工具只读这里。
"""
import json
from pathlib import Path

import numpy as np


def _upsample(z: np.ndarray, valid: np.ndarray, W: int, H: int) -> np.ndarray:
    """双线性上采样；无效像素不参与插值，周围有效权重不到一半的地方记 NaN。

    流程帧是把原图直接拉伸过去的，所以按像素中心对齐：x_proc = (x + 0.5)·w/W − 0.5。
    """
    from scipy.ndimage import map_coordinates
    h, w = z.shape
    ys = (np.arange(H) + 0.5) * h / H - 0.5
    xs = (np.arange(W) + 0.5) * w / W - 0.5
    yy, xx = np.meshgrid(ys, xs, indexing="ij")
    num = map_coordinates(np.where(valid, z, 0.0), [yy, xx], order=1, mode="nearest")
    den = map_coordinates(valid.astype(np.float64), [yy, xx], order=1, mode="nearest")
    out = np.full((H, W), np.nan, np.float32)
    ok = den >= 0.5
    out[ok] = (num[ok] / den[ok]).astype(np.float32)
    return out


def _conf_min(bundle_dir: Path) -> float:
    p = Path(bundle_dir) / "reference_build.json"
    if p.exists():
        return float(json.loads(p.read_text()).get("geometry_representation", {}).get("fusion_confidence_min", 0.1))
    return 0.1


def extract_hd(video: Path, bundle_dir: Path, out_dir: Path) -> dict:
    """写 frames/<source_frame:06d>.png、depth/<source_frame:06d>.npy、cameras.json，返回 cameras.json 的内容。"""
    import imageio.v3 as iio
    from PIL import Image

    bundle_dir, out_dir = Path(bundle_dir), Path(out_dir)
    cams = json.loads((bundle_dir / "alignment" / "cameras.json").read_text())
    w, h = cams["processed_size_wh"]
    pred = np.load(bundle_dir / "pi3x" / "predictions.npz")
    pos = {int(f): i for i, f in enumerate(np.load(bundle_dir / "pi3x" / "inputs.npz")["frame_indices"])}
    conf_min = _conf_min(bundle_dir)
    scale = depth_scale(bundle_dir)
    wanted = {int(f["source_frame"]) for f in cams["frames"]}
    (out_dir / "frames").mkdir(parents=True, exist_ok=True)
    (out_dir / "depth").mkdir(exist_ok=True)
    W = H = None
    for k, img in enumerate(iio.imiter(video)):
        if k in wanted:
            H, W = img.shape[:2]
            Image.fromarray(img[..., :3]).save(out_dir / "frames" / f"{k:06d}.png")
    if W is None:
        raise ValueError(f"{video} 里解码不到 {sorted(wanted)} 这些帧")
    S = np.diag([W / w, H / h, 1.0])
    frames = []
    for f in cams["frames"]:
        s = int(f["source_frame"])
        i = pos[s]
        conf = 1.0 / (1.0 + np.exp(-pred["conf"][i][..., 0]))  # bundle 里存的是原始 logit
        valid = (conf > conf_min) & pred["non_edge"][i]
        z = pred["local_points"][i][..., 2].astype(np.float64) * scale
        np.save(out_dir / "depth" / f"{s:06d}.npy", _upsample(z, valid & np.isfinite(z), W, H))
        frames.append({"source_frame": s, "c2w": f["c2w"], "K": (S @ np.asarray(f["intrinsics"], float)).tolist()})
    out = {"size_wh": [int(W), int(H)], "frames": frames}
    (out_dir / "cameras.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


def depth_scale(bundle_dir: Path) -> float:
    """Pi3X 局部点的单位换到房间世界坐标的倍数（world_transform 的尺度部分；刚体时为 1）。"""
    cams = json.loads((Path(bundle_dir) / "alignment" / "cameras.json").read_text())
    T = np.asarray(cams.get("world_transform", np.eye(4)), float)
    return float(np.cbrt(abs(np.linalg.det(T[:3, :3]))))


def load(out_dir: Path) -> dict:
    """读 extract_hd 的输出：cameras.json 的内容，外加 dir（高清帧目录）。"""
    out_dir = Path(out_dir)
    d = json.loads((out_dir / "cameras.json").read_text())
    d["dir"] = str(out_dir)
    return d


def project_box(rec: dict, frame: dict, size_wh) -> tuple:
    """框的 8 个角投到这一帧：返回 (外接框 xyxy（未裁剪）, 截断比例)。

    截断比例 = 1 − 画面内面积 / 外接框面积；有角点在相机后面（z < 5 cm）时只用前面的角；
    全在后面返回 (None, 1.0)。
    """
    from smallobj import boxes
    K = np.asarray(frame["K"], float)
    w2c = np.linalg.inv(np.asarray(frame["c2w"], float))
    cam = boxes.corners(rec) @ w2c[:3, :3].T + w2c[:3, 3]
    cam = cam[cam[:, 2] > 0.05]
    if len(cam) == 0:
        return None, 1.0
    uv = cam[:, :2] / cam[:, 2:3] * [K[0, 0], K[1, 1]] + [K[0, 2], K[1, 2]]
    x0, y0 = uv.min(0)
    x1, y1 = uv.max(0)
    W, H = size_wh
    area = max(x1 - x0, 1e-9) * max(y1 - y0, 1e-9)
    inside = max(0.0, min(x1, W) - max(x0, 0)) * max(0.0, min(y1, H) - max(y0, 0))
    return [float(x0), float(y0), float(x1), float(y1)], float(1.0 - inside / area)


def best_view(rec: dict, cams: dict) -> tuple:
    """最好的一帧：画面内面积 ×（1 − 截断）最大。返回 (source_frame 或 None, 那一帧的 xyxy, 截断 < 0.5 的帧数)。"""
    best, best_box, best_score, n_views = None, None, 0.0, 0
    for f in cams["frames"]:
        xyxy, trunc = project_box(rec, f, cams["size_wh"])
        if xyxy is None or trunc >= 1.0:
            continue
        n_views += trunc < 0.5
        score = (xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1]) * (1 - trunc) ** 2
        if score > best_score:
            best, best_box, best_score = int(f["source_frame"]), xyxy, score
    return best, best_box, n_views
