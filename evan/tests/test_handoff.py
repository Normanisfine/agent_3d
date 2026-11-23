import json

import numpy as np

from smallobj import boxes, handoff


def _r(iid, cat, cx, cy, z_bottom, l, w, h, yaw=0.0):
    return boxes.record(iid, cat, [cx, cy, z_bottom + h / 2], yaw, [l, w, h], source="pred")


def _sup(recs, **kw):
    return {r["object_id"]: s for r, s in zip(recs, handoff.supports(recs, **kw))}


def _frame(source_frame, eye, K=((100.0, 0, 100.0), (0, 100.0, 75.0), (0, 0, 1.0))):
    """朝 +x 看、图像上方是 +z 的相机（OpenCV：x 右、y 下、z 前），放在 eye。"""
    c2w = np.eye(4)
    c2w[:3, :3] = np.array([[0, -1, 0], [0, 0, -1], [1, 0, 0]], float).T   # 列 = 相机的 x、y、z 轴在世界里的方向
    c2w[:3, 3] = eye
    return {"source_frame": source_frame, "c2w": c2w.tolist(), "K": [list(row) for row in K]}


def test_support_floor_instance_floating():
    recs = [_r("table", "furniture/table", 0, 0, 0.0, 1.0, 1.0, 0.75),
            _r("cup", "decor/cup", 0.2, 0.1, 0.76, 0.08, 0.08, 0.10),        # 比桌面高 1 cm → 桌子
            _r("book", "decor/book", -0.2, 0.0, 0.73, 0.25, 0.18, 0.04),     # 陷进桌面 2 cm → 桌子
            _r("mug", "decor/mug", -0.2, 0.0, 0.77, 0.08, 0.08, 0.10),       # 书顶 0.77：叠在书上，不是桌子
            _r("toy", "decor/toy", 2.0, 2.0, 0.02, 0.2, 0.2, 0.2),           # 离地 2 cm → 地面
            _r("picture", "decor/picture", 3.0, 0.0, 1.20, 0.6, 0.03, 0.4),  # 挂在墙上 → None
            _r("lamp", "lighting/lamp", 0.3, -0.3, 0.85, 0.1, 0.1, 0.3)]     # 悬在桌面上方 10 cm → None
    s = _sup(recs)
    assert s["table"]["support"] == "floor" and s["table"]["gap_m"] == 0.0 and s["table"]["overlap"] == 1.0
    assert s["cup"]["support"] == "table" and abs(s["cup"]["gap_m"] - 0.01) < 1e-9 and abs(s["cup"]["overlap"] - 1) < 1e-9
    assert s["book"]["support"] == "table" and abs(s["book"]["gap_m"] + 0.02) < 1e-9
    assert s["mug"]["support"] == "book"
    assert s["toy"]["support"] == "floor"
    assert s["picture"] == {"support": None, "gap_m": None, "overlap": None}
    assert s["lamp"]["support"] is None
    assert _sup(recs, max_gap=0.12)["lamp"]["support"] == "table"   # 容差是参数


def test_support_needs_footprint_overlap():
    shelf = _r("shelf", "furniture/shelf", 0, 0, 0.0, 2.0, 0.3, 1.0, yaw=0.785398)   # 转了 45° 的细长架子
    on = _r("vase", "decor/vase", 0.5, 0.5, 1.0, 0.1, 0.1, 0.2)       # 在架子的长轴上
    off = _r("cup", "decor/cup", 0.6, -0.6, 1.0, 0.1, 0.1, 0.1)       # 在架子旁边：同样高度，足迹不相交
    edge = _r("tray", "decor/tray", 0.0, 0.0, 1.0, 0.4, 3.0, 0.02, yaw=0.785398)  # 只有一小条搭在架子上（交叠 < 25%）
    s = _sup([shelf, on, off, edge])
    assert s["vase"]["support"] == "shelf" and s["cup"]["support"] is None and s["tray"]["support"] is None
    assert abs(handoff.footprint_overlap(on, shelf) - 0.01) < 1e-9 and handoff.footprint_overlap(off, shelf) == 0.0


