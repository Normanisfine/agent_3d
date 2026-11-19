import numpy as np
import pytest

from smallobj import boxes, visibility

W, H, F = 574, 434, 497.0
K = np.array([[F, 0, W / 2], [0, F, H / 2], [0, 0, 1.0]])
C2W = np.eye(4)  # 相机在原点，朝 +z（OpenCV）


def cube_at(z, side=0.10):
    return boxes.record("c", "cup", (0.0, 0.0, z), 0.0, (side, side, side))


def test_cube_pixels_match_pinhole():
    px = visibility.visible_pixels(cube_at(2.0), C2W, K, (W, H))
    # 正对的面 10 cm、2 m 外约 24.9 px 见方；能看到一点侧面，所以允许 ±15%
    assert 0.85 * 24.85 ** 2 <= px <= 1.15 * 24.85 ** 2 * 1.2


def test_behind_wall_is_hidden():
    depth = np.full((217, 287), 1.0)  # 半分辨率深度图：1 m 处有一堵墙
    dK = K.copy(); dK[:2] *= 0.5
    assert visibility.visible_pixels(cube_at(2.0), C2W, K, (W, H), depth=depth, depth_K=dK) == 0


def test_unregistered_depth_counts_as_visible():
    depth = np.zeros((217, 287))  # 0 = 激光没扫到，按可见算
    dK = K.copy(); dK[:2] *= 0.5
    assert visibility.visible_pixels(cube_at(2.0), C2W, K, (W, H), depth=depth, depth_K=dK) > 500


def test_behind_camera_zero():
    assert visibility.visible_pixels(cube_at(-2.0), C2W, K, (W, H)) == 0


def test_resolution_scales_pixels():
    hi = visibility.visible_pixels(cube_at(2.0), C2W, visibility.scale_K(K, (W, H), (1024, 768)), (1024, 768))
    lo = visibility.visible_pixels(cube_at(2.0), C2W, K, (W, H))
    assert hi / lo == pytest.approx((1024 / W) ** 2, rel=0.2)
