import numpy as np

from smallobj import boxes, configs, p0, score


def _item(iid, c, size):
    r = boxes.record(iid, "cup", c, 0.3, size, source="boxer")
    r.update(item_id=iid)
    return r


def test_p0_falls_back_to_box():
    items = [_item("a", (0, 0, 0.8), (0.1, 0.1, 0.12)), _item("b", (1, 0, 0.8), (0.2, 0.1, 0.1)),
             _item("c", (2, 0, 0.8), (0.05, 0.05, 0.05))]
    placed = boxes.record("pa", "x", (0.01, 0, 0.81), 0.2, (0.09, 0.1, 0.12))
    placements = {"a": {"status": "accepted", "placed_box": placed}, "b": {"status": "rejected_fit", "placed_box": placed},
                  "c": None}
    out = p0.assemble(items, placements)
    assert [o["source"] for o in out] == ["gen", "box", "box"]
    assert np.allclose(out[0]["center"], placed["center"]) and out[0]["object_id"] == "a"
    for o, it in zip(out[1:], items[1:]):
        assert np.allclose(o["center"], it["center"]) and np.allclose(o["size"], it["size"])
    assert all(o["category"] == "cup" for o in out)


def test_p0_objects_json_is_scoreable(tmp_path):
    items = [_item("a", (0, 0, 0.8), (0.1, 0.1, 0.12))]
    out = p0.assemble(items, {"a": None})
    boxes.save(out, tmp_path / "objects.json")
    back = boxes.load(tmp_path / "objects.json")
    res = score.score_predictions(back, back, {"s": 1.0, "R": np.eye(3), "t": np.zeros(3)}, configs.default_thresholds())
    assert res["n_pred"] == 1 and res["rows"][0]["D"] == "correct"


def test_p0_generation_targets():
    items = [_item("s", (0, 0, 0.8), (0.3, 0.1, 0.1)), _item("m", (1, 0, 0.8), (0.6, 0.2, 0.2))]
    assert p0.generation_targets(items) == ["s"]


def test_blender_assemble_roundtrip(tmp_path):
    # 生成网格按 matrix_world 摆进 .blend，再用评测同一套导出：框要和 Python 里算的一致（验证 glTF 轴向抵消）
    import trimesh
    from smallobj import export_blend, gen3d
    a = trimesh.creation.box(extents=(1.0, 0.4, 0.4)); a.apply_translation((0, 0, 0.2))
    b = trimesh.creation.box(extents=(0.4, 0.4, 1.0)); b.apply_translation((-0.3, 0, 0.5))
    mesh = gen3d.clean_mesh(trimesh.util.concatenate([a, b]), up="z")
    mesh.export(tmp_path / "m.glb")
    M = np.eye(4)
    M[:3, :3] = 0.3 * boxes.rot_z(0.5)
    M[:3, 3] = (1.0, 2.0, 0.0)
    placed = boxes.fit_obb(trimesh.transform_points(mesh.vertices, M))
    objs = p0.assemble([_item("g", (1, 2, 0.1), (0.3, 0.1, 0.3)), _item("k", (3, 0, 0.5), (0.4, 0.2, 0.3))],
                       {"g": {"status": "accepted", "placed_box": placed, "mesh_glb": str(tmp_path / "m.glb"),
                              "matrix_world": M.tolist()}})
    pl = {"g": {"status": "accepted", "mesh_glb": str(tmp_path / "m.glb"), "matrix_world": M.tolist()}}
    assert p0.assemble_blend(objs, pl, tmp_path / "scene.blend")
    export_blend.export_objects(tmp_path / "scene.blend", tmp_path / "exp.json")
    got = {r["object_id"]: r for r in boxes.load(tmp_path / "exp.json")}
    assert np.allclose(got["g"]["center"], placed["center"], atol=2e-3)
    assert np.allclose(sorted(got["g"]["size"]), sorted(placed["size"]), atol=2e-3)
    assert np.allclose(got["k"]["center"], [3, 0, 0.5], atol=1e-3) and np.allclose(sorted(got["k"]["size"]), [0.2, 0.3, 0.4], atol=1e-3)