def test_support_has_no_cycles():
    # 两块叠在同一高度的地毯、踩着地毯的沙发：都记地面，不会互相当支撑
    recs = [_r("rug_a", "decor/rug", 0, 0, 0.0, 2.0, 1.5, 0.012), _r("rug_b", "decor/rug", 0.5, 0, 0.0, 2.0, 1.5, 0.012),
            _r("sofa", "furniture/sofa", 0, 0, 0.0, 1.8, 0.9, 0.8), _r("photo", "decor/paper", 0, 0.6, 0.012, 0.2, 0.15, 0.01)]
    s = _sup(recs)
    assert s["rug_a"]["support"] == "floor" and s["rug_b"]["support"] == "floor" and s["sofa"]["support"] == "floor"
    assert s["photo"]["support"] in ("rug_a", "rug_b")   # 放在地毯上的照片：地毯（比地面高）


def test_inside_smallest_container():
    recs = [_r("room", "context/kitchen", 0, 0, -0.1, 4.0, 4.0, 2.6), _r("sofa", "furniture/sofa", 0, 0, 0.0, 2.0, 0.9, 0.9),
            _r("cushion", "decor/cushion", 0.5, 0.0, 0.45, 0.4, 0.4, 0.3), _r("far", "decor/vase", 9.0, 9.0, 0.0, 0.1, 0.1, 0.2)]
    assert handoff.inside(recs) == [None, "room", "sofa", None]
    assert _sup(recs)["cushion"]["support"] is None   # 坐垫在沙发的框里面：按框看不出支撑面


def test_select_views_largest_inside_image():
    box = _r("vase", "decor/vase", 0.0, 0.0, 0.9, 0.2, 0.2, 0.2)
    cams = {"size_wh": [200, 150], "frames": [
        _frame(10, [-4.0, 0.0, 1.0]),    # 远：小
        _frame(20, [-1.0, 0.0, 1.0]),    # 近：大，完整
        _frame(30, [-2.0, 0.0, 1.0]),    # 中
        _frame(40, [-1.5, 0.0, 1.0]),    # 比 30 近
        _frame(50, [3.0, 0.0, 1.0]),     # 框在相机后面
        _frame(60, [-1.0, 5.0, 1.0])]}   # 框在画面外
    views = handoff.select_views(box, cams)
    assert [v["frame"] for v in views] == [20, 40, 30]
    assert views[0]["truncation"] == 0.0 and views[0]["area_px"] > views[1]["area_px"] > views[2]["area_px"]
    x0, y0, x1, y1 = views[0]["bbox_xyxy"]
    assert 0 <= x0 < 100 < x1 <= 200 and 0 <= y0 < 75 < y1 <= 150    # 框中心在光轴上，外接框包住主点
    assert [v["frame"] for v in handoff.select_views(box, cams, k=1)] == [20]
    assert handoff.select_views(box, {"size_wh": [200, 150], "frames": cams["frames"][4:]}) == []


def test_select_views_counts_only_area_inside_image():
    box = _r("cabinet", "furniture/cabinet", 0.0, 0.0, 0.5, 0.4, 1.0, 1.0)
    cams = {"size_wh": [200, 150], "frames": [_frame(1, [-1.2, 0.0, 1.0]), _frame(2, [-0.6, 0.9, 1.0])]}
    views = handoff.select_views(box, cams)
    assert [v["frame"] for v in views] == [1, 2] and views[1]["truncation"] > 0.3   # 2 更近，但大半出画
    for v in views:
        x0, y0, x1, y1 = v["bbox_xyxy"]
        assert 0 <= x0 <= x1 <= 200 and 0 <= y0 <= y1 <= 150
        assert abs(v["area_px"] - (x1 - x0) * (y1 - y0)) < 0.5 * (x1 - x0 + y1 - y0)   # 两边各自四舍五入到 0.1


