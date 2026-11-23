"""事后"吸附"（snap）：把一次运行里建好的小实例平移到和它对应的清单条目的位置，图像证据同意才挪。

动机（11-20）：建了但 misplaced 的小目标大多只错在位置（尺寸已经对），而清单 v2 自己的框位置不差。
这一步只用三样东西，都来自输入视频：运行存下来的实例框、检测清单（条目的框）、清单条目的掩码和 MoGe 深度。
真值只在 scripts/snap_dev.py 里用来给挪之前、挪之后打分，这个模块不碰。

三步，除了 entry_detections / views_of 读文件，其余都是纯函数，都返回新对象、不改输入：
1. 对应（一个实例最多对一个条目，一个条目最多给一个实例）：
   - decisions：运行自己的 inventory_decisions.json（条目 → 实例 id），只在它指的就是这份清单时用（decisions_match）；
   - nearest：只看几何——中心距离 ≤ max_dist、最长边之比在 [1/max_ratio, max_ratio] 里的条目是候选，
     可选再过一条类别相容（label_compatible），按距离从近到远一对一地取。
2. 挪（moved）：只平移，实例自己的尺寸和朝向不动。z 有三种：entry = 中心对中心；keep = 只挪水平位置；
   support = 保持"底面比支撑面高多少"（原来的支撑按 handoff.supports 算，新位置下方找最接近条目底面的面）。
3. 验收（evidence + accept）：在条目有掩码的那些帧里，实例框投影（8 个角的凸包）和条目掩码的 IoU，
   挪之后的平均值要比挪之前高出 margin；另有一条深度一致：掩码里 MoGe 深度的中位数到框的深度范围的距离
   （各帧取中位数）不超过 depth_tol。只有最长边 < ELIGIBLE_MAX_M 的实例参加。

注意验收不是独立证据：条目的框本来就是用同一批掩码和深度拟出来的，所以"挪之后"的重合度天然偏高。
它实际检查的是：实例现在的位置在图里对不上这个条目（否则不用挪）、实例的尺寸在图里和掩码相称、
条目在多帧之间自洽。条目本身放错了的时候，它拦不住。
"""
import json
import re
from pathlib import Path

import numpy as np

from smallobj import boxes, clean_inventory, handoff, labels
from smallobj.settle import FLOOR_Z

ELIGIBLE_MAX_M = 0.5   # 只挪最长边小于它的实例（XS、S 两档，和 inventory.route_rule 一样用 <）
MAX_DIST_M = 0.30      # nearest 的距离门槛（= thresholds.json 的 loose_abs_m）
MAX_RATIO = 1.5        # 最长边之比的门槛（= 严格判据 D 的尺寸范围）
MARGIN = 0.10          # 验收：挪之后的平均 IoU 至少比挪之前高这么多
DEPTH_TOL_M = 0.10     # 验收：挪之后掩码深度到框的深度范围的距离（各帧中位数）上限
NEAR_M = 0.05          # 相机前方不到 5 cm 的角当作在相机后面（同 hd.project_box）
SUPPORT_SEARCH_M = 0.15  # z_mode="support"：新位置的支撑面离条目底面最多这么远（同 settle 的 max_gap）

# 不参加类别比较的词：类别的大组名、方位、颜色、大小。实例 id 里这类词很多（sideboard_red_cup、switch_east_left）。
STOP_WORDS = {"decor", "fixture", "object", "furniture", "prop", "misc", "item", "small", "large", "big", "little",
              "left", "right", "east", "west", "north", "south", "upper", "lower", "middle", "mid", "top", "bottom",
              "front", "back", "red", "blue", "green", "white", "black", "yellow", "purple", "brown", "grey", "gray",
              "wall", "floor", "of", "on", "the", "and", "with"}
# 当成同一个词的几组（每组第一个是代表）。只收常见的叫法差别，不求全。
SYNONYMS = (("outlet", "socket", "plug", "plate", "switch"), ("cushion", "pillow"),
            ("picture", "painting", "photo", "frame", "poster", "collage"),
            ("television", "tv", "monitor", "screen", "display"), ("cup", "mug", "glass", "jar"), ("lamp", "light"),
            ("pot", "planter", "vase"), ("plant", "flower", "sunflower", "greenery", "orchid"),
            ("rug", "carpet", "mat"), ("sofa", "couch"), ("book", "magazine"), ("remote", "controller"),
            ("bottle", "cosmetic", "toiletry"), ("box", "organizer", "bin", "basket"))
