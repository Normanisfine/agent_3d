"""交接记录：一次运行里每个算分的实例一条（`<run>/objects.json`），给下游的物理仿真用；外加"没配上真值的实例"核对表用到的几何。

实例列表和打分用的是同一份：`export/objects.json` 过 `evaluate.filter_predictions`（去结构件）。框不做任何变换，
就是 .blend 自己的坐标系（AHa-3D 对齐后的房间坐标，z 向上，地面 z = 0），约定同 `boxes.record`。

- 支撑关系只看框（思路同 `settle.settle`，但不挪东西、不限物体大小）：底面落在另一个实例顶面的
  [−SUPPORT_PEN_M, +SUPPORT_GAP_M] 里、两个水平足迹的交叠 ≥ 自己足迹的 SUPPORT_MIN_OVERLAP、对方中心低于自己底面，
  取顶面最高的那个；没有就看地面 z = 0 在不在同一个范围里；都不是记 None（挂墙、吊顶，或者放在框表示不出来的面上：
  沙发坐垫、柜子里的隔板、窗台）。结构件（墙、地面、窗台）的框常常是空心的整圈，不当支撑物。
- 源帧：框的 8 个角投到 `perception/<scene>/hd` 的每一帧，按画面内的外接框面积取前几帧（不判断遮挡）。
"""
import json
from pathlib import Path

import numpy as np

from smallobj import boxes, evaluate, hd
from smallobj.settle import FLOOR_Z

PROJ = Path(__file__).resolve().parents[2]
VERSION = "handoff-1"
SUPPORT_GAP_M = 0.03        # 底面最多比支撑面高这么多
SUPPORT_PEN_M = 0.03        # 底面最多陷进支撑面这么多
SUPPORT_MIN_OVERLAP = 0.25  # 足迹交叠面积 / 自己的足迹面积
N_VIEWS = 3
NEAR_M = 0.05               # 相机前方不到 5 cm 的部分不画（同 hd.project_box）


def _bottom(r):
    return r["center"][2] - r["size"][2] / 2


def _top(r):
    return r["center"][2] + r["size"][2] / 2


def footprint_overlap(a, b) -> float:
    """两个框的水平足迹（旋转矩形）交叠面积，m²。裁剪用 evaluate 里算 IoU 的那一套。"""
    poly, pb = list(boxes.corners(a)[:4, :2]), boxes.corners(b)[:4, :2]
    for i in range(4):
        poly = evaluate._clip(poly, pb[i], pb[(i + 1) % 4])
        if not poly:
            return 0.0
    return evaluate._area(poly)


def supports(recs: list, floor_z: float = FLOOR_Z, max_gap: float = SUPPORT_GAP_M, max_pen: float = SUPPORT_PEN_M,
             min_overlap: float = SUPPORT_MIN_OVERLAP) -> list:
    """每个框放在谁上面。返回和 recs 等长的列表：{"support": 实例 id / "floor" / None, "gap_m", "overlap"}。

    gap_m = 自己的底面 − 支撑面（负数是陷进去）；overlap = 足迹交叠 / 自己的足迹（地面记 1.0）；没有支撑时两个都是 None。
    对方中心必须低于自己的底面：两块叠在同一高度的地毯不会互相当支撑，关系里也不会有环。
    """
    out = []
    for i, r in enumerate(recs):
        bottom, area = _bottom(r), r["size"][0] * r["size"][1]
        best = None  # (顶面高度, 交叠比例, id)
        for j, s in enumerate(recs):
            if j == i or s["center"][2] >= bottom or not -max_pen <= bottom - _top(s) <= max_gap:
                continue
            frac = footprint_overlap(r, s) / area
            if frac >= min_overlap and (best is None or (_top(s), frac) > best[:2]):
                best = (_top(s), frac, s["object_id"])
        if best is not None:
            out.append({"support": best[2], "gap_m": float(bottom - best[0]), "overlap": float(min(best[1], 1.0))})
        elif -max_pen <= bottom - floor_z <= max_gap:
            out.append({"support": "floor", "gap_m": float(bottom - floor_z), "overlap": 1.0})
        else:
            out.append({"support": None, "gap_m": None, "overlap": None})
    return out


