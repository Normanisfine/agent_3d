import numpy as np

from smallobj import align


def _rz(t):
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def test_sim3_recovers_known():
    rng = np.random.default_rng(0)
    src = rng.normal(size=(32, 3))
    R = _rz(np.deg2rad(40))
    dst = 1.3 * src @ R.T + np.array([0.5, -2.0, 218.0])
    s, Rh, t = align.align_sim3(src, dst, gravity=True, with_scale=True)
    assert abs(s - 1.3) < 1e-6
    assert np.allclose(Rh, R, atol=1e-6)
    assert np.allclose(s * src @ Rh.T + t, dst, atol=1e-6)


def test_gravity_only_yaw():
    rng = np.random.default_rng(1)
    src = rng.normal(size=(20, 3))
    dst = src + rng.normal(scale=0.01, size=src.shape)
    _, R, _ = align.align_sim3(src, dst, gravity=True, with_scale=True)
    assert np.allclose(R[2], [0, 0, 1]) and np.allclose(R[:, 2], [0, 0, 1])


def test_no_scale():
    rng = np.random.default_rng(2)
    src = rng.normal(size=(20, 3))
    s, _, _ = align.align_sim3(src, 2.0 * src, gravity=True, with_scale=False)
    assert s == 1.0


def test_apply_box_transform():
    rec = {"object_id": "a", "category": "cup", "center": [1.0, 0.0, 0.0], "yaw": 0.0, "size": [0.1, 0.1, 0.1],
           "confidence": 1.0, "source": "pred"}
    out = align.apply(rec, 2.0, _rz(np.pi / 2), np.array([0.0, 0.0, 1.0]))
    assert np.allclose(out["center"], [0.0, 2.0, 1.0], atol=1e-9)
    assert np.allclose(out["size"], [0.2, 0.2, 0.2])
    assert abs(out["yaw"] - np.pi / 2) < 1e-9


def test_pipeline_to_gt_recovers_transform(tmp_path):
    import json
    rng = np.random.default_rng(3)
    stamps = [1_000_000_000 + 97_000_000 * i for i in range(40)]
    gt_centers = np.c_[rng.uniform(-2, 2, 40), rng.uniform(-3, 1, 40), 218.5 + rng.uniform(-0.2, 0.2, 40)]
    scene = tmp_path / "scene"
    for s, c in zip(stamps, gt_centers):
        d = scene / "frames" / str(s)
        d.mkdir(parents=True)
        T = np.eye(4); T[:3, 3] = c
        (d / "RT.json").write_text(json.dumps(T.tolist()))
    (scene / "frame_map.json").write_text(json.dumps({"timestamps_ns": stamps}))
    # 流程坐标系 = 真值经过 s=0.8、绕 z 转 30°、平移后的样子；只用其中 32 帧
    R = _rz(np.deg2rad(30)); s_true = 0.8; t_true = np.array([1.0, 2.0, -217.0])
    picks = list(range(0, 40, 40 // 32 + 0))[:32]
    frames = []
    for i in picks:
        T = np.eye(4); T[:3, 3] = s_true * R @ gt_centers[i] + t_true
        frames.append({"source_frame": i, "c2w": T.tolist()})
    bundle = tmp_path / "bundle" / "alignment"
    bundle.mkdir(parents=True)
    (bundle / "cameras.json").write_text(json.dumps({"frames": frames}))
    out = align.pipeline_to_gt(tmp_path / "bundle", scene, with_scale=True)
    assert out["residual_median_m"] < 1e-6
    assert abs(out["s"] - 1 / s_true) < 1e-6
