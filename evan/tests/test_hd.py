import json

import numpy as np

from smallobj import hd


def make_video(path, w, h, n=5):
    import imageio.v3 as iio
    frames = np.stack([np.full((h, w, 3), 20 * i, np.uint8) for i in range(n)])
    iio.imwrite(path, frames, fps=10, codec="libx264", macro_block_size=1)
    return path


def make_bundle(root, proc_wh=(16, 12), source_frames=(0, 2, 4), fx=10.0, fy=10.0, z=2.0, bad_px=None):
    """假 bundle：alignment/cameras.json + pi3x/{predictions,inputs}.npz + reference_build.json。"""
    w, h = proc_wh
    (root / "alignment").mkdir(parents=True)
    (root / "pi3x").mkdir()
    K = [[fx, 0, w / 2], [0, fy, h / 2], [0, 0, 1]]
    frames = [{"source_frame": int(s), "c2w": np.eye(4).tolist(), "intrinsics": K} for s in source_frames]
    (root / "alignment" / "cameras.json").write_text(json.dumps(
        {"processed_size_wh": [w, h], "frames": frames, "world_transform": np.eye(4).tolist()}))
    n = len(source_frames)
    local = np.zeros((n, h, w, 3), np.float32)
    local[..., 2] = z
    conf = np.full((n, h, w, 1), 5.0, np.float32)  # 原始 logit；sigmoid(5) ≈ 0.99
    if bad_px is not None:
        conf[0, bad_px[1], bad_px[0], 0] = -10.0  # sigmoid(-10) ≈ 0，低于 0.1
    poses = np.repeat(np.eye(4, dtype=np.float32)[None], n, 0)
    np.savez(root / "pi3x" / "predictions.npz", local_points=local, conf=conf,
             non_edge=np.ones((n, h, w), bool), camera_poses=poses, points=local)
    np.savez(root / "pi3x" / "inputs.npz", frame_indices=np.array(source_frames))
    (root / "reference_build.json").write_text(json.dumps({"geometry_representation": {"fusion_confidence_min": 0.1}}))
    return root


def test_hd_frames_match_source_frames(tmp_path):
    video = make_video(tmp_path / "in.mp4", 64, 48)
    bundle = make_bundle(tmp_path / "b")
    cams = hd.extract_hd(video, bundle, tmp_path / "hd")
    assert sorted(f["source_frame"] for f in cams["frames"]) == [0, 2, 4]
    from PIL import Image
    for s in (0, 2, 4):
        assert Image.open(tmp_path / "hd" / "frames" / f"{s:06d}.png").size == (64, 48)


def test_hd_intrinsics_anisotropic(tmp_path):
    video = make_video(tmp_path / "in.mp4", 64, 48)
    cams = hd.extract_hd(video, make_bundle(tmp_path / "b"), tmp_path / "hd")
    K = np.array(cams["frames"][0]["K"])
    assert np.allclose(K, [[40, 0, 32], [0, 40, 24], [0, 0, 1]])
    # 流程帧 16×16（原图被拉伸）：x 放大 4 倍，y 放大 3 倍
    cams2 = hd.extract_hd(video, make_bundle(tmp_path / "b2", proc_wh=(16, 16)), tmp_path / "hd2")
    K2 = np.array(cams2["frames"][0]["K"])
    assert np.isclose(K2[0, 0], 40) and np.isclose(K2[1, 1], 30) and np.isclose(K2[1, 2], 24)


def test_hd_portrait(tmp_path):
    video = make_video(tmp_path / "in.mp4", 48, 64)
    cams = hd.extract_hd(video, make_bundle(tmp_path / "b", proc_wh=(12, 16)), tmp_path / "hd")
    assert cams["size_wh"] == [48, 64]


def test_hd_depth_upsampled(tmp_path):
    video = make_video(tmp_path / "in.mp4", 64, 48)
    hd.extract_hd(video, make_bundle(tmp_path / "b", bad_px=(3, 5)), tmp_path / "hd")
    d = np.load(tmp_path / "hd" / "depth" / "000000.npy")
    assert d.shape == (48, 64) and d.dtype == np.float32
    assert np.allclose(d[np.isfinite(d)], 2.0)
    assert np.isnan(d[5 * 4 + 1, 3 * 4 + 1])  # 低置信度像素对应的那块是 NaN
    assert np.isfinite(d).mean() > 0.9
    loaded = hd.load(tmp_path / "hd")
    assert loaded["size_wh"] == [64, 48] and len(loaded["frames"]) == 3


def test_project_box_and_best_view():
    from smallobj import boxes
    K = [[100, 0, 50], [0, 100, 40], [0, 0, 1]]
    # 相机在原点朝 +y 看（OpenCV：x 右、y 下、z 前）：世界 z 朝上
    c2w = np.eye(4)
    c2w[:3, :3] = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]
    cup = boxes.record("c", "cup", (0.0, 2.0, 0.0), 0.0, (0.2, 0.2, 0.2))
    xyxy, trunc = hd.project_box(cup, {"K": K, "c2w": c2w.tolist()}, (100, 80))
    assert trunc == 0.0 and 40 < (xyxy[0] + xyxy[2]) / 2 < 60 and 30 < (xyxy[1] + xyxy[3]) / 2 < 50
    side = boxes.record("s", "cup", (1.0, 2.0, 0.0), 0.0, (0.2, 0.2, 0.2))  # 中心正好在画面右边缘，一半出界
    _, trunc2 = hd.project_box(side, {"K": K, "c2w": c2w.tolist()}, (100, 80))
    assert 0 < trunc2 < 1
    behind = boxes.record("b", "cup", (0.0, -2.0, 0.0), 0.0, (0.2, 0.2, 0.2))
    assert hd.project_box(behind, {"K": K, "c2w": c2w.tolist()}, (100, 80)) == (None, 1.0)
    cams = {"size_wh": [100, 80], "frames": [{"source_frame": 0, "K": K, "c2w": c2w.tolist()},
                                             {"source_frame": 5, "K": K, "c2w": np.eye(4).tolist()}]}
    best, box, n_views = hd.best_view(cup, cams)
    assert best == 0 and n_views == 1


def test_align_depth_to_pi3x_scale():
    # 清单 v2：MoGe-2 在高清帧上的深度（边缘清楚、不缺像素）按中位比例对齐到 Pi3X 上采样深度的尺度
    import numpy as np
    from smallobj import hd
    rng = np.random.default_rng(0)
    moge = rng.uniform(1.0, 4.0, (60, 80)).astype(np.float32)
    pi3x = 2.0 * moge
    pi3x[:10] = np.nan                       # Pi3X 低置信度、边缘的地方是 NaN
    pi3x[20:22, :5] *= 3.0                   # 少量离群像素不影响中位数
    moge[59, 79] = np.inf                    # MoGe 自己判无效的像素
    out, s = hd.align_depth(moge, pi3x)
    assert abs(s - 2.0) < 1e-6
    assert np.isfinite(out[:10]).all()       # Pi3X 缺的地方 MoGe 补上
    assert np.isnan(out[59, 79]) and np.allclose(out[30:50], 2.0 * moge[30:50])