def inside(recs: list, lift: float = 0.01) -> list:
    """底面中心（抬高 lift）落在哪个更大的实例的框里：取体积最小的那个的 id，没有就是 None。
    支撑是 None 的时候用来区分"放在别人的框里面"（沙发上的靠垫、柜子里的东西）和真的悬空 / 挂墙。"""
    vol = [float(np.prod(r["size"])) for r in recs]
    out = []
    for i, r in enumerate(recs):
        pt = [[r["center"][0], r["center"][1], _bottom(r) + lift]]
        hit = [j for j, s in enumerate(recs) if j != i and vol[j] > vol[i] and boxes.contains(s, pt)[0]]
        out.append(recs[min(hit, key=lambda j: vol[j])]["object_id"] if hit else None)
    return out


def select_views(rec: dict, cams: dict, k: int = N_VIEWS) -> list:
    """框在画面内的外接框面积最大的 k 帧（面积相同取帧号小的）；完全出画或在相机后面的帧不要。

    每帧：{"frame", "bbox_xyxy"（裁到画面内）, "area_px", "truncation"（1 − 画面内面积 / 外接框面积）}。
    """
    W, H = cams["size_wh"]
    views = []
    for f in cams["frames"]:
        xyxy, trunc = hd.project_box(rec, f, cams["size_wh"])
        if xyxy is None:
            continue
        x0, y0, x1, y1 = max(xyxy[0], 0.0), max(xyxy[1], 0.0), min(xyxy[2], float(W)), min(xyxy[3], float(H))
        area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
        if area <= 0:
            continue
        views.append({"frame": int(f["source_frame"]), "bbox_xyxy": [round(v, 1) for v in (x0, y0, x1, y1)],
                      "area_px": round(area, 1), "truncation": round(trunc, 3)})
    views.sort(key=lambda v: (-v["area_px"], v["frame"]))
    return views[:k]


def visible_fraction(rec: dict, frame: dict, size_wh, depth, margin: float = 0.15, grid: int = 24) -> float:
    """这一帧里框没被挡住的比例：外接框（裁到画面内）上取 grid × grid 个点，深度图（hd/depth，房间尺度）在那里
    比框最近的角还近 margin 以上的算被挡住；深度无效（NaN）按可见算。框不在画面里返回 0.0。
    只用来挑核对图的那一帧（隔着墙投影很大的帧不要），交接记录里的 views 不用它。"""
    xyxy, _ = hd.project_box(rec, frame, size_wh)
    if xyxy is None:
        return 0.0
    W, H = size_wh
    x0, y0, x1, y1 = max(xyxy[0], 0.0), max(xyxy[1], 0.0), min(xyxy[2], float(W)), min(xyxy[3], float(H))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    w2c = np.linalg.inv(np.asarray(frame["c2w"], float))
    z = (boxes.corners(rec) @ w2c[:3, :3].T + w2c[:3, 3])[:, 2]
    z_near = float(z[z > NEAR_M].min())
    us = np.clip(np.linspace(x0, x1, grid + 2)[1:-1].astype(int), 0, W - 1)
    vs = np.clip(np.linspace(y0, y1, grid + 2)[1:-1].astype(int), 0, H - 1)
    d = np.asarray(depth)[np.ix_(vs, us)]
    return float(np.mean(~np.isfinite(d) | (d >= z_near - margin)))


def inventory_ties(decisions: dict) -> dict:
    """inventory_decisions.json（{清单条目 id: {"action", "object_id", ...}}）→ {实例 id: [清单条目 id, ...]}。
    只算带 object_id 的条目（built；几条重复检测可以指向同一个实例）。"""
    ties = {}
    for item_id, d in decisions.items():
        oid = d.get("object_id") if isinstance(d, dict) else None
        for o in (oid if isinstance(oid, list) else [oid]):
            if o:
                ties.setdefault(str(o), []).append(item_id)
    return ties


