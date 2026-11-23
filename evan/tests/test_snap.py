import json

import numpy as np
from PIL import Image

from smallobj import boxes, snap

K = [[100.0, 0, 50.0], [0, 100.0, 40.0], [0, 0, 1]]
WH = (100, 80)


def _c2w(dx=0.0):
    """相机在 (dx, 0, 0) 朝世界 +y 看（OpenCV：x 右、y 下、z 前），世界 z 朝上。"""
    T = np.eye(4)
    T[:3, :3] = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]
    T[0, 3] = dx
    return T


def _frame(s=0, dx=0.0):
    return {"source_frame": s, "K": K, "c2w": _c2w(dx).tolist()}


def _inst(iid, cat, center, size=(0.1, 0.1, 0.1), yaw=0.0):
    return boxes.record(iid, cat, center, yaw, size, source="pred")


def _entry(item_id, label, center, size=(0.1, 0.1, 0.1), alt=(), **kw):
    e = boxes.record(item_id, label, center, 0.0, size, source="clean")
    e.update(item_id=item_id, label=label, alt_labels=list(alt), members=[item_id], **kw)
    return e


def _view(true_box, s=0, dx=0.0, depth=True):
    """条目在这一帧的掩码 = 真实位置的框的剪影；深度图整张都是框前表面的深度。"""
    f = _frame(s, dx)
    front = true_box["center"][1] - true_box["size"][1] / 2
    return {"frame": f, "mask": snap.box_mask(true_box, f, WH),
            "depth": np.full((WH[1], WH[0]), front, np.float32) if depth else None}


def test_eligible_uses_strict_less_than():
    assert snap.eligible(_inst("a", "cup", [0, 0, 0], (0.49, 0.1, 0.1)))
    assert not snap.eligible(_inst("a", "cup", [0, 0, 0], (0.1, 0.5, 0.1)))


def test_words_and_label_rule():
    assert snap.words("sideboard_red_cup", "decor/cup") == ["sideboard", "cup", "cup"]   # 颜色、大组名去掉
    assert snap.words("cabinet_books_s0_pileA1") == ["cabinet", "book", "pilea"]          # 数字切开、变单数
    cup = _inst("sideboard_red_cup", "decor/cup", [0, 0, 0])
    assert snap.label_compatible(cup, _entry("c1", "glass", [0, 0, 0]))                    # cup、glass 同义
    assert snap.label_compatible(cup, _entry("c1", "tissue box", [0, 0, 0], alt=["mug"]))  # 备选类别也算
    assert not snap.label_compatible(cup, _entry("c1", "book", [0, 0, 0]))
    bowl = _inst("coffee_bowl_1", "bowl", [0, 0, 0])
    assert not snap.label_compatible(bowl, _entry("c1", "coffee table", [0, 0, 0]))        # 只共有修饰词不算
    remote = _inst("tv_remote", "objects/remote", [0, 0, 0])
    assert snap.label_compatible(remote, _entry("c1", "remote control", [0, 0, 0]))        # 实例类别的中心词在条目里
    frame = _inst("photo_3", "decor/picture_frame", [0, 0, 0])
    assert snap.label_compatible(frame, _entry("c1", "picture frame", [0, 0, 0]))


def test_associate_nearest_is_one_to_one_and_takes_closest_first():
    insts = [_inst("cup_a", "cup", [0.00, 0, 1]), _inst("cup_b", "cup", [0.10, 0, 1])]
    entries = [_entry("c1", "cup", [0.08, 0, 1]), _entry("c2", "cup", [0.25, 0, 1])]
    # c1 离 cup_b 更近（2 cm）：cup_b 拿 c1，cup_a 只能拿 c2（25 cm，门槛内）
    assert snap.associate_nearest(insts, entries, max_dist=0.3) == {"cup_b": "c1", "cup_a": "c2"}
    # 门槛收到 0.2：cup_a 没有别的候选，不会和 cup_b 共用 c1
    assert snap.associate_nearest(insts, entries, max_dist=0.2) == {"cup_b": "c1"}
    assert snap.associate_nearest(list(reversed(insts)), list(reversed(entries)), max_dist=0.3) == \
        {"cup_b": "c1", "cup_a": "c2"}                                                     # 和输入顺序无关