def test_visible_fraction_uses_depth():
    box = _r("vase", "decor/vase", 0.0, 0.0, 0.9, 0.2, 0.2, 0.2)        # 最近的角离相机 1.9 m
    frame, wh = _frame(0, [-2.0, 0.0, 1.0]), [200, 150]
    assert handoff.visible_fraction(box, frame, wh, np.full((150, 200), 2.0, np.float32)) == 1.0    # 表面就在框上
    assert handoff.visible_fraction(box, frame, wh, np.full((150, 200), 1.0, np.float32)) == 0.0    # 前面 1 m 有堵墙
    assert handoff.visible_fraction(box, frame, wh, np.full((150, 200), np.nan, np.float32)) == 1.0  # 深度无效按可见
    half = np.full((150, 200), 2.0, np.float32)
    half[:, :100] = 1.0                                                  # 左半边被挡
    assert abs(handoff.visible_fraction(box, frame, wh, half) - 0.5) < 0.1
    assert handoff.visible_fraction(box, _frame(0, [3.0, 0.0, 1.0]), wh, half) == 0.0   # 框在相机后面


def test_inventory_ties_and_unmatched():
    dec = {"b000": {"action": "skipped", "reason": "不是真东西"}, "b001": {"action": "built", "object_id": "lamp"},
           "b002": {"action": "built", "object_id": "lamp", "note": "重复检测"}, "b003": {"action": "built", "object_id": "tv"}}
    assert handoff.inventory_ties(dec) == {"lamp": ["b001", "b002"], "tv": ["b003"]}
    counted = [_r(i, "x", 0, 0, 0, 1, 1, 1) for i in ("tv", "lamp", "socket", "rug")]
    rows = [{"gt_id": "g1", "D": "correct", "pred_id": "tv"}, {"gt_id": "g2", "D": "missed"},
            {"gt_id": "g3", "D": "misplaced", "pred_id": "rug"}]
    assert [p["object_id"] for p in handoff.unmatched(counted, rows)] == ["lamp", "socket"]


def test_project_edges_clips_at_camera_plane():
    front = _r("a", "x", 0.0, 0.0, 0.9, 0.2, 0.2, 0.2)
    segs = handoff.project_edges(front, _frame(0, [-1.0, 0.0, 1.0]))
    assert len(segs) == 12
    pts = np.array([p for s in segs for p in s])
    assert np.allclose([pts[:, 0].min(), pts[:, 0].max()], [100 - 100 * 0.1 / 0.9, 100 + 100 * 0.1 / 0.9])
    through = _r("b", "x", 0.0, 0.0, 0.5, 2.0, 0.4, 1.0)      # 相机在框里面：后半截在相机后面
    segs = handoff.project_edges(through, _frame(0, [0.0, 0.0, 1.0]))
    assert len(segs) == 8 and np.isfinite(np.array(segs)).all()   # 后面那一圈 4 条棱不要，4 条长棱截断
    assert handoff.project_edges(front, _frame(0, [3.0, 0.0, 1.0])) == []