def unmatched(counted: list, rows: list) -> list:
    """算分的实例里没配上任何真值的（score_*.json 的 rows 里没有哪一行的 pred_id 是它），顺序同 counted。"""
    used = {r["pred_id"] for r in rows if r.get("pred_id") is not None}
    return [p for p in counted if p["object_id"] not in used]


def project_edges(rec: dict, frame: dict, near: float = NEAR_M) -> list:
    """框的 12 条棱投到这一帧，返回 [((u0, v0), (u1, v1)), ...]；穿过相机平面的棱在 z = near 处截断，整条在后面的不要。"""
    K = np.asarray(frame["K"], float)
    w2c = np.linalg.inv(np.asarray(frame["c2w"], float))
    cam = boxes.corners(rec) @ w2c[:3, :3].T + w2c[:3, 3]
    segs = []
    for a, b in boxes.EDGES:
        p, q = cam[a], cam[b]
        if p[2] < near and q[2] < near:
            continue
        if p[2] < near:
            p = p + (q - p) * ((near - p[2]) / (q[2] - p[2]))
        elif q[2] < near:
            q = q + (p - q) * ((near - q[2]) / (p[2] - q[2]))
        segs.append(tuple((float(K[0, 0] * v[0] / v[2] + K[0, 2]), float(K[1, 1] * v[1] / v[2] + K[1, 2])) for v in (p, q)))
    return segs


def crop_window(xyxy, size_wh, aspect: float = 4 / 3, pad: float = 2.2, min_w: float = 200.0) -> list:
    """围着画面内的外接框取一个固定长宽比的裁剪窗：比框大 pad 倍、至少 min_w 像素宽、不超出画面（超了就往里挪）。
    返回 [x0, y0, x1, y1]（浮点像素）。"""
    W, H = size_wh
    x0, y0, x1, y1 = max(xyxy[0], 0.0), max(xyxy[1], 0.0), min(xyxy[2], float(W)), min(xyxy[3], float(H))
    w = max(pad * (x1 - x0), pad * (y1 - y0) * aspect, min_w)
    w = min(w, float(W), H * aspect)
    h = w / aspect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    left = min(max(cx - w / 2, 0.0), W - w)
    top = min(max(cy - h / 2, 0.0), H - h)
    return [float(left), float(top), float(left + w), float(top + h)]


def crop_view(K, window, out_w: int) -> tuple:
    """只渲染裁剪窗的那台相机：返回 (K', [宽, 高])，渲染出来的图拉伸到裁剪图的大小就和源帧的裁剪逐像素对应。

    blender_render_views.py 只用 fx（方像素），高清帧的 fx、fy 差 2–3%，所以 K' 取 fx' = fy' = fx · out_w / 窗宽，
    竖直方向的差别放进渲染高度里：高 = 窗高 · fx' / fy。
    """
    K = np.asarray(K, float)
    x0, y0, x1, y1 = window
    a = out_w / (x1 - x0)
    f = K[0, 0] * a
    b = f / K[1, 1]
    out_h = max(1, int(round(b * (y1 - y0))))  # 取整最多差半个像素
    return [[f, 0.0, a * (K[0, 2] - x0)], [0.0, f, b * (K[1, 2] - y0)], [0.0, 0.0, 1.0]], [int(out_w), out_h]


def perception_dir(run_dir: Path, proj: Path = PROJ) -> Path:
    """runs/<组>/<场景>/<seed> 用的感知目录：组名以 -betty 结尾的是 perception_betty，其余是 perception（同 score_run.sh）。"""
    run_dir = Path(run_dir)
    return Path(proj) / ("perception_betty" if run_dir.parts[-3].endswith("-betty") else "perception") / run_dir.parts[-2]


def _rel(path: Path, proj: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(proj).resolve()))
    except ValueError:
        return str(path)