def test_associate_nearest_gates():
    cup = _inst("cup_a", "cup", [0, 0, 1], (0.1, 0.1, 0.1))
    assert snap.associate_nearest([cup], [_entry("c1", "cup", [0.31, 0, 1])], max_dist=0.3) == {}      # 太远
    assert snap.associate_nearest([cup], [_entry("c1", "cup", [0.05, 0, 1], (0.16, 0.1, 0.1))]) == {}  # 最长边 1.6 倍
    assert snap.associate_nearest([cup], [_entry("c1", "cup", [0.05, 0, 1], (0.16, 0.1, 0.1))], max_ratio=2.0) == \
        {"cup_a": "c1"}
    book = _entry("c1", "book", [0.05, 0, 1])
    assert snap.associate_nearest([cup], [book]) == {}                                     # 类别不相容
    assert snap.associate_nearest([cup], [book], use_labels=False) == {"cup_a": "c1"}
    # 类别相容的远一点的条目优先于不相容的近的
    assert snap.associate_nearest([cup], [book, _entry("c2", "mug", [0.2, 0, 1])]) == {"cup_a": "c2"}


def test_large_instances_are_never_associated():
    table = _inst("table", "furniture/table", [0, 0, 0.4], (1.2, 0.8, 0.75))
    shelf = _inst("shelf", "shelf", [1, 0, 0.4], (0.5, 0.2, 0.2))                           # 正好 0.5：不参加
    entries = [_entry("c1", "table", [0.05, 0, 0.4], (1.2, 0.8, 0.75)), _entry("c2", "shelf", [1.02, 0, 0.4], (0.5, 0.2, 0.2))]
    assert snap.associate_nearest([table, shelf], entries) == {}
    assert snap.associate_decisions([table, shelf], entries, {"c1": {"action": "built", "object_id": "table"},
                                                              "c2": {"action": "built", "object_id": "shelf"}}) == {}


def test_decisions_match_same_inventory_only():
    entries = [_entry(f"c{k:03d}", "cup", [k, 0, 0]) for k in range(10)]
    full = {f"c{k:03d}": {"action": "skipped"} for k in range(10)}
    assert snap.decisions_match(full, entries)
    assert snap.decisions_match({k: v for k, v in full.items() if k != "c009"}, entries)    # 盖住 90%
    assert not snap.decisions_match({k: v for k, v in list(full.items())[:5]}, entries)     # 只盖住一半
    assert not snap.decisions_match({**full, "c010": {"action": "skipped"}}, entries)       # 有这份清单里没有的条目
    assert not snap.decisions_match({f"b{k:03d}": {"action": "skipped"} for k in range(10)}, entries)  # Boxer 清单
    assert not snap.decisions_match({}, entries)


def test_associate_decisions_follows_the_agent_and_picks_nearest_duplicate():
    insts = [_inst("vase", "vase", [0, 0, 1]), _inst("bowl", "bowl", [1, 0, 1])]
    entries = [_entry("c1", "vase", [0.4, 0, 1]), _entry("c2", "glass", [0.1, 0, 1]), _entry("c3", "bowl", [1.5, 0, 1]),
               _entry("c4", "book", [1.0, 0, 1])]
    dec = {"c1": {"action": "built", "object_id": "vase"}, "c2": {"action": "built", "object_id": "vase"},
           "c3": {"action": "built", "object_id": ["bowl"]}, "c4": {"action": "skipped", "reason": "x"}}
    assert snap.associate_decisions(insts, entries, dec) == {"vase": "c2", "bowl": "c3"}    # 不看类别、不设门槛
    assert snap.associate_decisions(insts, entries, dec, max_dist=0.3) == {"vase": "c2"}
    big = [_entry("c1", "vase", [0.1, 0, 1], (0.3, 0.1, 0.1))]
    assert snap.associate_decisions(insts, big, {"c1": {"action": "built", "object_id": "vase"}}, max_ratio=1.5) == {}


