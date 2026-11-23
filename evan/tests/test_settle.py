from smallobj import boxes, settle


def _r(iid, cat, cx, cy, z_bottom, l, w, h, yaw=0.0):
    r = boxes.record(iid, cat, [cx, cy, z_bottom + h / 2], yaw, [l, w, h], source="clean")
    r["item_id"] = iid
    return r


def _bottom(r):
    return round(r["center"][2] - r["size"][2] / 2, 6)


def test_settle_onto_supports():
    # 借 SceneRig：按支撑顺序放下，穿进去的往上抬到顶面；这里是几何版（不跑物理仿真）
    items = [_r("table", "table", 0, 0, 0.0, 1.0, 1.0, 0.75),
             _r("cup", "cup", 0.2, 0.1, 0.80, 0.08, 0.08, 0.10),        # 悬在桌面上方 5 cm → 落到桌面
             _r("book", "book", -0.2, 0.0, 0.71, 0.25, 0.18, 0.04),     # 穿进桌面 4 cm → 抬到桌面
             _r("mug", "mug", -0.2, 0.0, 0.80, 0.08, 0.08, 0.10),       # 叠在书上：跟着书走，落到书顶 0.79
             _r("toy", "toy", 2.0, 2.0, 0.08, 0.2, 0.2, 0.2),           # 离地 8 cm → 落地
             _r("outlet", "power outlet", 3.0, 0.0, 0.30, 0.08, 0.02, 0.12),  # 墙上，离地 30 cm、下面没东西 → 不动
             _r("sofa", "sofa", 5.0, 0.0, 0.10, 2.0, 0.9, 0.8)]         # 大物体不动
    out = {r["item_id"]: r for r in settle.settle(items)}
    assert _bottom(out["cup"]) == 0.75 and out["cup"]["settled_on"] == "table"
    assert _bottom(out["book"]) == 0.75 and out["book"]["settled_on"] == "table"
    assert _bottom(out["mug"]) == 0.79 and out["mug"]["settled_on"] == "book"
    assert _bottom(out["toy"]) == 0.0 and out["toy"]["settled_on"] == "floor"
    assert _bottom(out["outlet"]) == 0.30 and out["outlet"]["settled_on"] is None
    assert _bottom(out["sofa"]) == 0.10 and out["sofa"]["settled_on"] is None
    assert _bottom(items[1]) == 0.80   # 不改输入


def test_settle_respects_rotated_footprint():
    # 支撑面按旋转后的足迹判断：转了 45° 的细长架子，角落外面的点不算在它上面
    shelf = _r("shelf", "shelf", 0, 0, 0.0, 2.0, 0.3, 1.0, yaw=0.785398)
    on = _r("vase", "vase", 0.5, 0.5, 1.05, 0.1, 0.1, 0.2)      # 在架子的长轴上
    off = _r("cup", "cup", 0.6, -0.6, 1.05, 0.1, 0.1, 0.1)      # 在架子旁边
    out = {r["item_id"]: r for r in settle.settle([shelf, on, off])}
    assert out["vase"]["settled_on"] == "shelf" and out["cup"]["settled_on"] is None


def test_same_size_groups():
    # 借 SceneRig：同类、尺寸相近的 ≥ 3 个共用中位尺寸；食物、植物、软物不做；差太多的不进组
    mugs = [_r(f"m{k}", "mug", k, 0, 0.75, s, s * 0.9, 0.1) for k, s in enumerate((0.09, 0.10, 0.12))]
    big = _r("m9", "mug", 9, 0, 0.75, 0.40, 0.35, 0.3)
    lamps = [_r(f"l{k}", "lamp", k, 5, 0.0, 0.3 + 0.1 * k, 0.3, 0.6) for k in range(2)]
    fruit = [_r(f"f{k}", "fruit", k, 9, 0.75, 0.06 + 0.02 * k, 0.06, 0.06) for k in range(3)]
    out = {r["item_id"]: r for r in settle.same_size(mugs + [big] + lamps + fruit)}
    assert all(abs(out[f"m{k}"]["size"][0] - 0.10) < 1e-9 for k in range(3))
    assert out["m0"]["same_size_group"] == "mug" and "same_size_group" not in out["m9"]
    assert out["m9"]["size"] == [0.40, 0.35, 0.3]
    assert out["l0"]["size"] == lamps[0]["size"] and out["f0"]["size"] == fruit[0]["size"]