_CANON = {w: g[0] for g in SYNONYMS for w in g}


def _id(entry):
    return entry["item_id"] if "item_id" in entry else entry["object_id"]


def eligible(rec, max_longest: float = ELIGIBLE_MAX_M) -> bool:
    """最长边 < max_longest 的实例才参加。"""
    return max(rec["size"]) < max_longest


def words(*texts, synonyms: bool = True) -> list:
    """把 id / 类别拆成词：小写，按非字母切开（数字、下划线、斜杠都是分隔），变单数，去掉 STOP_WORDS 和单个字母，
    同义词换成代表。保留顺序（最后一个词当中心词用），不去重。"""
    out = []
    for t in texts:
        for w in re.split(r"[^a-z]+", str(t).lower()):
            w = labels._singular(w)
            if len(w) >= 2 and w not in STOP_WORDS:
                out.append(_CANON.get(w, w) if synonyms else w)
    return out


def label_compatible(inst, entry) -> bool:
    """类别相容的规则：条目的 label 或某个 alt_label 的中心词（最后一个词）出现在实例的词里（id + 类别），
    或者实例类别的中心词出现在条目的词里（label + alt_labels）。词的处理见 words。
    例：实例 sideboard_red_cup（decor/cup）和条目 glass 相容（cup、glass 同义）；coffee_bowl_1（bowl）和条目
    coffee table 不相容（table 不在实例的词里，bowl 不在条目的词里）。"""
    inst_words = set(words(inst["object_id"], inst.get("category", "")))
    cat = words(inst.get("category", ""))
    names = [entry.get("label", entry.get("category", ""))] + list(entry.get("alt_labels", []))
    entry_words, heads = set(), set()
    for n in names:
        w = words(n)
        entry_words.update(w)
        if w:
            heads.add(w[-1])
    return bool(heads & inst_words) or bool(cat and cat[-1] in entry_words)


def size_ratio(inst, entry) -> float:
    """最长边之比（≥ 1）。"""
    a, b = max(inst["size"]), max(entry["size"])
    return max(a, b) / min(a, b)


def distance(inst, entry) -> float:
    return float(np.linalg.norm(np.subtract(inst["center"], entry["center"])))


def candidates(instances: list, entries: list, max_dist: float = MAX_DIST_M, max_ratio: float = MAX_RATIO,
               use_labels: bool = True, max_longest: float = ELIGIBLE_MAX_M) -> list:
    """过了门槛的 (距离, 实例下标, 条目下标)，按距离从近到远（同距离按下标，结果和输入顺序以外的东西无关）。"""
    out = []
    for i, p in enumerate(instances):
        if not eligible(p, max_longest):
            continue
        for j, e in enumerate(entries):
            d = distance(p, e)
            if d <= max_dist and size_ratio(p, e) <= max_ratio and (not use_labels or label_compatible(p, e)):
                out.append((d, i, j))
    return sorted(out)


def associate_nearest(instances: list, entries: list, max_dist: float = MAX_DIST_M, max_ratio: float = MAX_RATIO,
                      use_labels: bool = True, max_longest: float = ELIGIBLE_MAX_M) -> dict:
    """nearest 对应：候选按距离从近到远取，两边都没用过的才配（和 evaluate.match 的 greedy 一个取法）。
    返回 {实例 id: 条目 item_id}。"""
    pairs, used_i, used_j = {}, set(), set()
    for _, i, j in candidates(instances, entries, max_dist, max_ratio, use_labels, max_longest):
        if i not in used_i and j not in used_j:
            pairs[instances[i]["object_id"]] = _id(entries[j])
            used_i.add(i)
            used_j.add(j)
    return pairs


def decisions_match(decisions: dict, entries: list, min_cover: float = 0.9) -> bool:
    """inventory_decisions.json 指的是不是这份清单：它的键都得是这份清单的 item_id，而且盖住清单的 min_cover 以上。
    （Boxer 清单是 b###，清单 v2 和干净对照都是 c###：光看前缀分不开，所以两个方向都查。）"""
    ids = {_id(e) for e in entries}
    keys = set(decisions)
    return bool(keys) and keys <= ids and len(keys) >= min_cover * len(ids)


