import numpy as np
import pytest

from smallobj import colorize


def quad(z, x0=-0.5, x1=0.5, y0=-0.5, y1=0.5):
    """z 平面上的一个矩形，两个三角形。"""
    a, b, c, d = (x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)
    return np.array([[a, b, c], [a, c, d]], float)


def test_sample_surface_area_weighted_and_on_triangles():
    big, small = quad(1.0, -1, 1, -1, 1), quad(1.0, 0, 0.5, 0, 0.5)  # 面积 4 和 0.25
    pts = colorize.sample_surface(np.concatenate([big, small]), n=1700, seed=0)
    assert pts.shape == (1700, 3) and np.allclose(pts[:, 2], 1.0)
    in_small = (pts[:, 0] >= 0) & (pts[:, 0] <= 0.5) & (pts[:, 1] >= 0) & (pts[:, 1] <= 0.5)
    # 大矩形也盖住小矩形那一块：小块里的点约占 (0.25 + 0.25) / 4.25
    assert in_small.mean() == pytest.approx(0.5 / 4.25, abs=0.03)


def test_srgb_to_linear():
    assert colorize.srgb_to_linear(np.array([0.0, 0.5, 1.0])) == pytest.approx([0.0, 0.2140, 1.0], abs=1e-3)


def _frame():
    # 相机在原点朝 +z（OpenCV），100×100，焦距 100：整幅图是红色，深度处处 2 m
    K = [[100, 0, 50], [0, 100, 50], [0, 0, 1]]
    img = np.zeros((100, 100, 3), np.uint8)
    img[..., 0] = 255
    return {"K": K, "c2w": np.eye(4).tolist()}, img, np.full((100, 100), 2.0)


def test_object_colors_depth_test_and_root_fallback():
    cam, img, depth = _frame()
    pts = {"table": colorize.sample_surface(quad(2.0), 400, seed=0),          # 正好在观测到的表面上
           "hidden": colorize.sample_surface(quad(3.0), 400, seed=1),         # 被前面的表面挡住
           "leg": colorize.sample_surface(quad(3.0, 0, 0.1, 0, 0.1), 50, seed=2),  # 自己没取到颜色，跟着根节点 table 走
           "away": colorize.sample_surface(quad(2.0, 5, 6, 5, 6), 100, seed=3)}   # 画面外
    root_of = {"table": "table", "hidden": "hidden", "leg": "table", "away": "away"}
    out = colorize.object_colors(pts, root_of, [(cam, img, depth)], min_samples=20)
    assert out["table"]["source"] == "own" and out["table"]["rgb"] == pytest.approx([1.0, 0.0, 0.0])
    assert out["leg"]["source"] == "root" and out["leg"]["rgb"] == pytest.approx([1.0, 0.0, 0.0])
    assert "hidden" not in out and "away" not in out


def test_object_colors_ignores_invalid_depth():
    cam, img, depth = _frame()
    depth[:] = np.nan  # Pi3X 没把握的像素：不拿来上色
    pts = {"table": colorize.sample_surface(quad(2.0), 400, seed=0)}
    assert colorize.object_colors(pts, {"table": "table"}, [(cam, img, depth)], min_samples=20) == {}
