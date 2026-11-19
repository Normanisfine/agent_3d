import json
from pathlib import Path

import numpy as np

from smallobj import boxes, inventory

FX = Path(__file__).parent / "fixtures"


def _det(i, label, center, size, score, frame):
    r = boxes.record(f"d{i}", label, center, 0.1, size, confidence=score, source="det")
    r.update(frame=frame, score=score, bbox2d_xyxy=[0, 0, 10, 10])
    return r


def test_fuse_merges_same_object_across_frames():
    dets = [_det(0, "cup", (1.00, 2.00, 0.80), (0.08, 0.08, 0.10), 0.9, 12),
            _det(1, "cup", (1.01, 2.00, 0.80), (0.08, 0.08, 0.10), 0.7, 23),
            _det(2, "cup", (0.99, 2.01, 0.81), (0.08, 0.08, 0.10), 0.6, 35)]
    out = inventory.fuse(dets, iou_min=0.25)
    assert len(out) == 1
    assert out[0]["n_frames"] == 3 and out[0]["best_frame"] == 12
    assert np.allclose(out[0]["center"], [1.0, 2.0, 0.8], atol=0.01)


def test_fuse_keeps_different_labels_apart():
    dets = [_det(0, "book", (0, 0, 0.8), (0.3, 0.2, 0.05), 0.9, 0),
            _det(1, "laptop", (0, 0, 0.8), (0.3, 0.2, 0.05), 0.8, 0)]
    assert sorted(o["category"] for o in inventory.fuse(dets)) == ["book", "laptop"]


def test_from_boxer_fixture():
    items = inventory.from_boxer(FX / "boxer_raw")
    assert len(items) == 3 and items[0]["category"] == "lamp" and items[0]["source"] == "boxer"
    assert np.allclose(items[0]["center"], [-2.023219347, -0.7289238573, 1.982840657], atol=1e-6)
    assert np.allclose(items[0]["size"], [0.3242979049682617, 0.32119643688201904, 0.49212872982025146], atol=1e-6)
    assert abs(boxes.wrap(items[0]["yaw"] - 2 * np.arctan2(-0.6948986649513245, 0.7191077470779419))) < 1e-5
    assert abs(items[0]["score"] - 0.65) < 1e-6
    assert len({it["item_id"] for it in items}) == 3


def test_save_load_roundtrip(tmp_path):
    items = inventory.from_boxer(FX / "boxer_raw")
    inventory.save(items, tmp_path / "inv.json")
    assert inventory.load(tmp_path / "inv.json") == json.loads(json.dumps(items))


def test_fuse_handles_90deg_swapped_detections():
    # 同一本 0.40×0.10 的书，一帧拟成 (yaw, [0.4, 0.1])，另一帧拟成 (yaw+90°, [0.1, 0.4])：合并后仍是 0.4×0.1
    a = _det(0, "book", (0, 0, 0.8), (0.40, 0.10, 0.03), 0.9, 0)
    b = _det(1, "book", (0, 0, 0.8), (0.10, 0.40, 0.03), 0.8, 12)
    b["yaw"] = a["yaw"] + np.pi / 2
    out = inventory.fuse([a, b])
    assert len(out) == 1
    assert np.allclose(sorted(out[0]["size"][:2]), [0.10, 0.40], atol=1e-6)
