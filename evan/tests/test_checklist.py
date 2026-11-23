import copy
import json
import random

from smallobj import boxes, checklist


def _item(i, label, center, size, score, yaw=0.0, **extra):
    """和 inventory_v2.json 里的条目同样的键。"""
    r = boxes.record(f"c{i:03d}", label, center, yaw, size, confidence=score, source="clean")
    r.update(item_id=r["object_id"], score=score, best_frame=10 * i, bbox2d_xyxy=[0.0, 0.0, 10.0, 10.0],
             n_frames=1 + i, det_sources=["full"], n_views=2, settled_on=None)
    r.update(extra)
    return r


def _ids(entries):
    return [e["item_id"] for e in entries]


def test_same_label_duplicate_by_iou_is_dropped():
    items = [_item(0, "cup", (1.00, 2.00, 0.80), (0.08, 0.08, 0.10), 0.9),
             _item(1, "cup", (1.01, 2.00, 0.80), (0.08, 0.08, 0.10), 0.7),   # 和 c000 几乎重合
             _item(2, "cup", (1.50, 2.00, 0.80), (0.08, 0.08, 0.10), 0.6)]   # 另一个杯子
    out = checklist.build(items)
    assert _ids(out) == ["c000", "c002"]
    assert all(e["n_members"] == 1 and e["alt_labels"] == [] for e in out)


def test_same_label_duplicate_by_centre_distance_is_dropped():
    # 同一本书的两个框：一个拟薄了，IoU 只有 0.2，但中心只差 1 cm
    items = [_item(0, "book", (0.0, 0.0, 0.50), (0.30, 0.20, 0.05), 0.9),
             _item(1, "book", (0.0, 0.0, 0.51), (0.30, 0.20, 0.01), 0.5)]
    assert _ids(checklist.build(items, iou_min=0.25, center_frac=0.5)) == ["c000"]
    assert _ids(checklist.dedupe_same_label(items, iou_min=0.25, center_frac=0.5)) == ["c000"]
    # 关掉中心距离这一条就留下两个
    assert _ids(checklist.build(items, iou_min=0.25, center_frac=0.0)) == ["c000", "c001"]


def test_same_label_neighbours_are_kept():
    # 并排的两本书：不重叠，中心相距 0.25 m > 0.5 × 对角线（0.36 m）的一半
    items = [_item(0, "book", (0.00, 0.0, 0.5), (0.30, 0.20, 0.05), 0.9),
             _item(1, "book", (0.00, 0.25, 0.5), (0.30, 0.20, 0.05), 0.8)]
    assert _ids(checklist.build(items)) == ["c000", "c001"]


def test_higher_score_survives_whatever_the_input_order():
    items = [_item(0, "cup", (1.00, 2.00, 0.80), (0.08, 0.08, 0.10), 0.4),
             _item(1, "cup", (1.01, 2.00, 0.80), (0.08, 0.08, 0.10), 0.7)]
    assert _ids(checklist.build(items)) == ["c001"]


def test_different_labels_overlapping_are_grouped_not_dropped():
    items = [_item(0, "notebook", (0.0, 0.0, 0.5), (0.30, 0.20, 0.03), 0.6),
             _item(1, "book", (0.01, 0.0, 0.5), (0.30, 0.20, 0.03), 0.9),
             _item(2, "magazine", (0.0, 0.01, 0.5), (0.30, 0.20, 0.03), 0.5),
             _item(3, "cup", (2.0, 0.0, 0.5), (0.08, 0.08, 0.10), 0.8)]
    out = checklist.build(items)
    assert _ids(out) == ["c001", "c003"]
    e = out[0]
    assert e["label"] == "book" and e["category"] == "book"
    assert e["alt_labels"] == ["notebook", "magazine"]       # 按成员分数从高到低
    assert e["members"] == ["c001", "c000", "c002"] and e["n_members"] == 3
    # 框和证据都是代表条目原样的
    rep = items[1]
    for k in ("object_id", "center", "yaw", "size", "confidence", "source", "score", "best_frame", "bbox2d_xyxy",
              "n_frames", "det_sources", "n_views", "settled_on"):
        assert e[k] == rep[k], k
    assert out[1]["label"] == "cup" and out[1]["alt_labels"] == [] and out[1]["members"] == ["c003"]