def associate_decisions(instances: list, entries: list, decisions: dict, max_dist=None, max_ratio=None,
                        max_longest: float = ELIGIBLE_MAX_M) -> dict:
    """decisions 对应：agent 自己记的"条目 → 实例"。几条条目指向同一个实例时取离实例现在位置最近的一条；
    max_dist / max_ratio 给了就同样要过门槛（None 不设）。返回 {实例 id: 条目 item_id}。"""
    by_id = {_id(e): e for e in entries}
    pairs = {}
    for p in instances:
        if not eligible(p, max_longest):
            continue
        best = None
        for item_id in handoff.inventory_ties(decisions).get(p["object_id"], []):
            e = by_id.get(item_id)
            if e is None:
                continue
            d = distance(p, e)
            if (max_dist is None or d <= max_dist) and (max_ratio is None or size_ratio(p, e) <= max_ratio) \
                    and (best is None or (d, item_id) < best):
                best = (d, item_id)
        if best is not None:
            pairs[p["object_id"]] = best[1]
    return pairs


def _bottom(r):
    return r["center"][2] - r["size"][2] / 2


def moved(inst, entry, z_mode: str = "entry", others=None, floor_z: float = FLOOR_Z,
          search: float = SUPPORT_SEARCH_M) -> dict:
    """实例平移到条目的位置，尺寸和 yaw 不变。z_mode：
    - "entry"：中心对中心；
    - "keep"：只挪水平位置，高度不变；
    - "support"：保持底面比支撑面高多少。原来的支撑和高度差按 handoff.supports 在 [实例] + others 里算；
      新位置下方的面 = 地面或 others 里足迹和挪后的足迹交叠 ≥ handoff.SUPPORT_MIN_OVERLAP 的实例的顶面，
      取离条目底面最近的、且不超过 search 的那个，底面 = 那个面 + 原来的高度差。原来没有支撑（挂墙、悬空）
      或新位置找不到面时退回 "entry"。
    """
    out = {**inst, "center": [float(entry["center"][0]), float(entry["center"][1]), float(entry["center"][2])],
           "size": list(inst["size"])}
    if z_mode == "entry":
        return out
    if z_mode == "keep":
        out["center"][2] = float(inst["center"][2])
        return out
    if z_mode != "support":
        raise ValueError(f"z_mode 只能是 entry / keep / support，收到 {z_mode!r}")
    others = [o for o in (others or []) if o["object_id"] != inst["object_id"]]
    near = [o for o in others  # 只有顶面在容差里的才可能是支撑，先筛一遍，省得 supports 把所有实例两两算一遍
            if -handoff.SUPPORT_PEN_M <= _bottom(inst) - (o["center"][2] + o["size"][2] / 2) <= handoff.SUPPORT_GAP_M]
    sup = handoff.supports([inst] + near, floor_z=floor_z)[0]
    if sup["support"] is None:
        return out
    target, area = _bottom(entry), inst["size"][0] * inst["size"][1]
    surfaces = [floor_z] + [o["center"][2] + o["size"][2] / 2 for o in others
                            if handoff.footprint_overlap(out, o) / area >= handoff.SUPPORT_MIN_OVERLAP]
    best = min(surfaces, key=lambda z: abs(z - target))
    if abs(best - target) <= search:
        out["center"][2] = float(best + sup["gap_m"] + inst["size"][2] / 2)
    return out


def box_mask(rec, frame, size_wh):
    """框投到这一帧的剪影（8 个角的凸包），(H, W) 的 bool 数组。有角在相机后面（z < NEAR_M）时返回全 False：
    小物体这时基本出画了（同 visibility.visible_pixels 的处理）。"""
    from PIL import Image, ImageDraw
    from scipy.spatial import ConvexHull
    W, H = size_wh
    K = np.asarray(frame["K"], float)
    w2c = np.linalg.inv(np.asarray(frame["c2w"], float))
    cam = boxes.corners(rec) @ w2c[:3, :3].T + w2c[:3, 3]
    if np.any(cam[:, 2] <= NEAR_M):
        return np.zeros((H, W), bool)
    uv = cam[:, :2] / cam[:, 2:3] * [K[0, 0], K[1, 1]] + [K[0, 2], K[1, 2]]
    if uv[:, 0].max() < 0 or uv[:, 1].max() < 0 or uv[:, 0].min() > W or uv[:, 1].min() > H:
        return np.zeros((H, W), bool)
    try:
        hull = uv[ConvexHull(uv).vertices]
    except Exception:  # 投影退化成一条线
        return np.zeros((H, W), bool)
    img = Image.new("1", (W, H), 0)
    ImageDraw.Draw(img).polygon([tuple(float(v) for v in p) for p in hull], fill=1)
    return np.asarray(img, bool)


