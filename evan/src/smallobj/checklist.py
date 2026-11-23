"""清单 v2 → 给 agent 的核对表（docs/plans/2026-10-29-scenerig-detection.md，11-20 定的做法）。

清单 v2 的条目大多是重复检测。这里只按几何整理，不看真值、不用 VLM：
- 同类别的重复按规则去掉（留分数最高的）；
- 不同类别叠在一起的不去掉，并成一组，当作一个核对项交给 agent：代表条目 = 组里分数最高的，其余类别列在 alt_labels；
- 一个框落在更大的框里面不算重叠（架子上的东西都在架子的框里）；
- 可选的尺寸上限 max_side：只留最长边 < max_side 的条目，大家具留给 agent 自己建。
"重叠" = 3D IoU > iou_min，或大小相当（最长边之比 ≤ size_ratio）且中心距离 < center_frac × 两个框里较短的那条对角线。
都返回新列表，不改输入。
"""
import numpy as np

from smallobj import evaluate


def _id(r):
    return r.get("item_id", r["object_id"])


def _score(r):
    return r.get("score", r.get("confidence", 0.0))


def _by_score(items: list) -> list:
    """分数从高到低，同分按 item_id：结果和输入顺序无关。"""
    return sorted(items, key=lambda r: (-_score(r), _id(r)))


def overlaps(a, b, iou_min: float = 0.25, center_frac: float = 0.5, size_ratio=3.0) -> bool:
    """两个框是不是同一处的东西：3D IoU > iou_min；或者大小相当（最长边之比 ≤ size_ratio，None 不设）
    且中心距离 < center_frac × 较短的对角线（center_frac = 0 关掉这一条）。
    尺寸条件是为了"在更大的框里面"不算：书正好在架子框的中心时，中心距离是 0，但不是同一个东西。"""
    d = float(np.linalg.norm(np.subtract(a["center"], b["center"])))
    da, db = float(np.linalg.norm(a["size"])), float(np.linalg.norm(b["size"]))
    la, lb = max(a["size"]), max(b["size"])
    if d < center_frac * min(da, db) and (size_ratio is None or max(la, lb) <= size_ratio * min(la, lb)):
        return True
    if d >= (da + db) / 2:  # 外接球都不相交，IoU 一定是 0，省掉多边形求交
        return False
    return evaluate.iou3d(a, b) > iou_min


def limit_side(items: list, max_side=None) -> list:
    """只留最长边 < max_side 的条目（和分档、route_rule 一样用 <）；max_side=None 不筛。"""
    return [r for r in items if max_side is None or max(r["size"]) < max_side]


def dedupe_same_label(items: list, iou_min: float = 0.25, center_frac: float = 0.5, size_ratio=3.0) -> list:
    """同类去重：按分数从高到低，和已留下的某个同类条目重叠（见 overlaps）的去掉。返回留下的条目，分数从高到低。"""
    kept = {}
    out = []
    for r in _by_score(items):
        same = kept.setdefault(r["category"], [])
        if any(overlaps(k, r, iou_min, center_frac, size_ratio) for k in same):
            continue
        same.append(r)
        out.append(r)
    return out


def group_overlapping(items: list, iou_min: float = 0.25, center_frac: float = 0.5, size_ratio=3.0) -> list:
    """重叠的条目并成组：按分数从高到低，和已有某组的代表（组里第一个，分数最高）重叠就进那一组，
    和多个代表重叠时进分数最高的那一组；都不重叠就自己开一组。只跟代表比，不连锁（a–b、b–c 重叠不会把 c 拉进 a 的组）。
    同类去重之后再调用时，和代表重叠的一定是别的类别。返回 [[代表, 成员, …]]，组按代表的分数从高到低。"""
    groups = []
    for r in _by_score(items):
        for g in groups:
            if overlaps(g[0], r, iou_min, center_frac, size_ratio):
                g.append(r)
                break
        else:
            groups.append([r])
    return groups


def entry(group: list) -> dict:
    """一组 → 一个核对项。前五个键是 item_id（代表条目的 item_id，和原清单、按 item_id 存的掩码对得上）、
    label（代表的类别）、alt_labels（其余成员里不同于 label 的类别，按成员分数从高到低，不重复）、
    n_members（组里条目数，含代表）、members（成员的 item_id，代表在最前）；
    后面是代表条目原样的全部键（object_id、category、center、yaw、size、confidence、source、score、best_frame、
    bbox2d_xyxy、n_frames、det_sources、n_views、settled_on，有的还有 same_size_group），所以核对项仍可当清单条目用。"""
    rep = group[0]
    alt = []
    for m in group[1:]:
        if m["category"] != rep["category"] and m["category"] not in alt:
            alt.append(m["category"])
    out = {"item_id": _id(rep), "label": rep["category"], "alt_labels": alt, "n_members": len(group),
           "members": [_id(m) for m in group]}
    out.update({k: list(v) if isinstance(v, list) else v for k, v in rep.items() if k != "item_id"})
    return out


def build(items: list, iou_min: float = 0.25, center_frac: float = 0.5, max_side=None, size_ratio=3.0,
          cross_label: bool = True) -> list:
    """清单条目 → 核对表：先按 max_side 筛（大框先去掉，不拿它去重别的），再同类去重，再把不同类别重叠的并组。
    cross_label=False 时不并组，每个留下的条目各自一项（只做同类去重的对照）。
    输出顺序：代表条目的 score 从高到低，同分按 item_id；和输入顺序无关。每项的键见 entry。"""
    kept = dedupe_same_label(limit_side(items, max_side), iou_min, center_frac, size_ratio)
    groups = group_overlapping(kept, iou_min, center_frac, size_ratio) if cross_label else [[r] for r in kept]
    return [entry(g) for g in groups]


def export_crops(scene_id: str, list_name: str = "inventory_v2_list.json", root=None):
    """逐项清单每一条在最好那一帧的投影框（四周留 15%）裁一张图：perception/<id>/inventory_v2_crops/<item_id>.jpg。
    和 inventory.export_crops 一样的裁法，单独一个目录：清单 v2 的 item_id 会和 Boxer 清单的撞名。"""
    import json
    from pathlib import Path

    from PIL import Image
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    P = root / "perception" / scene_id
    out = P / "inventory_v2_crops"
    out.mkdir(exist_ok=True)
    for it in json.loads((P / list_name).read_text()):
        if it.get("best_frame") is None or not it.get("bbox2d_xyxy"):
            continue
        im = Image.open(P / "hd" / "frames" / f"{int(it['best_frame']):06d}.png")
        x0, y0, x1, y1 = it["bbox2d_xyxy"]
        mx, my = 0.15 * (x1 - x0), 0.15 * (y1 - y0)
        box = (max(0, int(x0 - mx)), max(0, int(y0 - my)), min(im.width, int(x1 + mx) + 1), min(im.height, int(y1 + my) + 1))
        if box[2] - box[0] >= 2 and box[3] - box[1] >= 2:
            im.crop(box).convert("RGB").save(out / f"{it['item_id']}.jpg", quality=90)
    return out