def build(run_dir, proj: Path = PROJ) -> dict:
    """读 <run>/export/objects.json（加上有的话 inventory_decisions.json、感知目录的 hd/cameras.json），返回交接记录。"""
    run_dir, proj = Path(run_dir), Path(proj)
    counted = evaluate.filter_predictions(boxes.load(run_dir / "export" / "objects.json"))
    pdir = perception_dir(run_dir, proj)
    cams = hd.load(pdir / "hd") if (pdir / "hd" / "cameras.json").exists() else None
    dec = run_dir / "inventory_decisions.json"
    ties = inventory_ties(json.loads(dec.read_text())) if dec.exists() else None
    sup, ins = supports(counted), inside(counted)
    objects = []
    for r, s, within in zip(counted, sup, ins):
        views = select_views(r, cams) if cams else []
        for v in views:
            v["image"] = _rel(pdir / "hd" / "frames" / f"{v['frame']:06d}.png", proj)
        objects.append({"id": r["object_id"], "category": r.get("category"),
                        "center": r["center"], "size": r["size"], "yaw": r["yaw"],
                        "support": s["support"], "support_gap_m": s["gap_m"], "support_overlap": s["overlap"],
                        "inside": within,
                        "from_inventory": None if ties is None else r["object_id"] in ties,
                        "inventory_ids": None if ties is None else ties.get(r["object_id"], []),
                        "views": views})
    n_floor = sum(o["support"] == "floor" for o in objects)
    n_null = sum(o["support"] is None for o in objects)
    return {
        "generator": "smallobj.handoff", "version": VERSION,
        "run": _rel(run_dir, proj), "arm": run_dir.parts[-3], "scene": run_dir.parts[-2], "seed": run_dir.parts[-1],
        "sources": {"boxes": "export/objects.json（过 evaluate.filter_predictions，和打分用的实例一致）",
                    "inventory_decisions": "inventory_decisions.json" if ties is not None else None,
                    "cameras": _rel(pdir / "hd" / "cameras.json", proj) if cams else None},
        "frame": "scene.blend 自己的坐标系（AHa-3D 对齐后的房间坐标，没有变到真值坐标）：右手系，z 向上，地面在 z = 0。"
                 "center 是框中心；size = [l, w, h] 是整条边长，l 沿 yaw 方向、w 在水平面内垂直于它、h 竖直；"
                 "yaw 是绕 z 轴的转角。框只绕竖直轴转。",
        "units": {"length": "m", "angle": "rad", "image": "px（views 里的 bbox_xyxy、area_px，按 hd/frames 的原尺寸）"},
        "tolerances": {"floor_z": FLOOR_Z, "support_gap_m": SUPPORT_GAP_M, "support_pen_m": SUPPORT_PEN_M,
                       "support_min_overlap": SUPPORT_MIN_OVERLAP},
        "fields": {
            "support": "放在谁上面：实例 id、\"floor\" 或 null。只看框：底面在对方顶面的 [−support_pen_m, +support_gap_m] 里、"
                       "足迹交叠 ≥ 自己足迹的 support_min_overlap、对方中心低于自己底面，取顶面最高的；否则底面在 floor_z 的"
                       "同一范围里记 floor；都不是记 null（挂墙、吊顶，或放在框表示不出来的面上）。结构件不当支撑物。",
            "support_gap_m": "自己的底面 − 支撑面，负数是陷进去",
            "support_overlap": "足迹交叠面积 / 自己的足迹面积（floor 记 1.0）",
            "inside": "底面中心落在哪个更大的实例的框里（取体积最小的），没有是 null；support 为 null 时用来看是不是放在别人里面",
            "from_inventory": "inventory_decisions.json 里有条目的 object_id 指向这个实例（true / false）；这次运行没有这个文件时是 null",
            "inventory_ids": "指向这个实例的清单条目 id；没有 inventory_decisions.json 时是 null",
            "views": f"框在画面内的外接框面积最大的至多 {N_VIEWS} 帧（不判断遮挡）；frame 是输入视频的帧号，image 相对项目根目录",
        },
        "counts": {"instances": len(objects), "on_floor": n_floor, "on_instance": len(objects) - n_floor - n_null,
                   "no_support": n_null},
        "objects": objects,
    }


def write(run_dir, proj: Path = PROJ) -> dict:
    """写 <run>/objects.json，返回写进去的内容。"""
    out = build(run_dir, proj)
    (Path(run_dir) / "objects.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    return out