def mask_iou(a, b) -> float:
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    union = int((a | b).sum())
    return float((a & b).sum() / union) if union else 0.0


def depth_residual(rec, frame, mask, depth):
    """掩码里深度的中位数到框的深度范围 [最近的角, 最远的角] 的距离（在范围里是 0），米。
    掩码里没有有效深度，或者框有角在相机后面时返回 None。"""
    d = np.asarray(depth)[np.asarray(mask, bool)]
    d = d[np.isfinite(d)]
    w2c = np.linalg.inv(np.asarray(frame["c2w"], float))
    z = (boxes.corners(rec) @ w2c[:3, :3].T + w2c[:3, 3])[:, 2]
    if d.size == 0 or np.any(z <= NEAR_M):
        return None
    obs = float(np.median(d))
    return float(max(z.min() - obs, obs - z.max(), 0.0))


def evidence(before, after, views: list, size_wh) -> dict:
    """图像证据。views：条目有掩码的帧，每帧 {"frame": cameras.json 的一帧, "mask": bool 数组, "depth": 数组或 None}。
    返回 {"n_frames", "iou_before", "iou_after", "gain", "depth_before", "depth_after"}：IoU 是各帧的平均，
    深度是各帧 depth_residual 的中位数（哪一帧都算不出来时是 None）。没有帧时 n_frames = 0，其余是 None。"""
    if not views:
        return {"n_frames": 0, "iou_before": None, "iou_after": None, "gain": None,
                "depth_before": None, "depth_after": None}
    iou = {"before": [], "after": []}
    dep = {"before": [], "after": []}
    for v in views:
        for name, rec in (("before", before), ("after", after)):
            iou[name].append(mask_iou(v["mask"], box_mask(rec, v["frame"], size_wh)))
            r = depth_residual(rec, v["frame"], v["mask"], v["depth"]) if v.get("depth") is not None else None
            if r is not None:
                dep[name].append(r)
    b, a = float(np.mean(iou["before"])), float(np.mean(iou["after"]))
    return {"n_frames": len(views), "iou_before": b, "iou_after": a, "gain": a - b,
            "depth_before": float(np.median(dep["before"])) if dep["before"] else None,
            "depth_after": float(np.median(dep["after"])) if dep["after"] else None}


def accept(ev: dict, margin: float = MARGIN, depth_tol=DEPTH_TOL_M, min_frames: int = 1) -> bool:
    """验收：条目至少在 min_frames 帧里有掩码；挪之后的平均 IoU − 挪之前的 ≥ margin；
    depth_tol 不是 None 时，挪之后的深度距离还得 ≤ depth_tol（算不出深度的不卡这一条）。"""
    if ev["n_frames"] < max(min_frames, 1) or ev["gain"] is None or ev["gain"] < margin:
        return False
    return depth_tol is None or ev["depth_after"] is None or ev["depth_after"] <= depth_tol


