from pathlib import Path

import numpy as np
import pytest

from smallobj import boxes, export_blend

PROJ = Path(__file__).resolve().parent.parent
OFFICE48 = PROJ / "third_party/aha-3d/examples/office48/whitebox.blend"


def _box_mesh(rec):
    v = boxes.corners(rec)
    f = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                  [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    return v, f


def _same_corners(a, b, tol=1e-6):
    ca, cb = boxes.corners(a), boxes.corners(b)
    return all(np.min(np.linalg.norm(cb - p, axis=1)) < tol for p in ca)


def test_fit_groups_recovers_rotated_box():
    truth = boxes.record("t", "decor/cups", (1.0, 2.0, 0.5), 0.6, (0.3, 0.1, 0.2))
    other = boxes.record("o", "architecture/room", (0.0, 0.0, 1.2), 0.0, (4.0, 4.0, 2.4))
    v1, f1 = _box_mesh(truth)
    v2, f2 = _box_mesh(other)
    vertices = np.vstack([v1, v2])
    faces = np.vstack([f1, f2 + 8])
    face_object_id = np.r_[np.zeros(12, int), np.ones(12, int)]
    groups = [{"id": "cup_1", "semantic_class": "decor/cups"}, {"id": "room", "semantic_class": "architecture/room"}]
    recs = export_blend.fit_groups(vertices, faces, face_object_id, groups)
    by_id = {r["object_id"]: r for r in recs}
    assert set(by_id) == {"cup_1", "room"}
    assert by_id["cup_1"]["category"] == "decor/cups"
    assert _same_corners(by_id["cup_1"], truth, tol=1e-6)


def test_fit_groups_merges_parts_of_one_instance():
    a = boxes.record("a", "x", (0.0, 0.0, 0.5), 0.0, (1.0, 0.5, 0.1))   # 桌面
    b = boxes.record("b", "x", (0.0, 0.0, 0.2), 0.0, (0.1, 0.1, 0.4))   # 桌腿
    va, fa = _box_mesh(a)
    vb, fb = _box_mesh(b)
    recs = export_blend.fit_groups(np.vstack([va, vb]), np.vstack([fa, fb + 8]), np.r_[np.zeros(12, int), np.ones(12, int)],
                                   [{"id": "table", "semantic_class": "furniture/tables"}] * 2)
    assert len(recs) == 1
    assert np.allclose(sorted(recs[0]["size"]), sorted([1.0, 0.5, 0.55]), atol=1e-6)


@pytest.mark.skipif(not OFFICE48.exists(), reason="AHa-3D 示例场景不在")
def test_office48_export(tmp_path):
    n = export_blend.export_objects(OFFICE48, tmp_path / "objects.json")
    recs = boxes.load(tmp_path / "objects.json")
    assert n == len(recs) and n > 100
    assert all(min(r["size"]) > 0 for r in recs)


def test_flat_object_gets_min_thickness():
    poster = boxes.record("p", "x", (0.0, 0.0, 1.5), 0.0, (0.6, 0.0, 0.8))
    v, f = _box_mesh(poster)
    recs = export_blend.fit_groups(v, f, np.zeros(12, int), [{"id": "poster", "semantic_class": "decor"}])
    assert min(recs[0]["size"]) == pytest.approx(0.01)
