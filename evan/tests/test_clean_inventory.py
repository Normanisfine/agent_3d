import json

import numpy as np
from PIL import Image

from smallobj import clean_inventory

K = [[100.0, 0, 50.0], [0, 100.0, 40.0], [0, 0, 1]]


def _c2w(dx=0.0):
    """相机在 (dx, 0, 0) 朝世界 +y 看（OpenCV：x 右、y 下、z 前），世界 z 朝上。"""
    T = np.eye(4)
    T[:3, :3] = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]
    T[0, 3] = dx
    return T


def test_points_from_mask_backprojects():
    depth = np.full((80, 100), 2.0, np.float32)
    mask = np.zeros((80, 100), bool)
    mask[40:43, 50:53] = True
    pts = clean_inventory.points_from_mask(mask, depth, K, np.eye(4))
    assert pts.shape == (9, 3) and np.allclose(pts[:, 2], 2.0)
    assert np.allclose(sorted(set(np.round(pts[:, 0], 6))), [0.0, 0.02, 0.04])
    depth[41, 51] = np.nan
    assert len(clean_inventory.points_from_mask(mask, depth, K, np.eye(4))) == 8


def test_build_two_frames_one_object(tmp_path):
    hd_dir, masks = tmp_path / "hd", tmp_path / "masks"
    (hd_dir / "depth").mkdir(parents=True)
    masks.mkdir()
    frames, index = [], []
    for k, (s, dx) in enumerate(((0, 0.0), (12, 0.01))):
        np.save(hd_dir / "depth" / f"{s:06d}.npy", np.full((80, 100), 2.0, np.float32))
        frames.append({"source_frame": s, "K": K, "c2w": _c2w(dx).tolist()})
        m = np.zeros((80, 100), np.uint8)
        m[30:40, 40:60] = 255
        Image.fromarray(m).save(masks / f"m{k}.png")
        index.append({"frame": s, "label": "picture frame", "score": 0.8 - 0.1 * k, "mask": f"m{k}.png",
                      "box_xyxy": [40, 30, 60, 40]})
    (hd_dir / "cameras.json").write_text(json.dumps({"size_wh": [100, 80], "frames": frames}))
    (masks / "index.json").write_text(json.dumps(index))
    items = clean_inventory.build(hd_dir, masks)
    assert len(items) == 1
    it = items[0]
    assert it["source"] == "clean" and it["category"] == "picture frame" and it["n_frames"] == 2
    assert abs(max(it["size"]) - 0.39) < 0.05 * 0.39       # 20 像素 × 2 m / 100 ≈ 0.39–0.40 m
    assert abs(it["size"][2] - 0.19) < 0.05 * 0.19 + 0.005  # 10 像素高
    assert it["best_frame"] == 0 and it["item_id"].startswith("c")