def test_moved_keeps_size_and_yaw():
    cup = _inst("cup", "cup", [0, 0, 0.8], (0.08, 0.06, 0.1), yaw=0.3)
    e = _entry("c1", "cup", [0.2, 0.1, 0.9], (0.12, 0.1, 0.2))
    m = snap.moved(cup, e)
    assert m["center"] == [0.2, 0.1, 0.9] and m["size"] == cup["size"] and m["yaw"] == cup["yaw"]
    assert m["object_id"] == "cup" and cup["center"] == [0.0, 0.0, 0.8]                      # 不改输入
    assert snap.moved(cup, e, z_mode="keep")["center"] == [0.2, 0.1, 0.8]


def test_moved_support_keeps_height_above_support():
    table = _inst("table", "table", [0, 0, 0.375], (1.0, 1.0, 0.75))
    shelf = _inst("shelf", "shelf", [2, 0, 0.5], (0.6, 0.4, 1.0))
    cup = _inst("cup", "cup", [0.3, 0, 0.75 + 0.01 + 0.05])                                  # 比桌面高 1 cm
    others = [table, shelf, cup]
    same = snap.moved(cup, _entry("c1", "cup", [0.1, 0.2, 0.83]), z_mode="support", others=others)
    assert np.allclose(same["center"], [0.1, 0.2, 0.81])                                    # 还在桌上：高度差照旧
    onto = snap.moved(cup, _entry("c1", "cup", [2.0, 0.1, 1.07]), z_mode="support", others=others)
    assert np.allclose(onto["center"], [2.0, 0.1, 1.0 + 0.01 + 0.05])                       # 挪到架子顶上
    far = snap.moved(cup, _entry("c1", "cup", [2.0, 0.1, 1.40]), z_mode="support", others=others)
    assert np.allclose(far["center"], [2.0, 0.1, 1.40])                                     # 条目底面离哪个面都远：按条目
    hung = _inst("clock", "clock", [0.3, 0.5, 1.6])                                         # 原来没有支撑：按条目
    assert np.allclose(snap.moved(hung, _entry("c1", "clock", [0.1, 0.5, 1.5]), z_mode="support",
                                  others=others)["center"], [0.1, 0.5, 1.5])


def test_box_mask_and_depth_residual():
    box = _inst("b", "box", [0, 2.0, 0], (0.2, 0.2, 0.2))
    m = snap.box_mask(box, _frame(), WH)
    assert m.shape == (80, 100) and m[40, 50] and not m[10, 10]
    assert 100 <= m.sum() <= 170                                                            # 前表面约 11 × 11 像素
    assert not snap.box_mask(_inst("b", "box", [0, -2.0, 0]), _frame(), WH).any()           # 在相机后面
    assert not snap.box_mask(_inst("b", "box", [5.0, 2.0, 0]), _frame(), WH).any()          # 出画
    assert snap.mask_iou(m, m) == 1.0 and snap.mask_iou(m, np.zeros_like(m)) == 0.0
    depth = np.full((80, 100), 1.9, np.float32)
    assert snap.depth_residual(box, _frame(), m, depth) < 1e-6                              # 前表面在框的深度范围里
    assert abs(snap.depth_residual(_inst("b", "box", [0, 2.5, 0], (0.2, 0.2, 0.2)), _frame(), m, depth) - 0.5) < 1e-6
    assert snap.depth_residual(box, _frame(), m, np.full((80, 100), np.nan)) is None


