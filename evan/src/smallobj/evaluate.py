"""评测：按大小分档、一对一配对、每个真值物体的三种结局（设计文档 9.3、9.4 节）。

两套严格判据分开报：I = 3D IoU ≥ iou_strict；D = 归一化中心距离 d̂ ≤ dhat_strict 且最长边之比在 size_ratio 内。
宽松门槛（d̂ ≤ dhat_loose 或 IoU ≥ iou_loose）内但没过严格判据 = misplaced；连宽松门槛都没进 = missed。
"""
import numpy as np
from scipy.optimize import linear_sum_assignment

from smallobj import boxes

BINS = ("XS", "S", "M", "L")
# AHa-3D 的结构件：文档里写 architecture/…，作者的 office48 实际用 semantic_class "structure"、"floor"，
# 物体 ID 形如 structure/back_left、exterior/door。看类别和 ID 的第一段，任一在下面就算结构件。
STRUCTURAL_SEGMENTS = {"architecture", "structure", "floor", "ceiling", "wall", "exterior"}


def size_bin(rec, edges):
    longest = max(rec["size"])
    for name, edge in zip(BINS, edges):
        if longest < edge:
            return name
    return BINS[-1]


def dhat(pred, gt):
    half_diag = 0.5 * float(np.linalg.norm(gt["size"]))
    return float(np.linalg.norm(np.subtract(pred["center"], gt["center"]))) / half_diag


def _clip(subject, a, b):
    """Sutherland–Hodgman：用有向边 a→b 的左侧半平面裁剪凸多边形。"""
    out = []
    side = lambda p: (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    for i, cur in enumerate(subject):
        prev = subject[i - 1]
        sc, sp = side(cur), side(prev)
        if sc >= 0:
            if sp < 0:
                out.append(prev + (cur - prev) * (sp / (sp - sc)))
            out.append(cur)
        elif sp >= 0:
            out.append(prev + (cur - prev) * (sp / (sp - sc)))
    return out


def _area(poly):
    if len(poly) < 3:
        return 0.0
    p = np.asarray(poly)
    return 0.5 * abs(float(np.dot(p[:, 0], np.roll(p[:, 1], -1)) - np.dot(p[:, 1], np.roll(p[:, 0], -1))))


def iou3d(a, b):
    """只绕竖直轴转的框：底面凸多边形求交 × 竖直方向重叠。"""
    pa, pb = boxes.corners(a)[:4, :2], boxes.corners(b)[:4, :2]  # 逆时针的底面
    poly = list(pa)
    for i in range(4):
        poly = _clip(poly, pb[i], pb[(i + 1) % 4])
        if not poly:
            return 0.0
    za = (a["center"][2] - a["size"][2] / 2, a["center"][2] + a["size"][2] / 2)
    zb = (b["center"][2] - b["size"][2] / 2, b["center"][2] + b["size"][2] / 2)
    inter = _area(poly) * max(0.0, min(za[1], zb[1]) - max(za[0], zb[0]))
    va, vb = float(np.prod(a["size"])), float(np.prod(b["size"]))
    return inter / (va + vb - inter) if inter > 0 else 0.0


def _strict_I(p, g, th):
    return iou3d(p, g) >= th["iou_strict"]


def _strict_D(p, g, th):
    """判据 D：d̂ ≤ 0.5（或中心距离 ≤ strict_floor_m，10-27 G1 定为 10 cm；没有这个键时不设下限），且最长边之比在范围内。"""
    lo, hi = th["size_ratio"]
    ratio = max(p["size"]) / max(g["size"])
    near = dhat(p, g) <= th["dhat_strict"] or \
        np.linalg.norm(np.subtract(p["center"], g["center"])) <= th.get("strict_floor_m", 0.0)
    return near and lo <= ratio <= hi


def _size_log_ratio(p, g):
    return abs(float(np.log(max(p["size"]) / max(g["size"]))))


def _loose(p, g, th):
    """宽松门槛：位置大致对（d̂ 或 IoU），而且大小相当（最长边之比在 1/r 到 r 之间）。
    10-23 补尺寸条件：没有它，柜子里的一本书会被当成"柜子建坏了"，还把书从书的真值那里抢走。"""
    r = th.get("loose_size_ratio_max", float("inf"))
    if _size_log_ratio(p, g) > np.log(r):
        return False
    if th.get("loose_abs_m") and np.linalg.norm(np.subtract(p["center"], g["center"])) <= th["loose_abs_m"]:
        return True  # 绝对距离门槛：10-27 G1 起正式口径设 30 cm（之前只在敏感性分析里用）
    return dhat(p, g) <= th["dhat_loose"] or iou3d(p, g) >= th["iou_loose"]


def match(preds, gts, th):
    """匈牙利一对一配对，代价 = d̂ + |log(最长边之比)|，只保留过宽松门槛的对。返回 [(pred_idx, gt_idx)]。"""
    if not preds or not gts:
        return []
    big = 1e6
    cost = np.full((len(preds), len(gts)), big)
    for i, p in enumerate(preds):
        for j, g in enumerate(gts):
            if _loose(p, g, th):
                cost[i, j] = dhat(p, g) + _size_log_ratio(p, g)
    if th.get("match_mode", "hungarian") == "greedy":
        # 按代价从小到大取，两边都没用过的才配（不会为了多配一对把"建好了"拆成两个"建坏了"）
        pairs, used_p, used_g = [], set(), set()
        for i, j in sorted(zip(*np.nonzero(cost < big)), key=lambda ij: cost[ij]):
            if i not in used_p and j not in used_g:
                pairs.append((int(i), int(j)))
                used_p.add(i)
                used_g.add(j)
        return pairs
    rows, cols = linear_sum_assignment(cost)
    return [(int(i), int(j)) for i, j in zip(rows, cols) if cost[i, j] < big]


def outcomes(preds, gts, th):
    """每个真值物体一行：{"gt_id","category","bin","I","D","dhat","iou"}。"""
    pairs = {j: i for i, j in match(preds, gts, th)}
    rows = []
    for j, g in enumerate(gts):
        row = {"gt_id": g["object_id"], "category": g["category"], "bin": size_bin(g, th["bin_edges_m"]),
               "I": "missed", "D": "missed", "dhat": None, "iou": None}
        if j in pairs:
            p = preds[pairs[j]]
            row.update(I="correct" if _strict_I(p, g, th) else "misplaced",
                       D="correct" if _strict_D(p, g, th) else "misplaced",
                       dhat=dhat(p, g), iou=iou3d(p, g), pred_id=p["object_id"])
        rows.append(row)
    return rows


def _first(seg):
    return str(seg).split("/", 1)[0].split(":", 1)[-1].strip().lower()


def filter_predictions(preds, segments=STRUCTURAL_SEGMENTS):
    """去掉结构件预测（墙、地面、天花板、房梁、门洞等），见 STRUCTURAL_SEGMENTS。"""
    return [p for p in preds if _first(p.get("category", "")) not in segments and _first(p["object_id"]) not in segments]


def summarize(rows):
    """每档：个数、两套判据下的 correct / misplaced / missed 比例（recall = correct 比例）。"""
    out = {}
    for b in BINS:
        sub = [r for r in rows if r["bin"] == b]
        if not sub:
            continue
        d = {"n": len(sub)}
        for k in ("I", "D"):
            for o, name in (("correct", "recall"), ("misplaced", "misplaced"), ("missed", "missed")):
                d[f"{name}_{k}"] = sum(r[k] == o for r in sub) / len(sub)
        out[b] = d
    return out