def test_group_lists_each_alternative_label_once():
    items = [_item(0, "book", (0.0, 0.0, 0.5), (0.30, 0.20, 0.04), 0.9),
             _item(1, "notebook", (0.0, 0.0, 0.52), (0.30, 0.20, 0.04), 0.6),    # 和 book 重叠
             _item(2, "notebook", (0.0, 0.0, 0.48), (0.30, 0.20, 0.04), 0.5)]    # 也和 book 重叠
    out = checklist.build(items, iou_min=0.25, center_frac=0.0)   # 两个 notebook 互相 IoU = 0 不算重复
    assert len(out) == 1 and out[0]["n_members"] == 3 and out[0]["alt_labels"] == ["notebook"]


def test_grouping_is_against_the_representative_only():
    # a–b 重叠、b–c 重叠、a–c 不重叠：c 不跟着 b 并进 a 的组（不连锁）
    items = [_item(0, "tray", (0.00, 0.0, 0.5), (0.30, 0.30, 0.05), 0.9),
             _item(1, "plate", (0.12, 0.0, 0.5), (0.30, 0.30, 0.05), 0.8),
             _item(2, "bowl", (0.24, 0.0, 0.5), (0.30, 0.30, 0.05), 0.7)]
    out = checklist.build(items, iou_min=0.25, center_frac=0.0)
    assert [e["members"] for e in out] == [["c000", "c001"], ["c002"]]


def test_cross_label_off_keeps_overlapping_labels_as_separate_entries():
    items = [_item(0, "book", (0.0, 0.0, 0.5), (0.30, 0.20, 0.03), 0.9),
             _item(1, "notebook", (0.0, 0.0, 0.5), (0.30, 0.20, 0.03), 0.6)]
    out = checklist.build(items, cross_label=False)
    assert _ids(out) == ["c000", "c001"] and all(e["n_members"] == 1 for e in out)


def test_containment_is_not_dropped_or_grouped():
    # 架子上的东西都在架子的框里面：不去掉，也不和架子并成一组
    items = [_item(0, "shelf", (0.0, 0.0, 1.0), (1.0, 0.3, 2.0), 0.9),
             _item(1, "book", (0.0, 0.0, 1.0), (0.20, 0.15, 0.03), 0.5),      # 正好在架子框的中心
             _item(2, "vase", (0.3, 0.0, 1.6), (0.10, 0.10, 0.25), 0.4)]      # 架子框里的另一处
    for kw in ({}, {"iou_min": 0.15, "center_frac": 0.5}, {"iou_min": 0.4, "center_frac": 0.35}):
        out = checklist.build(items, **kw)
        assert _ids(out) == ["c000", "c001", "c002"] and all(e["n_members"] == 1 for e in out)


def test_same_label_containment_is_not_dropped():
    # 同类的小框在大框里面（层板、一个格子）也不去掉
    items = [_item(0, "shelf", (0.0, 0.0, 1.0), (1.0, 0.3, 2.0), 0.9),
             _item(1, "shelf", (0.0, 0.0, 0.4), (0.9, 0.28, 0.03), 0.3),      # 一块层板
             _item(2, "shelf", (0.0, 0.0, 1.0), (0.3, 0.28, 0.3), 0.2)]       # 一个格子，中心和大框重合
    assert _ids(checklist.dedupe_same_label(items)) == ["c000", "c001", "c002"]
    assert _ids(checklist.build(items)) == ["c000", "c001", "c002"]


def test_overlaps_rule():
    a = _item(0, "a", (0, 0, 0), (0.4, 0.4, 0.4), 0.9)
    assert checklist.overlaps(a, _item(1, "b", (0.05, 0, 0), (0.4, 0.4, 0.4), 0.5), iou_min=0.25, center_frac=0.0)
    assert not checklist.overlaps(a, _item(1, "b", (0.3, 0, 0), (0.4, 0.4, 0.4), 0.5), iou_min=0.25, center_frac=0.0)
    assert not checklist.overlaps(a, _item(1, "b", (5.0, 0, 0), (0.4, 0.4, 0.4), 0.5))
    # 中心距离 0.3 m：对角线 0.69 m，取 0.5 时算重叠，取 0.35 时不算
    b = _item(1, "b", (0.3, 0, 0), (0.4, 0.4, 0.4), 0.5)
    assert checklist.overlaps(a, b, iou_min=0.9, center_frac=0.5)
    assert not checklist.overlaps(a, b, iou_min=0.9, center_frac=0.35)
    # 大小差太多（最长边之比 > size_ratio）时中心距离这一条不算
    small = _item(2, "c", (0, 0, 0), (0.05, 0.05, 0.05), 0.5)
    assert not checklist.overlaps(a, small, iou_min=0.25, center_frac=0.5, size_ratio=3.0)
    assert checklist.overlaps(a, small, iou_min=0.25, center_frac=0.5, size_ratio=None)