def test_evidence_accepts_only_when_overlap_improves():
    truth = _inst("t", "cup", [0.0, 2.0, 0.0], (0.2, 0.2, 0.2))
    views = [_view(truth, 0, 0.0), _view(truth, 20, 0.3)]
    off = _inst("cup", "cup", [0.25, 2.0, 0.0], (0.2, 0.2, 0.2))                            # 偏了 25 cm：图里对不上
    ev = snap.evidence(off, snap.moved(off, truth), views, WH)
    assert ev["n_frames"] == 2 and ev["iou_before"] < 0.05 and ev["iou_after"] > 0.95 and ev["depth_after"] < 1e-6
    assert snap.accept(ev)
    near = _inst("cup", "cup", [0.01, 2.0, 0.0], (0.2, 0.2, 0.2))                           # 本来就对着：提高不到 margin
    ev = snap.evidence(near, snap.moved(near, truth), views, WH)
    assert ev["gain"] < snap.MARGIN and not snap.accept(ev)
    assert snap.accept(ev, margin=0.0)                                                      # margin 是参数
    assert not snap.accept(snap.evidence(off, off, [], WH))                                 # 条目没有掩码：不挪
    assert not snap.accept(snap.evidence(off, snap.moved(off, truth), views[:1], WH), min_frames=2)


def test_accept_rejects_inconsistent_depth_and_wrong_entry_position():
    truth = _inst("t", "cup", [0.0, 2.0, 0.0], (0.2, 0.2, 0.2))
    views = [_view(truth, 0, 0.0)]
    off = _inst("cup", "cup", [0.25, 2.0, 0.0], (0.2, 0.2, 0.2))
    # 条目沿视线放远了 60 cm：投影还盖着掩码的一部分，但深度对不上
    deep = _entry("c1", "cup", [0.0, 2.6, 0.0], (0.2, 0.2, 0.2))
    ev = snap.evidence(off, snap.moved(off, deep), views, WH)
    assert ev["gain"] >= snap.MARGIN and ev["depth_after"] > 0.3
    assert not snap.accept(ev) and snap.accept(ev, depth_tol=None)
    # 条目的框不在自己掩码的位置上（比如被贴支撑面挪走了）：挪过去重合反而没有，拒绝
    wrong = _entry("c1", "cup", [0.0, 2.0, 0.6], (0.2, 0.2, 0.2))
    ev = snap.evidence(off, snap.moved(off, wrong), views, WH)
    assert ev["iou_after"] == 0.0 and not snap.accept(ev, depth_tol=None)
    assert snap.evidence(off, off, [_view(truth, depth=False)], WH)["depth_after"] is None  # 没有深度也能算


def test_snap_moves_accepted_small_and_leaves_the_rest():
    truth = _inst("t", "cup", [0.0, 2.0, 0.0], (0.2, 0.2, 0.2))
    cup = _inst("cup", "cup", [0.25, 2.0, 0.0], (0.18, 0.16, 0.2), yaw=0.2)                 # 要挪
    mug = _inst("mug", "cup", [1.0, 2.0, 0.0], (0.2, 0.2, 0.2))                             # 已经对着自己的条目
    sofa = _inst("sofa", "sofa", [0.3, 2.0, 0.0], (2.0, 0.9, 0.8))                          # 大件：pairs 里有也不动
    lamp = _inst("lamp", "lamp", [3.0, 2.0, 0.0])                                           # 没有对应
    mug_entry = _entry("c2", "cup", [1.01, 2.0, 0.0], (0.2, 0.2, 0.2))
    entries = [_entry("c1", "cup", truth["center"], (0.2, 0.2, 0.2)), mug_entry]
    views = {"c1": [_view(truth)], "c2": [_view(mug)]}
    insts = [cup, mug, sofa, lamp]
    cache = {}
    out, log = snap.snap(insts, entries, {"cup": "c1", "mug": "c2", "sofa": "c1"}, lambda e: views[e["item_id"]], WH,
                         cache=cache)
    assert [o["object_id"] for o in out] == ["cup", "mug", "sofa", "lamp"]
    assert out[0]["center"] == [0.0, 2.0, 0.0] and out[0]["size"] == cup["size"] and out[0]["yaw"] == cup["yaw"]
    assert out[1] is mug and out[2] is sofa and out[3] is lamp
    assert cup["center"] == [0.25, 2.0, 0.0]                                                # 不改输入
    assert [(l["object_id"], l["item_id"], l["accepted"]) for l in log] == [("cup", "c1", True), ("mug", "c2", False)]
    assert abs(log[0]["move_m"] - 0.25) < 1e-9 and set(cache) == {("cup", "c1", "entry"), ("mug", "c2", "entry")}
    out2, log2 = snap.snap(insts, entries, {"cup": "c1"}, lambda e: 1 / 0, WH, cache=cache)  # 用缓存，不再取掩码
    assert out2[0]["center"] == out[0]["center"] and len(log2) == 1
    out3, _ = snap.snap(insts, entries, {"cup": "c1"}, lambda e: views[e["item_id"]], WH, margin=2.0)
    assert out3[0] is cup                                                                   # 门槛过不了就原样