def snap(instances: list, entries: list, pairs: dict, views_of, size_wh, z_mode: str = "entry",
         margin: float = MARGIN, depth_tol=DEPTH_TOL_M, min_frames: int = 1,
         max_longest: float = ELIGIBLE_MAX_M, cache=None) -> tuple:
    """对每一对（实例, 条目）算挪后的框和图像证据，过了验收的换成挪后的框。

    pairs：{实例 id: 条目 item_id}（associate_* 的输出）；views_of(条目) → evidence 要的 views。
    挪后的框和 support 的支撑关系都按挪之前的场景算，各实例互不影响，结果和处理顺序无关。
    cache：可选的字典，(实例 id, 条目 id, z_mode) → (挪后的框, 证据)，同一场景反复试阈值时省掉重算。
    返回 (新的实例列表（顺序同输入）, 记录)：记录每对一条
    {"object_id", "item_id", "move_m", "accepted", "after": 挪后的框, **证据}。最长边 ≥ max_longest 的实例原样留着，
    就算 pairs 里有它也不动。"""
    by_id = {_id(e): e for e in entries}
    out, log = [], []
    for p in instances:
        e = by_id.get(pairs.get(p["object_id"]))
        if e is None or not eligible(p, max_longest):
            out.append(p)
            continue
        key = (p["object_id"], _id(e), z_mode)
        if cache is not None and key in cache:
            new, ev = cache[key]
        else:
            new = moved(p, e, z_mode, others=instances)
            ev = evidence(p, new, views_of(e), size_wh)
            if cache is not None:
                cache[key] = (new, ev)
        ok = accept(ev, margin, depth_tol, min_frames)
        log.append({"object_id": p["object_id"], "item_id": _id(e), "move_m": distance(p, new),
                    "accepted": ok, "after": new, **ev})
        out.append(new if ok else p)
    return out, log


def entry_detections(hd_dir, masks_dir, depth_name: str = "depth_moge", min_points: int = 30,
                     iou_min: float = 0.25) -> dict:
    """清单条目 → 并进它的那几个检测：{item_id: [index.json 的条目（frame、mask、score、label…）]}。

    清单里没存这层对应（inventory.fuse 只留了最高分那一帧），这里照 clean_inventory.build + inventory.fuse 的
    做法重算一遍：每个掩码反投影拟框，按分数从高到低，和同类簇首的 3D IoU ≥ iou_min 的并进去，第 k 个簇就是
    条目 c{k:03d}。参数要和建清单时一样（清单 v2：depth_moge、30 个点、0.25）。只读掩码和深度，不碰真值。"""
    from PIL import Image

    from smallobj import evaluate, hd
    hd_dir, masks_dir = Path(hd_dir), Path(masks_dir)
    by_frame = {int(f["source_frame"]): f for f in hd.load(hd_dir)["frames"]}
    depths, dets = {}, []
    for k, m in enumerate(json.loads((masks_dir / "index.json").read_text())):
        s = int(m["frame"])
        if s not in depths:
            depths[s] = np.load(hd_dir / depth_name / f"{s:06d}.npy")
        mask = np.asarray(Image.open(masks_dir / m["mask"])) > 0
        pts = clean_inventory.points_from_mask(mask, depths[s], by_frame[s]["K"], by_frame[s]["c2w"])
        if len(pts) < min_points:
            continue
        r = boxes.fit_obb(pts, object_id=f"d{k}", category=m["label"], source="clean")
        r.update(score=float(m["score"]), det=dict(m))
        dets.append(r)
    clusters = []
    for d in sorted(dets, key=lambda r: -r["score"]):
        for c in clusters:
            if c[0]["category"] == d["category"] and evaluate.iou3d(c[0], d) >= iou_min:
                c.append(d)
                break
        else:
            clusters.append([d])
    return {f"c{k:03d}": [d["det"] for d in c] for k, c in enumerate(clusters)}


def views_of(entry, detections: dict, cams: dict, masks_dir, depth_dir=None, _cache=None) -> list:
    """条目有掩码的帧（evidence 的输入）：条目的 members（核对表并组的成员，没有就是它自己）在 detections 里的
    检测，同一帧的掩码取并集。depth_dir 给了就带上那一帧的深度。_cache：可选字典，存读过的深度图。"""
    from PIL import Image
    masks_dir = Path(masks_dir)
    by_frame = {int(f["source_frame"]): f for f in cams["frames"]}
    masks = {}
    for member in entry.get("members", [_id(entry)]):
        for det in detections.get(member, []):
            m = np.asarray(Image.open(masks_dir / det["mask"])) > 0
            s = int(det["frame"])
            masks[s] = masks[s] | m if s in masks else m
    out = []
    for s in sorted(masks):
        depth = None
        if depth_dir is not None:
            key = (str(depth_dir), s)
            if _cache is not None and key in _cache:
                depth = _cache[key]
            else:
                depth = np.load(Path(depth_dir) / f"{s:06d}.npy")
                if _cache is not None:
                    _cache[key] = depth
        out.append({"frame": by_frame[s], "mask": masks[s], "depth": depth})
    return out
