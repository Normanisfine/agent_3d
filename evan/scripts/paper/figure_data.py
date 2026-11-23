"""论文图表用的数：从已有运行重新配对一遍（判据 D、相机拟合尺度，和主表同一套代码和门槛），写一份 paper/smallobj/figures/data.json。

比 results/test_opus_6rooms/summary.json 多出来的：每个配上的小目标的中心偏差和尺寸比（看摆错是偏了还是大小不对）、
各组和各份清单"配上真值的实例占比"（清单当成直接摆好的物体来打分，不过 agent）、A5 两遍。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/paper/figure_data.py
"""
import json
from pathlib import Path

import numpy as np

from smallobj import align, boxes, evaluate, inventory, score

PROJ = Path(__file__).resolve().parents[2]
ROOMS = ["42897538", "42898849", "42899617", "42899712", "42899729", "44358442"]
ARMS = {"A0": ("A0-claude", "0"), "A1": ("A1-claude", "0"), "A2": ("A2-claude", "0"), "A5": ("A5-claude", "0"), "A5s1": ("A5-claude", "1")}
LISTS = {"boxer": "inventory.json", "revised": "inventory_v2.json", "checklist": "inventory_v2_list.json"}
BINS = evaluate.BINS
SMALL = ("XS", "S")


def tally(preds, gts, th, with_offsets=False):
    rows = evaluate.outcomes(preds, gts, th)
    by_id = {p["object_id"]: p for p in preds}
    gt_by_id = {g["object_id"]: g for g in gts}
    out = {"n": len(preds), "matched": len({r["pred_id"] for r in rows if r.get("pred_id")})}
    for b in BINS:
        sub = [r for r in rows if r["bin"] == b]
        out[b] = {k: sum(r["D"] == k for r in sub) for k in ("correct", "misplaced", "missed")} | {"n": len(sub)}
    if with_offsets:  # 配上的小目标：中心距离（米）、允许的中心距离、最长边之比
        out["offsets"] = []
        for r in rows:
            if r["bin"] in SMALL and r.get("pred_id"):
                p, g = by_id[r["pred_id"]], gt_by_id[r["gt_id"]]
                d = float(np.linalg.norm(np.subtract(p["center"], g["center"])))
                allowed = max(th["strict_floor_m"], th["dhat_strict"] * 0.5 * float(np.linalg.norm(g["size"])))
                ratio = max(p["size"]) / max(g["size"])
                out["offsets"].append({"bin": r["bin"], "D": r["D"], "d": round(d, 4), "allowed": round(allowed, 4), "ratio": round(ratio, 4),
                                       "center_ok": d <= allowed, "size_ok": th["size_ratio"][0] <= ratio <= th["size_ratio"][1]})
    return out


def main():
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    data = {"rooms": ROOMS, "arms": {a: {} for a in ARMS}, "lists": {l: {} for l in LISTS}, "targets": {}}
    for sid in ROOMS:
        P, scene = PROJ / "perception" / sid, PROJ / "scenes" / sid
        gts = boxes.load(scene / "gt" / "boxes.json")
        tf = align.pipeline_to_gt(P / "bundle", scene, with_scale=True)
        data["targets"][sid] = {b: sum(evaluate.size_bin(g, th["bin_edges_m"]) == b for g in gts) for b in BINS}
        for name, fname in LISTS.items():
            items = inventory.load(P / fname)
            moved = [align.apply(it, tf["s"], tf["R"], tf["t"]) for it in items]
            data["lists"][name][sid] = tally(moved, gts, th)
        for name, (arm, seed) in ARMS.items():
            run = PROJ / "runs" / arm / sid / seed
            preds = score.prepare_predictions(boxes.load(run / "export" / "objects.json"), tf, th)
            t = tally(preds, gts, th, with_offsets=True)
            log = json.loads((run / "run_log.json").read_text())
            t["minutes"], t["usd"] = log["wall_s"] / 60, log["usage"]["cost_usd_equiv"]
            saved = json.loads((run / "score_sim3.json").read_text())  # 和已存的打分对一下，防止这里算的和主表不一致
            for b in BINS:
                assert t[b]["correct"] == sum(r["D"] == "correct" and r["bin"] == b for r in saved["rows"]), (sid, name, b)
            dec = run / "inventory_decisions.json"
            if name.startswith("A5") and dec.exists():
                acts = [v.get("action", "?") for v in json.loads(dec.read_text()).values()]
                t["decisions"] = {k: acts.count(k) for k in sorted(set(acts))}
            data["arms"][name][sid] = t
        print(sid, "done", flush=True)
    out = PROJ / "paper" / "smallobj" / "figures" / "data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    for name in list(LISTS) + list(ARMS):
        d = data["lists" if name in LISTS else "arms"][name]
        small = sum(d[s][b]["correct"] for s in ROOMS for b in SMALL)
        print(f"{name:10s} n={sum(d[s]['n'] for s in ROOMS):5d} matched={sum(d[s]['matched'] for s in ROOMS):4d} small_correct={small:4d} "
              + " ".join(f"{b}:{sum(d[s][b]['correct'] for s in ROOMS)}/{sum(d[s][b]['misplaced'] for s in ROOMS)}/{sum(d[s][b]['missed'] for s in ROOMS)}" for b in BINS))
    for name in ARMS:
        offs = [o for s in ROOMS for o in data["arms"][name][s]["offsets"]]
        mis = [o for o in offs if o["D"] == "misplaced"]
        print(f"{name:5s} matched small {len(offs)}, misplaced {len(mis)}: center only {sum((not o['center_ok']) and o['size_ok'] for o in mis)}, "
              f"size only {sum(o['center_ok'] and not o['size_ok'] for o in mis)}, both {sum((not o['center_ok']) and not o['size_ok'] for o in mis)}; "
              f"median d of matched {np.median([o['d'] for o in offs]) * 100:.1f} cm" if offs else name)


if __name__ == "__main__":
    main()
