"""清单 v2 的两个几何后处理（借 SceneRig，`docs/research/05-scenerig.md`）。

- settle：小物体贴到正下方的支撑面（地面 z=0 或足迹更大的物体顶面），穿进去的往上抬到顶面；按底面从低到高处理，
  叠放的物体跟着下面的走。SceneRig 用 Isaac 做重力沉降，这里只做几何版。
- same_size：同类、尺寸相近的 ≥ 3 个物体共用中位尺寸（SceneRig 的自动发现也要 ≥ 3 个，排除食物、植物、软物）。
都返回新列表，不改输入。
"""
import numpy as np

from smallobj import boxes

FLOOR_Z = 0.0  # AHa-3D 对齐后的房间坐标里地面在 z = 0（同 p0.FLOOR_Z）
NOT_SAME_SIZE = {"fruit", "vegetable", "food", "bread", "plant", "potted plant", "flower", "leaf", "stone",
                 "towel", "cloth", "clothes", "blanket", "pillow", "cushion", "bag", "rug", "curtain", "napkin"}


def _copy(r):
    return {**r, "center": list(r["center"]), "size": list(r["size"])}


def _bottom(r):
    return r["center"][2] - r["size"][2] / 2


def _on_footprint(support, x, y):
    lx, ly, _ = boxes.to_local(support, [[x, y, support["center"][2]]])[0]
    return abs(lx) <= support["size"][0] / 2 and abs(ly) <= support["size"][1] / 2


def settle(items: list, floor_z: float = FLOOR_Z, max_longest: float = 0.5, max_gap: float = 0.15,
           max_pen: float = 0.10) -> list:
    """最长边 < max_longest 的物体：在中心正下方找顶面落在 [底面 − max_gap, 底面 + max_pen] 里、足迹比它大的物体，
    取最高的那个顶面贴上去；没有就看地面在不在这个范围里。都不在（挂在墙上、离支撑面太远）就不动。
    每条加 settled_on：支撑物的 item_id、"floor" 或 None。"""
    out = [_copy(r) for r in items]
    for r in out:
        r["settled_on"] = None
    for i in sorted(range(len(out)), key=lambda i: _bottom(out[i])):
        r = out[i]
        if max(r["size"]) >= max_longest:
            continue
        bottom, area = _bottom(r), r["size"][0] * r["size"][1]
        best, best_top = None, None
        for j, s in enumerate(out):
            if j == i or s["size"][0] * s["size"][1] <= area:
                continue
            top = s["center"][2] + s["size"][2] / 2
            if bottom - max_gap <= top <= bottom + max_pen and _on_footprint(s, *r["center"][:2]) \
                    and (best_top is None or top > best_top):
                best, best_top = s.get("item_id", s["object_id"]), top
        if best is None and bottom - max_gap <= floor_z <= bottom + max_pen:
            best, best_top = "floor", floor_z
        if best is not None:
            r["center"][2] = best_top + r["size"][2] / 2
            r["settled_on"] = best
    return out


def same_size(items: list, min_members: int = 3, max_ratio: float = 1.5, exclude=NOT_SAME_SIZE) -> list:
    """按类别分组；和组内中位尺寸（长边、短边、高）每一维都差不到 max_ratio 倍的算组员，组员 ≥ min_members 时
    都改成组员的中位尺寸（保留各自哪一边是长边）。组员加 same_size_group = 类别。"""
    out = [_copy(r) for r in items]
    by_cat = {}
    for r in out:
        by_cat.setdefault(r["category"], []).append(r)
    for cat, rs in by_cat.items():
        if cat in exclude or len(rs) < min_members:
            continue
        dims = np.array([[max(r["size"][:2]), min(r["size"][:2]), r["size"][2]] for r in rs])
        med = np.median(dims, 0)
        ok = np.all(np.maximum(dims / med, med / dims) <= max_ratio, axis=1)
        if ok.sum() < min_members:
            continue
        L, W, H = np.median(dims[ok], 0)
        for r, keep in zip(rs, ok):
            if keep:
                r["size"] = [float(L), float(W), float(H)] if r["size"][0] >= r["size"][1] else [float(W), float(L), float(H)]
                r["same_size_group"] = cat
    return out