def test_entry_detections_and_views_of(tmp_path):
    hd_dir, masks = tmp_path / "hd", tmp_path / "masks"
    (hd_dir / "depth_moge").mkdir(parents=True)
    masks.mkdir()
    frames, index = [], []
    for k, (s, dx) in enumerate(((0, 0.0), (12, 0.01))):
        np.save(hd_dir / "depth_moge" / f"{s:06d}.npy", np.full((80, 100), 2.0, np.float32))
        frames.append({"source_frame": s, "K": K, "c2w": _c2w(dx).tolist()})
        m = np.zeros((80, 100), np.uint8)
        m[30:40, 40:60] = 255
        Image.fromarray(m).save(masks / f"m{k}.png")
        index.append({"frame": s, "label": "picture frame", "score": 0.8 - 0.1 * k, "mask": f"m{k}.png",
                      "box_xyxy": [40, 30, 60, 40]})
    far = np.zeros((80, 100), np.uint8)                                                     # 另一处的同类物体：单独一条
    far[60:70, 5:25] = 255
    Image.fromarray(far).save(masks / "far.png")
    index.append({"frame": 0, "label": "picture frame", "score": 0.6, "mask": "far.png", "box_xyxy": [5, 60, 25, 70]})
    tiny = np.zeros((80, 100), np.uint8)                                                    # 点太少：建清单时跳过，这里也跳过
    tiny[0:2, 0:2] = 255
    Image.fromarray(tiny).save(masks / "tiny.png")
    index.append({"frame": 0, "label": "cup", "score": 0.9, "mask": "tiny.png", "box_xyxy": [0, 0, 2, 2]})
    cams = {"size_wh": [100, 80], "frames": frames}
    (hd_dir / "cameras.json").write_text(json.dumps(cams))
    (masks / "index.json").write_text(json.dumps(index))
    det = snap.entry_detections(hd_dir, masks)
    assert sorted(det) == ["c000", "c001"]
    assert [d["mask"] for d in det["c000"]] == ["m0.png", "m1.png"] and [d["mask"] for d in det["c001"]] == ["far.png"]
    entry = {"item_id": "c000", "members": ["c000", "c001"]}                               # 并组：同一帧的掩码取并集
    cache = {}
    views = snap.views_of(entry, det, cams, masks, hd_dir / "depth_moge", cache)
    assert [v["frame"]["source_frame"] for v in views] == [0, 12]
    assert views[0]["mask"].sum() == 400 and views[1]["mask"].sum() == 200 and views[0]["depth"].shape == (80, 100)
    assert len(cache) == 2
    alone = snap.views_of({"item_id": "c001"}, det, cams, masks)                            # 没有 members 就是它自己
    assert len(alone) == 1 and alone[0]["depth"] is None and alone[0]["mask"].sum() == 200
