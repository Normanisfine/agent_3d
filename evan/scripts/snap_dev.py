"""事后"吸附"（smallobj.snap）在开发集上的测量：只读开发集的运行，结果写到 results/snap_dev/，不往运行目录里写。

对每个有 export/objects.json 和 score_sim3.json 的开发集运行：实例框读进内存 → 小实例对应到清单 v2 的核对表
（perception/<id>/inventory_v2_list.json）→ 挪 → 图像验收 → 用仓库的打分（score.score_predictions，Sim(3) 对齐、
判据 D）重打一遍，和挪之前比。真值只用来打分和事后归因，对应、挪、验收都不看真值（"真值验收"那几行除外，
它们是上界，不是方法）。

用法：OMP_NUM_THREADS=1 PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .runtime/venv/bin/python scripts/snap_dev.py
输出：results/snap_dev/README.md、summary.json（全部数字）、moves.json（预先定的配置下每一对的记录）、
cache/<scene>_detections.json（清单条目 → 掩码的对应，重算一次约半分钟，存下来）。
"""
import json
import time
from pathlib import Path

import numpy as np

from smallobj import align, boxes, evaluate, handoff, hd, score, snap

PROJ = Path(__file__).resolve().parent.parent
OUT = PROJ / "results" / "snap_dev"
SKIP_ARMS = {"logs", "showcase"}
BINS = evaluate.BINS
# 预先定的配置（看结果之前写下的，见 README）：门槛都取打分口径里现成的数
DECLARED = dict(mode="nearest", max_dist=snap.MAX_DIST_M, max_ratio=snap.MAX_RATIO, use_labels=True, z_mode="entry",
                margin=snap.MARGIN, depth_tol=snap.DEPTH_TOL_M, min_frames=1, accept="image")
ORACLE_PASSES = 3
LOOSE = dict(DECLARED, max_dist=0.6, max_ratio=3.0, use_labels=False)  # 最松的对应，只给真值验收当上界用


def cfg_name(c):
    if c.get("name"):
        return c["name"]
    acc = {"image": f"IoU 提高 ≥ {c['margin']:g}" + ("" if c["depth_tol"] is None else f"、深度 ≤ {c['depth_tol']:g} m")
           + ("" if c["min_frames"] <= 1 else f"、≥ {c['min_frames']} 帧"),
           "all": "不验收（对应上的都挪）", "oracle": "真值验收（上界，不是方法）"}[c["accept"]]
    z = {"entry": "", "keep": "、高度不变", "support": "、保持离支撑面的高度"}[c["z_mode"]]
    return (f"距离 ≤ {c['max_dist']:g} m、尺寸比 ≤ {c['max_ratio']:g}、" + ("类别相容" if c["use_labels"] else "不看类别")
            + z + "；" + acc)


def variants():
    """扫描：从预先定的配置出发一次只改一项，外加 距离 × IoU 提高量 × 是否看类别 的小网格。"""
    out = [dict(DECLARED)]
    for k, vals in (("use_labels", [False]), ("max_dist", [0.15, 0.2, 0.4, 0.6]), ("max_ratio", [1.25, 2.0, 3.0]),
                    ("margin", [0.0, 0.05, 0.2, 0.3]), ("depth_tol", [None, 0.05]), ("min_frames", [2]),
                    ("z_mode", ["keep", "support"]), ("accept", ["all"])):
        out += [dict(DECLARED, **{k: v}) for v in vals]
    grid = [dict(DECLARED, max_dist=d, margin=m, use_labels=u)
            for u in (True, False) for d in (0.2, 0.3, 0.4, 0.6) for m in (0.05, 0.1, 0.2, 0.3)]
    return out, [g for g in grid if g not in out]


def find_runs():
    """runs/<组>/<开发集场景>/<seed>/ 里有 export/objects.json 和 score_sim3.json 的。下划线开头的目录不看。
    返回 (用到的, 跳过的 [(路径, 原因)])。"""
    dev = json.loads((PROJ / "configs" / "splits.json").read_text())["dev"]
    used, skipped = [], []
    for arm in sorted(p for p in (PROJ / "runs").iterdir() if p.is_dir()):
        if arm.name.startswith("_") or arm.name in SKIP_ARMS:
            continue
        for sid in dev:
            for run in sorted(p for p in (arm / sid).glob("*") if p.is_dir()):
                if not ((run / "export" / "objects.json").exists() and (run / "score_sim3.json").exists()):
                    skipped.append((run, "没有 export/objects.json 或 score_sim3.json"))
                elif arm.name.endswith("-betty"):
                    skipped.append((run, "用的是 perception_betty 的坐标系，那边没有清单 v2 和掩码"))
                else:
                    used.append(run)
    return used, skipped