def test_crop_window_and_view():
    win = handoff.crop_window([90, 70, 110, 80], [200, 150], aspect=4 / 3, pad=2.0, min_w=40)
    assert np.allclose(win, [80, 60, 120, 90])                                   # 宽 = 2 × 20，高 = 宽 / (4/3)
    win = handoff.crop_window([-30, 0, 10, 20], [200, 150], aspect=4 / 3, pad=2.0, min_w=80)
    assert np.allclose(win, [0, 0, 80, 60])                                      # 贴着画面的角：往里挪，不出画
    assert np.allclose(handoff.crop_window([0, 0, 200, 150], [200, 150]), [0, 0, 200, 150])   # 再大也就是整幅
    assert np.allclose(handoff.crop_window([20, 0, 60, 150], [120, 150]), [0, 30, 120, 120])  # 竖幅画面：宽度封顶

    K = np.array([[100.0, 0, 100.0], [0, 104.0, 75.0], [0, 0, 1.0]])             # fx ≠ fy
    win = [80.0, 60.0, 120.0, 90.0]
    K2, wh = handoff.crop_view(K, win, out_w=400)
    K2 = np.array(K2)
    assert wh[0] == 400 and K2[0, 0] == K2[1, 1] == 1000.0 and wh[1] == round(30 * 1000 / 104)
    p = np.array([0.03, -0.02, 1.0])                                             # 相机坐标里的一个点
    u, v = (K @ p)[:2]
    u2, v2 = (K2 @ p)[:2]
    assert np.isclose(u2, (u - 80) * 400 / 40) and np.isclose(v2, (v - 60) * 1000 / 104)   # 渲染图拉伸回去就对上
    assert abs(wh[1] - 30 * 1000 / 104) <= 0.5


def test_build_and_write(tmp_path):
    run = tmp_path / "runs" / "A2-x" / "123" / "0"
    (run / "export").mkdir(parents=True)
    recs = [_r("floor", "structure/floor", 0, 0, -0.05, 5, 5, 0.05), _r("wall_n", "structure/wall", 0, 2.5, 0, 5, 0.1, 2.5),
            _r("table", "furniture/table", 0, 0, 0.0, 1.0, 1.0, 0.8), _r("vase", "decor/vase", 0, 0, 0.8, 0.2, 0.2, 0.2),
            _r("clock", "decor/clock", 0.0, 2.4, 1.6, 0.3, 0.05, 0.3)]
    boxes.save(recs, run / "export" / "objects.json")
    (run / "inventory_decisions.json").write_text(json.dumps({"b000": {"action": "built", "object_id": "table"},
                                                              "b001": {"action": "skipped", "reason": "x"}}))
    hd_dir = tmp_path / "perception" / "123" / "hd"
    hd_dir.mkdir(parents=True)
    (hd_dir / "cameras.json").write_text(json.dumps({"size_wh": [200, 150], "frames": [
        _frame(7, [-2.0, 0.0, 1.0]), _frame(9, [-3.0, 0.0, 1.0])]}))
    out = handoff.write(run, proj=tmp_path)
    assert json.loads((run / "objects.json").read_text()) == out
    assert out["run"] == "runs/A2-x/123/0" and out["scene"] == "123" and out["version"] == handoff.VERSION
    assert out["tolerances"] == {"floor_z": 0.0, "support_gap_m": 0.03, "support_pen_m": 0.03, "support_min_overlap": 0.25}
    assert out["counts"] == {"instances": 3, "on_floor": 1, "on_instance": 1, "no_support": 1}
    by = {o["id"]: o for o in out["objects"]}
    assert list(by) == ["table", "vase", "clock"]                    # 结构件不出现，顺序同导出
    assert by["vase"]["support"] == "table" and by["table"]["support"] == "floor" and by["clock"]["support"] is None
    assert by["vase"]["center"] == recs[3]["center"] and by["vase"]["size"] == recs[3]["size"] and by["vase"]["yaw"] == 0.0
    assert by["table"]["from_inventory"] is True and by["table"]["inventory_ids"] == ["b000"]
    assert by["vase"]["from_inventory"] is False and by["vase"]["inventory_ids"] == []
    assert [v["frame"] for v in by["vase"]["views"]] == [7, 9]
    assert by["vase"]["views"][0]["image"] == "perception/123/hd/frames/000007.png"

    (run / "inventory_decisions.json").unlink()                      # 没有清单决定（A1 这类）：不知道 → None
    out = handoff.build(run, proj=tmp_path)
    assert all(o["from_inventory"] is None and o["inventory_ids"] is None for o in out["objects"])
    assert out["sources"]["inventory_decisions"] is None