def test_max_side():
    items = [_item(0, "sofa", (0.0, 0.0, 0.4), (2.0, 0.9, 0.8), 0.9),
             _item(1, "chair", (3.0, 0.0, 0.4), (0.5, 0.5, 0.9), 0.8),
             _item(2, "cup", (5.0, 0.0, 0.8), (0.08, 0.08, 0.10), 0.7),
             _item(3, "box", (7.0, 0.0, 0.25), (0.5, 0.3, 0.3), 0.6)]
    assert _ids(checklist.build(items)) == ["c000", "c001", "c002", "c003"]
    assert _ids(checklist.build(items, max_side=1.5)) == ["c001", "c002", "c003"]
    assert _ids(checklist.build(items, max_side=0.5)) == ["c002"]           # 最长边 < max_side 才留（0.5 不留）
    assert _ids(checklist.limit_side(items, 0.5)) == ["c002"] and len(checklist.limit_side(items, None)) == 4


def test_max_side_is_applied_before_dedup():
    # 高分的大框被尺寸上限去掉了，就不能再把同类的小框当重复去掉
    items = [_item(0, "cushion", (0.0, 0.0, 0.5), (0.55, 0.45, 0.15), 0.9),
             _item(1, "cushion", (0.0, 0.0, 0.5), (0.45, 0.45, 0.15), 0.6)]
    assert _ids(checklist.build(items)) == ["c000"]
    assert _ids(checklist.build(items, max_side=0.5)) == ["c001"]


def test_deterministic_and_does_not_touch_input():
    rng = random.Random(0)
    items = []
    for i in range(40):
        c = (rng.uniform(0, 1.0), rng.uniform(0, 1.0), rng.uniform(0, 0.5))
        s = (rng.uniform(0.05, 0.4), rng.uniform(0.05, 0.4), rng.uniform(0.05, 0.4))
        items.append(_item(i, rng.choice(["cup", "book", "box"]), c, s, rng.choice([0.5, 0.6, 0.7, 0.8]),
                           yaw=rng.uniform(-3, 3)))
    before = copy.deepcopy(items)
    ref = checklist.build(items, iou_min=0.15, center_frac=0.35, max_side=0.39)
    assert items == before
    assert 1 < len(ref) < len(items) and any(e["n_members"] > 1 for e in ref)
    for seed in range(5):
        shuffled = copy.deepcopy(items)
        random.Random(seed).shuffle(shuffled)
        assert checklist.build(shuffled, iou_min=0.15, center_frac=0.35, max_side=0.39) == ref
    # 输出顺序：代表条目的分数从高到低，同分按 item_id
    keys = [(-e["score"], e["item_id"]) for e in ref]
    assert keys == sorted(keys)
    # 每个留下的条目只出现在一个组里；改输出不会改到输入
    members = [m for e in ref for m in e["members"]]
    assert len(members) == len(set(members))
    ref[0]["center"][0] += 1.0
    assert items == before
    json.dumps(ref)


def test_entry_fields():
    items = [_item(0, "chair", (0.0, 0.0, 0.45), (0.5, 0.5, 0.9), 0.8, same_size_group="chair", settled_on="floor")]
    e = checklist.build(items)[0]
    assert list(e)[:5] == ["item_id", "label", "alt_labels", "n_members", "members"]
    assert e["same_size_group"] == "chair" and e["settled_on"] == "floor" and e["source"] == "clean"
    assert {k: e[k] for k in items[0]} == items[0]          # 清单条目的键原样都在
    assert checklist.build([]) == []