class Scene:
    """一个场景要用的东西：核对表、条目的掩码、相机、真值和对齐。掩码按条目读，读过的留在内存里。"""

    def __init__(self, sid):
        self.sid = sid
        self.P = PROJ / "perception" / sid
        self.masks_dir = self.P / "sam3_objects_v2"
        self.entries = json.loads((self.P / "inventory_v2_list.json").read_text())
        self.cams = hd.load(self.P / "hd")
        self.gts = boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")
        self.tf = align.pipeline_to_gt(self.P / "bundle", PROJ / "scenes" / sid, with_scale=True)
        cache = OUT / "cache" / f"{sid}_detections.json"
        if cache.exists():
            self.det = json.loads(cache.read_text())
        else:
            self.det = snap.entry_detections(self.P / "hd", self.P / "sam3_objects_v2")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(self.det) + "\n")
        raw = json.loads((self.P / "inventory_v2.json").read_text())  # 核对：重算的对应和清单里存的对得上
        self.det_mismatch = sum(len(self.det.get(it["item_id"], [])) != it["n_frames"]
                                or self.det[it["item_id"]][0]["box_xyxy"] != it["bbox2d_xyxy"] for it in raw)
        self._views, self._depth = {}, {}
        small = [e for e in self.entries if snap.eligible(e)]  # 条目自己的框投回去，和自己的掩码还对不对得上
        self_iou = [float(np.mean([snap.mask_iou(v["mask"], snap.box_mask(e, v["frame"], self.cams["size_wh"]))
                                   for v in snap.views_of(e, self.det, self.cams, self.P / "sam3_objects_v2")]))
                    for e in small]
        self.self_check = {"small_entries": len(small), "self_iou_lt_0.05": sum(v < 0.05 for v in self_iou),
                           "of_which_settled": sum(v < 0.05 and e.get("settled_on") is not None
                                                   for v, e in zip(self_iou, small)),
                           "self_iou_median": float(np.median(self_iou)),
                           "one_frame": sum(len({d["frame"] for m in e["members"] for d in self.det.get(m, [])}) == 1
                                            for e in small)}

    def views_of(self, entry):
        k = snap._id(entry)
        if k not in self._views:
            self._views[k] = snap.views_of(entry, self.det, self.cams, self.masks_dir,
                                           self.P / "hd" / "depth_moge", self._depth)
        return self._views[k]


class BoxerScene(Scene):
    """旁证用：同一个场景，条目换成 Boxer 清单（inventory.json，A2 / A3 的运行拿到的那份），
    掩码用 item_masks/（每条在投影最好的几帧里用框提示分出来的）。相机、真值、对齐和 Scene 共用。"""

    def __init__(self, scene):
        self.sid, self.P, self.cams, self.gts, self.tf = scene.sid, scene.P, scene.cams, scene.gts, scene.tf
        self.masks_dir = self.P / "item_masks"
        self.entries = json.loads((self.P / "inventory.json").read_text())
        self.det = {}
        for m in json.loads((self.masks_dir / "index.json").read_text()):
            if m.get("status") == "ok":
                self.det.setdefault(m["item_id"], []).append(m)
        self._views, self._depth = {}, scene._depth


def counts(rows):
    """每档 D 判据下 [correct, misplaced, missed] 的个数。"""
    return {b: [sum(r["bin"] == b and r["D"] == o for r in rows) for o in ("correct", "misplaced", "missed")]
            for b in BINS}


def n_correct(rows):
    return sum(r["D"] == "correct" for r in rows)


