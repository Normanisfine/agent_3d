import numpy as np

from smallobj import boxes


def test_corners_axis_aligned():
    rec = boxes.record("a", "cup", center=(1.0, 2.0, 0.5), yaw=0.0, size=(2.0, 1.0, 1.0))
    c = boxes.corners(rec)
    assert c.shape == (8, 3)
    assert set(np.round(c[:, 0], 6)) == {0.0, 2.0}
    assert set(np.round(c[:, 1], 6)) == {1.5, 2.5}
    assert set(np.round(c[:, 2], 6)) == {0.0, 1.0}


def test_transform_yaw_90():
    rec = boxes.record("a", "cup", center=(1.0, 0.0, 0.5), yaw=0.0, size=(2.0, 1.0, 1.0))
    out = boxes.transform(rec, yaw=np.pi / 2, translation=(0.0, 0.0, 0.0))
    assert np.allclose(out["size"], [2.0, 1.0, 1.0])
    assert np.allclose(out["center"], [0.0, 1.0, 0.5], atol=1e-9)


def test_fit_obb_recovers_rotated_box():
    rng = np.random.default_rng(0)
    for _ in range(100):
        yaw, size = rng.uniform(-np.pi, np.pi), rng.uniform(0.05, 2.0, 3)
        rec = boxes.record("x", "obj", rng.uniform(-3, 3, 3), yaw, size)
        fit = boxes.fit_obb(boxes.corners(rec), object_id="f", category="obj")
        assert np.allclose(sorted(fit["size"][:2]), sorted(size[:2]), atol=1e-6)
        assert np.isclose(fit["size"][2], size[2]) and np.allclose(fit["center"], rec["center"], atol=1e-6)
