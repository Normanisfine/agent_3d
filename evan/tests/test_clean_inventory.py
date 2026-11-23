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


def _scene(tmp_path, dets, depth_name="depth", depth=2.0):
    """dets: [(帧号, 标签, 来源, (y0, y1, x0, x1))]；每帧相机一样。"""
    hd_dir, masks = tmp_path / "hd", tmp_path / "masks"
    (hd_dir / depth_name).mkdir(parents=True)
    masks.mkdir()
    frames, index = {}, []
    for k, (s, label, src, (y0, y1, x0, x1)) in enumerate(dets):
        np.save(hd_dir / depth_name / f"{s:06d}.npy", np.full((80, 100), depth, np.float32))
        frames[s] = {"source_frame": s, "K": K, "c2w": _c2w().tolist()}
        m = np.zeros((80, 100), np.uint8)
        m[y0:y1, x0:x1] = 255
        Image.fromarray(m).save(masks / f"m{k}.png")
        index.append({"frame": s, "label": label, "score": 0.8, "mask": f"m{k}.png", "box_xyxy": [x0, y0, x1, y1],
                      "source": src})
    (hd_dir / "cameras.json").write_text(json.dumps({"size_wh": [100, 80], "frames": list(frames.values())}))
    (masks / "index.json").write_text(json.dumps(index))
    return hd_dir, masks


def test_build_tile_only_detections_need_two_frames(tmp_path):
    # 清单 v2：只在放大窗口里检测到的物体要在 ≥ 2 帧里出现才收（代替 SceneRig 用 MolmoPoint 做的第二个模型确认）；
    # 整帧检测到的照旧 1 帧就收
    hd_dir, masks = _scene(tmp_path, [(0, "cup", "tile", (30, 40, 10, 30)), (5, "cup", "tile", (30, 40, 10, 30)),
                                      (0, "remote control", "tile", (30, 40, 70, 90)),
                                      (0, "book", "full", (60, 70, 40, 60))])
    cats = sorted(it["category"] for it in clean_inventory.build(hd_dir, masks, min_frames_tile=2))
    assert cats == ["book", "cup"]
    assert sorted(it["category"] for it in clean_inventory.build(hd_dir, masks)) == ["book", "cup", "remote control"]
    cup = next(it for it in clean_inventory.build(hd_dir, masks, min_frames_tile=2) if it["category"] == "cup")
    assert cup["det_sources"] == ["tile"] and cup["n_frames"] == 2


def test_build_reads_other_depth(tmp_path):
    # 清单 v2 用对齐到 Pi3X 尺度的 MoGe-2 深度（hd/depth_moge/）反投影
    hd_dir, masks = _scene(tmp_path, [(0, "book", "full", (30, 40, 40, 60))], depth_name="depth_moge", depth=4.0)
    it = clean_inventory.build(hd_dir, masks, depth_name="depth_moge")[0]
    assert abs(max(it["size"]) - 0.78) < 0.05


def test_build_keep_filter_for_ablations(tmp_path):
    # SAM 3 只跑一次（整帧 + 窗口，固定表 + 开放词表），消融时按检测来源、类别过滤
    hd_dir, masks = _scene(tmp_path, [(0, "cup", "tile", (30, 40, 10, 30)), (5, "cup", "tile", (30, 40, 10, 30)),
                                      (0, "book", "full", (60, 70, 40, 60))])
    items = clean_inventory.build(hd_dir, masks, keep=lambda m: m.get("source") == "full")
    assert [it["category"] for it in items] == ["book"]