class Run:
    def __init__(self, run_dir, scene, th):
        self.dir, self.scene, self.th = run_dir, scene, th
        self.name = "/".join(run_dir.parts[-3:])
        self.preds = boxes.load(run_dir / "export" / "objects.json")
        assert len({p["object_id"] for p in self.preds}) == len(self.preds), f"{self.name}: 实例 id 有重复"
        self.counted = evaluate.filter_predictions(self.preds)
        self.rows0 = self.rescore({})
        saved = {r["gt_id"]: r["D"] for r in json.loads((run_dir / "score_sim3.json").read_text())["rows"]}
        self.baseline_mismatch = sum(saved.get(r["gt_id"]) != r["D"] for r in self.rows0)
        self.ev_cache, self.fixing = {}, {}
        dec = run_dir / "inventory_decisions.json"
        self.decisions = json.loads(dec.read_text()) if dec.exists() else None

    def correct0(self, oid):
        return any(r.get("pred_id") == oid and r["D"] == "correct" for r in self.rows0)

    def rescore(self, new_by_id):
        preds = [new_by_id.get(p["object_id"], p) for p in self.preds]
        return score.score_predictions(preds, self.scene.gts, self.scene.tf, self.th)["rows"]

    def pairs(self, c):
        if c["mode"] == "decisions":
            return snap.associate_decisions(self.counted, self.scene.entries, self.decisions, c["max_dist"], c["max_ratio"])
        return snap.associate_nearest(self.counted, self.scene.entries, c["max_dist"], c["max_ratio"], c["use_labels"])

    def apply(self, c):
        """一个配置在这次运行上的结果：对应、验收、重打分、被挪实例的去向。"""
        pairs = self.pairs(c)
        image = c["accept"] == "image"
        _, log = snap.snap(self.counted, self.scene.entries, pairs, self.scene.views_of, self.scene.cams["size_wh"],
                           z_mode=c["z_mode"], margin=c["margin"] if image else -np.inf,
                           depth_tol=c["depth_tol"] if image else None, min_frames=c["min_frames"] if image else 0,
                           cache=self.ev_cache)
        if c["accept"] == "all":
            for l in log:
                l["accepted"] = True
        if c["accept"] == "oracle":
            # 按真值一个一个试（上界）：挪了之后全场 correct 数不掉，并且要么变多、要么这个实例自己变成 correct
            # （它从别的实例手里换来一个真值，那个实例下一轮还可以再挪）。一轮里有新留下的就再过一轮，最多 ORACLE_PASSES 轮。
            taken, best = {}, n_correct(self.rows0)
            for l in log:
                l["accepted"] = False
            for _ in range(ORACLE_PASSES):
                changed = False
                for l in log:
                    if l["accepted"]:
                        continue
                    rows = self.rescore({**taken, l["object_id"]: l["after"]})
                    n = n_correct(rows)
                    own = any(r.get("pred_id") == l["object_id"] and r["D"] == "correct" for r in rows)
                    if n > best or (n == best and own and not self.correct0(l["object_id"])):
                        l["accepted"], changed = True, True
                        taken[l["object_id"]], best = l["after"], n
                if not changed:
                    break
        new = {l["object_id"]: l["after"] for l in log if l["accepted"]}
        rows = self.rescore(new) if new else self.rows0
        before = {r["pred_id"]: r["D"] for r in self.rows0 if r.get("pred_id")}
        after = {r["pred_id"]: r["D"] for r in rows if r.get("pred_id")}
        trans = {}
        for oid in new:
            k = f"{before.get(oid, 'unmatched')}→{after.get(oid, 'unmatched')}"
            trans[k] = trans.get(k, 0) + 1
        return {"eligible": sum(snap.eligible(p) for p in self.counted), "associated": len(log), "accepted": len(new),
                "before": counts(self.rows0), "after": counts(rows), "trans": trans, "log": log, "pairs": pairs}

    def diagnose(self, res, c):
        """事后归因（用真值）：基线里 XS、S 档 misplaced 的目标，各自卡在哪一步。"""
        th, tf, sc = self.th, self.scene.tf, self.scene
        by_id = {p["object_id"]: p for p in self.counted}
        gts = {g["object_id"]: g for g in sc.gts}
        logs = {l["object_id"]: l for l in res["log"]}
        to_gt = lambda r: align.apply(r, tf["s"], tf["R"], tf["t"])
        out = {}
        for r in self.rows0:
            if r["bin"] not in ("XS", "S") or r["D"] != "misplaced":
                continue
            p, g = by_id[r["pred_id"]], gts[r["gt_id"]]
            lo, hi = th["size_ratio"]
            if not snap.eligible(p):
                k = "实例最长边 ≥ 0.5 m，不参加"
            elif not lo <= max(to_gt(p)["size"]) / max(g["size"]) <= hi:
                k = "尺寸不对（吸附不改尺寸）"
            else:
                key = (p["object_id"], g["object_id"])
                if key not in self.fixing:
                    self.fixing[key] = {snap._id(e) for e in sc.entries
                                        if evaluate._strict_D(to_gt(snap.moved(p, e)), g, th)}
                fixing = self.fixing[key]
                l = logs.get(p["object_id"])
                if not fixing:
                    k = "只错位置，但核对表里没有哪一条的位置够准"
                elif l is None:
                    ok = [e for e in sc.entries if snap._id(e) in fixing]
                    gated = [e for e in ok if snap.distance(p, e) <= c["max_dist"] and snap.size_ratio(p, e) <= c["max_ratio"]]
                    if not gated:
                        why = "都在距离或尺寸比门槛外"
                    elif c["use_labels"] and not any(snap.label_compatible(p, e) for e in gated):
                        why = "类别不相容"
                    else:
                        why = "被别的实例占了"
                    k = "只错位置，有位置够准的条目，但没对应上：" + why
                elif l["item_id"] not in fixing:
                    k = "只错位置，对应到了别的条目" + ("，并且挪了" if l["accepted"] else "，验收拦下")
                else:
                    k = "只错位置，对应到了位置够准的条目，" + ("挪了" if l["accepted"] else "验收没过")
            out[k] = out.get(k, 0) + 1
        return out


def pool(results):
    """多次运行的结果加起来。"""
    tot = {"eligible": 0, "associated": 0, "accepted": 0, "trans": {},
           "before": {b: [0, 0, 0] for b in BINS}, "after": {b: [0, 0, 0] for b in BINS}}
    for r in results:
        for k in ("eligible", "associated", "accepted"):
            tot[k] += r[k]
        for k, v in r["trans"].items():
            tot["trans"][k] = tot["trans"].get(k, 0) + v
        for when in ("before", "after"):
            for b in BINS:
                tot[when][b] = [x + y for x, y in zip(tot[when][b], r[when][b])]
    return tot


def small_share(c):
    """XS+S 里 correct 的占比。"""
    n = sum(c["XS"]) + sum(c["S"])
    return (c["XS"][0] + c["S"][0]) / n if n else float("nan")


def gate(t):
    """预先定的门槛：XS+S correct 占比至少涨 5 个百分点，M、L 的 correct 不掉。"""
    gain = 100 * (small_share(t["after"]) - small_share(t["before"]))
    keep = all(t["after"][b][0] >= t["before"][b][0] for b in ("M", "L"))
    return gain, keep, gain >= 5.0 and keep


def tr(t, *keys):
    return sum(v for k, v in t["trans"].items() if k in keys)


def fmt_bin(t, b):
    x, y = t["before"][b], t["after"][b]
    return f"{x[0]}/{x[1]}/{x[2]} → {y[0]}/{y[1]}/{y[2]}"


def row(label, t):
    gain, keep, ok = gate(t)
    return (f"| {label} | {t['eligible']} | {t['associated']} | {t['accepted']} | " + " | ".join(fmt_bin(t, b) for b in BINS)
            + f" | {100 * small_share(t['before']):.1f}% → {100 * small_share(t['after']):.1f}%（{gain:+.1f}） | "
            + f"{tr(t, 'misplaced→correct')} | {tr(t, 'correct→misplaced', 'correct→unmatched')} | "
            + f"{tr(t, 'unmatched→correct', 'unmatched→misplaced')}（{tr(t, 'unmatched→correct')}） | "
            + f"{tr(t, 'misplaced→unmatched')} | {'过' if ok else '不过'} |")


HEAD = ("| {} | 小实例 | 对应上 | 挪了 | XS | S | M | L | XS+S correct 占比 | misplaced→correct | correct→坏 | "
        "没配上→配上（其中 correct） | misplaced→没配上 | 门槛 |\n|" + "---|" * 15)


def main():
    t0 = time.time()
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    used, skipped = find_runs()
    sweep, grid = variants()
    oracle = [dict(DECLARED, accept="oracle"), dict(LOOSE, accept="oracle")]
    configs = sweep + grid + oracle
    per_cfg = [[] for _ in configs]   # per_cfg[k][i] = 第 k 个配置在第 i 次运行上的结果
    runs_meta, diag_by_cfg, moves, side, boxer, scenes_meta = [], {}, [], [], [], {}
    by_scene = {}
    for run in used:
        by_scene.setdefault(run.parts[-2], []).append(run)
    order = []
    for sid, rs in by_scene.items():   # 一次只留一个场景的掩码在内存里
        scene = Scene(sid)
        scenes_meta[sid] = {"entries": len(scene.entries), "det_mismatch": scene.det_mismatch,
                            "align_residual_m": scene.tf["residual_median_m"], "align_s": scene.tf["s"],
                            "self_check": scene.self_check,
                            "gt": {b: sum(evaluate.size_bin(g, th["bin_edges_m"]) == b for g in scene.gts) for b in BINS}}
        for run_dir in rs:
            run = Run(run_dir, scene, th)
            order.append(run.name)
            dm = run.decisions is not None and snap.decisions_match(run.decisions, scene.entries)
            runs_meta.append({"run": run.name, "instances": len(run.counted), "baseline_mismatch": run.baseline_mismatch,
                              "has_decisions": run.decisions is not None, "decisions_match_v2": dm})
            for k, c in enumerate(configs):
                res = run.apply(c)
                per_cfg[k].append(res)
                if c["accept"] != "oracle":
                    d = run.diagnose(res, c)
                    for pool_name in ("all", "agent") if run.name.startswith("A") else ("all",):
                        tgt = diag_by_cfg.setdefault((k, pool_name), {})
                        for kk, v in d.items():
                            tgt[kk] = tgt.get(kk, 0) + v
                if k == 0:
                    moves += [{"run": run.name, **l} for l in res["log"]]
            if dm:  # 运行自己的 decisions 指的就是这份核对表：再跑一遍 decisions 对应
                c = dict(DECLARED, mode="decisions", max_dist=None, max_ratio=snap.MAX_RATIO, name="decisions 对应")
                side.append((run.name, run.apply(c)))
            elif run.decisions is not None and (scene.P / "item_masks" / "index.json").exists():
                bscene = BoxerScene(scene)
                if snap.decisions_match(run.decisions, bscene.entries):  # 指的是 Boxer 清单：旁证
                    brun = Run(run_dir, bscene, th)
                    for label, c in (("decisions、尺寸比 ≤ 1.5、验收同预先定的", dict(DECLARED, mode="decisions", max_dist=None)),
                                     ("decisions、不设门槛、不验收", dict(DECLARED, mode="decisions", max_dist=None,
                                                                 max_ratio=None, accept="all")),
                                     ("decisions、尺寸比 ≤ 1.5、真值验收（上界）", dict(DECLARED, mode="decisions",
                                                                         max_dist=None, accept="oracle")),
                                     ("nearest（预先定的配置，条目换成 Boxer 清单）", dict(DECLARED))):
                        boxer.append((run.name, label, brun.apply(c)))
            print(f"{run.name} 完成，{time.time() - t0:.0f} s", flush=True)
        del scene
    pooled = [pool(r) for r in per_cfg]
    agent = [i for i, n in enumerate(order) if n.startswith("A")]
    pooled_agent = [pool([r[i] for i in agent]) for r in per_cfg]
    n_method = len(sweep) + len(grid)

    def better(k):  # 选"最好的非真值配置"：M、L 不掉的前提下 XS+S correct 最多，并列取靠前的（离预先定的近）
        t = pooled[k]
        keep = all(t["after"][b][0] >= t["before"][b][0] for b in ("M", "L"))
        return (keep, t["after"]["XS"][0] + t["after"]["S"][0], -k)
    best = max(range(n_method), key=better)
    best_any = max(range(n_method), key=lambda k: (pooled[k]["after"]["XS"][0] + pooled[k]["after"]["S"][0], -k))
    L = []
    w = L.append
    w("# 事后吸附（snap）：把建好的小实例挪到清单 v2 条目的位置，开发集上的测量\n")
    w("代码 `src/smallobj/snap.py`，本页由 `scripts/snap_dev.py` 生成（数字都在 `summary.json`，预先定的配置下每一对的记录在 "
      "`moves.json`）。只读开发集的运行，不往运行目录里写，也没有重跑任何模型。\n")
    w("## 做法\n")
    w("对一次运行里最长边 < 0.5 m 的实例（算分的实例，已去结构件）：\n")
    w("1. **对应**（一个实例最多对一个条目，一个条目最多给一个实例）。条目来自去重后的核对表 "
      "`perception/<id>/inventory_v2_list.json`。\n"
      "   - nearest：中心距离 ≤ 门槛、最长边之比 ≤ 门槛的条目是候选，按距离从近到远一对一地取。\n"
      "   - 类别相容（可开可关）：条目的 label 或某个 alt_label 的中心词（最后一个词）出现在实例的词里（实例 id 和类别"
      "按非字母切开、变单数、去掉方位和颜色这类词），或者实例类别的中心词出现在条目的词里；另有 14 组同义词"
      "（outlet/socket、cushion/pillow、cup/mug/glass、picture/frame/painting 等，见 `snap.SYNONYMS`）。\n"
      "   - decisions：运行自己的 `inventory_decisions.json`，只在它指的就是这份核对表时用"
      "（键都是核对表的 item_id，并且盖住 ≥ 90% 的条目）。\n")
    w("2. **挪**：只平移到条目的中心，实例自己的尺寸和朝向不变。另试了两种高度：高度不变（只挪水平位置）、"
      "保持离支撑面的高度（支撑按 `handoff.supports` 的规则找）。\n")
    w("3. **验收**（只用图像）：在条目有掩码的帧里（`sam3_objects_v2/`，条目 → 掩码的对应照建清单的做法重算，"
      "和 `inventory_v2.json` 里存的帧数、最好一帧的框逐条核对），实例框的投影（8 个角的凸包）和条目掩码的 IoU，"
      "各帧取平均；挪之后要比挪之前高出一个量才挪。深度一致：掩码里 MoGe 深度的中位数到挪后的框的深度范围的距离"
      "（各帧取中位数）不超过上限。\n")
    w("**预先定的配置**（看结果之前写下的，数取自打分口径里现成的门槛）：nearest、距离 ≤ 0.30 m（宽松门槛的绝对距离）、"
      "最长边之比 ≤ 1.5（严格判据 D 的尺寸范围）、看类别、中心对中心、IoU 提高 ≥ 0.10、深度 ≤ 0.10 m。\n")
    w("**预先定的门槛**：开发集运行合起来，XS+S 目标里 correct 的占比至少涨 5 个百分点，M、L 的 correct 不掉。\n")
    w("验收不是独立证据：条目的框就是用同一批掩码和深度拟出来的，\"挪之后\"的重合天然偏高。它实际检查的是实例现在的位置"
      "在图里对不上这个条目、实例的尺寸在图里和掩码相称、条目在多帧之间自洽；条目自己放错了它拦不住。\n")
    w("## 用到的运行\n")
    w(f"开发集 5 个场景里只有 3 个有带 export/ 和 score_sim3.json 的运行，共 {len(used)} 次；"
      "47331319、42899698 还没有运行（清单 v2 有，没法测）。`runs/_interrupted`、`runs/_superseded` 没看。\n")
    w("| 运行 | 算分的实例 | 小实例（< 0.5 m） | 有 inventory_decisions | 指的是核对表 v2 | 基线和 score_sim3.json 不一致的行 |\n|---|---|---|---|---|---|")
    for m, r in zip(runs_meta, per_cfg[0]):
        w(f"| {m['run']} | {m['instances']} | {r['eligible']} | {'有' if m['has_decisions'] else '—'} | "
          f"{'是' if m['decisions_match_v2'] else ('否' if m['has_decisions'] else '—')} | {m['baseline_mismatch']} |")
    w("")
    for run, why in skipped:
        w(f"- 没用 `{'/'.join(run.parts[-3:])}`：{why}")
    w("\n| 场景 | 核对项 | 对齐残差中位数 | 尺度 | 真值 XS / S / M / L | 条目 ↔ 掩码核对不上的条数 |\n|---|---|---|---|---|---|")
    for sid, m in scenes_meta.items():
        w(f"| {sid} | {m['entries']} | {100 * m['align_residual_m']:.1f} cm | {m['align_s']:.3f} | "
          + " / ".join(str(m["gt"][b]) for b in BINS) + f" | {m['det_mismatch']} |")
    w("\n核对表里小条目（最长边 < 0.5 m）自己的框投回自己的掩码：\n")
    w("| 场景 | 小条目 | 只在 1 帧里有掩码 | 和自己掩码的 IoU 中位数 | IoU < 0.05 的 | 其中 settled_on 不是空的 |\n|---|---|---|---|---|---|")
    for sid, m in scenes_meta.items():
        c = m["self_check"]
        w(f"| {sid} | {c['small_entries']} | {c['one_frame']} | {c['self_iou_median']:.2f} | {c['self_iou_lt_0.05']} | "
          f"{c['of_which_settled']} |")
    w("\nA2 / A3r / A3v 的 `inventory_decisions.json` 指的是 Boxer 清单（b###），不是核对表 v2，所以 decisions 对应在现有的"
      "开发集运行上一次也用不上（A5 的运行出来之后才有）；下面全是 nearest。P0 / P0c 不是 agent 建的（清单框直接摆进去），"
      "也列在里面，另给只算 agent 运行（A 开头）的合计。\n")
    w("## 预先定的配置：每次运行和合计\n")
    w("每档三个数是 correct / misplaced / missed（判据 D，Sim(3) 对齐），箭头前是挪之前、后是挪之后。"
      "后四列只数被挪的实例：\"correct→坏\" = 原来 correct、挪完变成 misplaced 或没配上。\n")
    w(HEAD.format("运行"))
    for name, r in zip(order, per_cfg[0]):
        w(row(name, r))
    w(row("**合计（全部运行）**", pooled[0]))
    w(row("**合计（agent 运行）**", pooled_agent[0]))
    w("")
    w("## 阈值扫描（全部运行合计）\n")
    w("从预先定的配置出发一次只改一项；最后两行是**真值验收**：对应上的一个一个试，挪了以后全场 correct 数变多才留。"
      "这是用真值挑的，是上界，不是方法。\n")
    w(HEAD.format("配置"))
    for k, c in enumerate(sweep):
        w(row(("**预先定的**：" if k == 0 else "") + cfg_name(c), pooled[k]))
    for k in range(n_method, len(configs)):
        w(row("**上界**：" + cfg_name(configs[k]), pooled[k]))
    w("\n距离 × IoU 提高量 × 是否看类别 的小网格（其余同预先定的配置；格子里是 挪了几个 / XS+S correct 的变化 / M+L correct 的变化）：\n")
    w("| 类别 | 距离 | 提高 ≥ 0.05 | ≥ 0.1 | ≥ 0.2 | ≥ 0.3 |\n|---|---|---|---|---|---|")
    lookup = {json.dumps(c, sort_keys=True): k for k, c in enumerate(configs[:n_method])}
    for u in (True, False):
        for d in (0.2, 0.3, 0.4, 0.6):
            cells = []
            for m in (0.05, 0.1, 0.2, 0.3):
                t = pooled[lookup[json.dumps(dict(DECLARED, max_dist=d, margin=m, use_labels=u), sort_keys=True)]]
                ds = sum(t["after"][b][0] - t["before"][b][0] for b in ("XS", "S"))
                dl = sum(t["after"][b][0] - t["before"][b][0] for b in ("M", "L"))
                cells.append(f"{t['accepted']} / {ds:+d} / {dl:+d}")
            w(f"| {'看' if u else '不看'} | ≤ {d:g} m | " + " | ".join(cells) + " |")
    w("")
    w("## 最好的非真值配置和上界\n")
    w(f"在上面试过的 {n_method} 个配置里，按\"M、L 不掉的前提下 XS+S correct 最多\"挑（并列取离预先定的近的）。"
      "这是在同一批运行上挑的，数字偏乐观。\n")
    w(HEAD.format("配置"))
    w(row("预先定的", pooled[0]))
    w(row("最好的非真值配置：" + cfg_name(configs[best]), pooled[best]))
    w(row("同上，只算 agent 运行", pooled_agent[best]))
    if best_any != best:
        w(row("不管 M、L 时 XS+S correct 最多的：" + cfg_name(configs[best_any]), pooled[best_any]))
        w(row("同上，只算 agent 运行", pooled_agent[best_any]))
    for k in range(n_method, len(configs)):
        w(row("上界：" + cfg_name(configs[k]), pooled[k]))
        w(row("同上，只算 agent 运行", pooled_agent[k]))
    w("")
    for title, pl in (("全部运行", pooled), ("只算 agent 运行", pooled_agent)):
        n_small = sum(pl[0]["before"]["XS"]) + sum(pl[0]["before"]["S"])
        w(f"{title}（correct 的个数；XS+S 目标 {n_small} 个，每次运行各算一遍）：\n")
        w("| | XS | S | M | L | XS+S correct 占比 |\n|---|---|---|---|---|---|")
        w("| 挪之前 | " + " | ".join(str(pl[0]["before"][b][0]) for b in BINS)
          + f" | {100 * small_share(pl[0]['before']):.1f}% |")
        for label, k in (("预先定的", 0), ("最好的非真值配置", best), ("真值验收（上界）", n_method),
                         ("真值验收 + 最松的对应（上界）", n_method + 1)):
            w(f"| {label} | " + " | ".join(str(pl[k]["after"][b][0]) for b in BINS)
              + f" | {100 * small_share(pl[k]['after']):.1f}%（{gate(pl[k])[0]:+.1f}） |")
        w("")
    w("## 门槛过没过\n")
    g0, g1 = gate(pooled[0]), gate(pooled[best])
    ga0, ga1 = gate(pooled_agent[0]), gate(pooled_agent[best])
    go = gate(pooled[n_method + 1])
    ml = "、".join(f"{b} {pooled[0]['before'][b][0]} → {pooled[0]['after'][b][0]}" for b in ("M", "L"))
    gb, gba = gate(pooled[n_method]), gate(pooled_agent[n_method])
    w(f"**{'过了' if g0[2] else '没过'}。** 预先定的配置：XS+S correct 占比 {g0[0]:+.1f} 个百分点（要 ≥ +5），"
      f"M、L 的 correct：{ml}（{'没掉' if g0[1] else '掉了'}）；只算 agent 运行 {ga0[0]:+.1f}。"
      f"在同一批运行上挑出来的最好配置是 {g1[0]:+.1f}（agent 运行 {ga1[0]:+.1f}），{'过' if g1[2] else '不过'}。"
      f"上界：同样的对应、换成真值验收是 {gb[0]:+.1f}（agent 运行 {gba[0]:+.1f}）；对应放到最松再用真值验收是 {go[0]:+.1f}"
      f"（agent 运行 {gate(pooled_agent[n_method + 1])[0]:+.1f}）。\n")
    w("## 卡在哪（全部运行合计）\n")
    w("基线里 XS、S 档 misplaced 的目标（建了、配上了、没过严格判据；每次运行各算一遍），按真值事后归因。\"位置够准的条目\" = 把这个实例"
      "平移到那条的中心就能过严格判据 D（不管门槛，核对表里任何一条都算）。\n")
    cols = [diag_by_cfg.get((kk, pn), {}) for kk in (0, best) for pn in ("all", "agent")]
    diag, diag_best = cols[0], cols[2]
    w("| 情况 | 预先定的配置 | 其中 agent 运行 | 最好的非真值配置 | 其中 agent 运行 |\n|---|---|---|---|---|")
    for k in sorted(set().union(*cols), key=lambda k: (-diag.get(k, 0), k)):
        w(f"| {k} | " + " | ".join(str(c.get(k, 0)) for c in cols) + " |")
    w("| 合计 | " + " | ".join(str(sum(c.values())) for c in cols) + " |")
    w("")
    acc = [m for m in moves if m["accepted"]]
    w(f"被挪的实例（{len(acc)} 个）挪了多远：中位数 "
      f"{100 * float(np.median([m['move_m'] for m in acc])) if acc else float('nan'):.0f} cm；"
      f"对应上的 {len(moves)} 对里，条目只在 1 帧里有掩码的 {sum(m['n_frames'] == 1 for m in moves)} 对，"
      f"挪之前 IoU 的中位数 {float(np.median([m['iou_before'] for m in moves if m['iou_before'] is not None])):.2f}、"
      f"挪之后 {float(np.median([m['iou_after'] for m in moves if m['iou_after'] is not None])):.2f}。\n")
    if side:
        w("## decisions 对应（运行自己的 inventory_decisions.json 指的就是核对表 v2 的运行）\n")
        w(HEAD.format("运行"))
        for name, r in side:
            w(row(name, r))
        w("")
    if boxer:
        w("## 旁证：decisions 对应，条目换成运行自己拿到的 Boxer 清单\n")
        w("A2 / A3r / A3v 的 decisions 指的是 Boxer 清单（`inventory.json`），掩码用 `item_masks/`。这不是要测的那个想法"
          "（Boxer 的框不是清单 v2，而且 Boxer 用 CA-1M 的训练集训练过），只是看 decisions 这条对应路在真实运行上长什么样。\n")
        w(HEAD.format("运行 / 配置"))
        labels_ = []
        for name, label, r in boxer:
            w(row(f"{name}：{label}", r))
            if label not in labels_:
                labels_.append(label)
        for label in labels_:
            w(row(f"**合计**：{label}", pool([r for _, lb, r in boxer if lb == label])))
        w("")
    w("<!-- 以下\"读法\"是 11-20 对着上面这批运行写的；运行变了要重看 -->")
    notes = OUT / "notes.md"
    if notes.exists():
        w(notes.read_text().rstrip() + "\n")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "README.md").write_text("\n".join(L) + "\n")

    def slim(r):
        return {k: v for k, v in r.items() if k not in ("log", "pairs")}
    summary = {"runs": runs_meta, "skipped": [["/".join(p.parts[-3:]), why] for p, why in skipped], "scenes": scenes_meta,
               "boxer_side": [{"run": n, "config": lb, **slim(r)} for n, lb, r in boxer],
               "declared": DECLARED, "best_index": best, "best_any_index": best_any,
               "diagnosis": {"declared": cols[0], "declared_agent": cols[1], "best": cols[2], "best_agent": cols[3]},
               "configs": [{"config": c, "name": cfg_name(c), "pooled": slim(pooled[k]), "pooled_agent": slim(pooled_agent[k]),
                            "gate": dict(zip(("gain_pp", "ml_kept", "met"), gate(pooled[k]))),
                            "per_run": {n: slim(r) for n, r in zip(order, per_cfg[k])}} for k, c in enumerate(configs)]}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    (OUT / "moves.json").write_text(json.dumps(
        [{k: v for k, v in m.items() if k != "after"} | {"center_after": m["after"]["center"]} for m in moves],
        indent=1, ensure_ascii=False) + "\n")
    print(f"写到 {OUT}，{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
