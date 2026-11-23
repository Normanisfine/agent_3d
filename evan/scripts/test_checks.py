"""6 个测试房间上给主表配的三项核对（A5 的提示词和去重规则已在标签 a5-frozen 冻结，之后才看测试集的清单分数）。

1. 清单本身的分数（不过 agent）：Boxer 清单、清单 v2、去重后的逐项清单，每档"检测到 / 建对"，条目数和配上真值的条目比例。
2. 各组多建的物体：重建实例数、配上真值的个数、没配上的按实例最长边分档。
3. 碰巧基线：每个重建实例水平随机挪开 0.5–1.5 米、挪 20 次取平均后的建对数（report.chance_by_bin 的做法，这里报个数）。
   实例越多越容易碰上别的真值；真实建对数远高于它，才说明提升不是靠多建框。
另列 A5 每个房间对清单逐项的表态（built / duplicate / part / skipped）。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/test_checks.py   输出 results/test_opus_6rooms/checks.md、checks.json
"""
import collections
import json
from pathlib import Path

import numpy as np

from smallobj import align, boxes, evaluate, inventory, score

PROJ = Path(__file__).resolve().parent.parent
ROOMS = ["42897538", "42898849", "42899617", "42899712", "42899729", "44358442"]
ARMS = [("A0-claude", "基线"), ("A1-claude", "All objects"), ("A2-claude", "Inventory（Boxer 清单）"), ("A5-claude", "逐项清单（清单 v2）")]
LISTS = [("inventory.json", "Boxer 清单"), ("inventory_v2.json", "清单 v2"), ("inventory_v2_list.json", "去重后的逐项清单")]
BINS = evaluate.BINS
SMALL = ("XS", "S")


def correct_by_bin(preds, gts, th):
    rows = evaluate.outcomes(preds, gts, th)
    return {b: sum(r["D"] == "correct" for r in rows if r["bin"] == b) for b in BINS}, rows


def chance_correct(preds, gts, th, n=20, seed=0, shift=(0.5, 1.5)):
    rng = np.random.default_rng(seed)
    acc = {b: 0.0 for b in BINS}
    for _ in range(n):
        moved = [dict(p, center=(np.asarray(p["center"], float) + [r * np.cos(a), r * np.sin(a), 0.0]).tolist())
                 for p in preds for a, r in [(rng.uniform(0, 2 * np.pi), rng.uniform(*shift))]]
        for b, c in correct_by_bin(moved, gts, th)[0].items():
            acc[b] += c / n
    return acc


def main():
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    edges = th["bin_edges_m"]
    inv = {name: collections.Counter() for _, name in LISTS}
    arms = {name: collections.Counter() for _, name in ARMS}
    per_room, decisions = [], {}
    for sid in ROOMS:
        P, scene = PROJ / "perception" / sid, PROJ / "scenes" / sid
        gts = boxes.load(scene / "gt" / "boxes.json")
        tf = align.pipeline_to_gt(P / "bundle", scene, with_scale=True)
        for fname, name in LISTS:
            items = inventory.load(P / fname)
            rows = score.score_inventory(items, gts, tf, th)
            t = inv[name]
            t["rooms"] += 1
            t["items"] += len(items)
            t["matched"] += len({r["pred_id"] for r in rows if r["D"] != "missed" and r.get("pred_id")})
            for b in BINS:
                sub = [r for r in rows if r["bin"] == b]
                t[b, "n"] += len(sub)
                t[b, "det"] += sum(r["D"] != "missed" for r in sub)
                t[b, "cor"] += sum(r["D"] == "correct" for r in sub)
        for arm, name in ARMS:
            run = PROJ / "runs" / arm / sid / "0"
            if not (run / "run_log.json").exists() or not (run / "export" / "objects.json").exists():
                continue
            preds = score.prepare_predictions(boxes.load(run / "export" / "objects.json"), tf, th)
            real, rows = correct_by_bin(preds, gts, th)
            chance = chance_correct(preds, gts, th)
            used = {r["pred_id"] for r in rows if r["D"] != "missed" and r.get("pred_id")}
            t = arms[name]
            t["rooms"] += 1
            t["built"] += len(preds)
            t["matched"] += len(used)
            for p in preds:
                b = evaluate.size_bin(p, edges)
                t["built", b] += 1
                t["unmatched", b] += p["object_id"] not in used
            for b in BINS:
                t["real", b] += real[b]
                t["chance", b] += chance[b]
            per_room.append({"room": sid, "arm": name, "built": len(preds), "matched": len(used),
                             "small_correct": sum(real[b] for b in SMALL), "small_chance": round(sum(chance[b] for b in SMALL), 1)})
            dec = run / "inventory_decisions.json"
            if arm == "A5-claude" and dec.exists():
                decisions[sid] = dict(collections.Counter(v.get("action", "?") for v in json.loads(dec.read_text()).values()))
        print(sid, "done", flush=True)

    L = ["# 6 个测试房间：清单本身的分数、多建的物体、碰巧基线", "",
         "判据 D、宽松门槛、相机拟合尺度。A5 的提示词和去重规则在标签 `a5-frozen` 冻结之后才算的这些数。", "",
         "## 清单本身（不过 agent）", "",
         "每格是 检测到 / 建对，占该档真值的比例；把清单里的每个框当成已经摆好的物体来打分。", "",
         "| 清单 | 条目数 | 配上真值的条目 | " + " | ".join(f"{b}（{inv[LISTS[0][1]][b, 'n']}）" for b in BINS) + " |", "|---|---|---|" + "---|" * len(BINS)]
    for _, name in LISTS:
        t = inv[name]
        L.append(f"| {name} | {t['items']} | {t['matched'] / t['items']:.0%} | " + " | ".join(
            f"{t[b, 'det'] / t[b, 'n']:.0%} / {t[b, 'cor'] / t[b, 'n']:.0%}" for b in BINS) + " |")
    L += ["", "## 各组重建的实例", "",
          "没配上的按实例自己的最长边分档。只合计该组已有运行的房间。", "",
          "| 组 | 房间数 | 重建实例 | 配上真值 | 没配上 | 其中 XS | S | M | L |", "|---|---|---|---|---|---|---|---|---|"]
    for _, name in ARMS:
        t = arms[name]
        if not t["rooms"]:
            continue
        L.append(f"| {name} | {t['rooms']} | {t['built']} | {t['matched']}（{t['matched'] / t['built']:.0%}） | {t['built'] - t['matched']} | "
                 + " | ".join(str(t["unmatched", b]) for b in BINS) + " |")
    L += ["", "## 碰巧基线", "",
          "每格是 真实建对数 / 实例随机挪开后的平均建对数。", "",
          "| 组 | 房间数 | " + " | ".join(BINS) + " |", "|---|---|" + "---|" * len(BINS)]
    for _, name in ARMS:
        t = arms[name]
        if t["rooms"]:
            L.append(f"| {name} | {t['rooms']} | " + " | ".join(f"{t['real', b]} / {t['chance', b]:.1f}" for b in BINS) + " |")
    L += ["", "### 各房间 50 cm 以下（XS + S）", "", "| 房间 | 组 | 重建实例 | 配上真值 | 真实建对 | 碰巧建对 |", "|---|---|---|---|---|---|"]
    L += [f"| {r['room']} | {r['arm']} | {r['built']} | {r['matched']} | {r['small_correct']} | {r['small_chance']} |" for r in per_room]
    if decisions:
        keys = ["built", "duplicate", "part", "skipped"]
        L += ["", "## A5 对清单逐项的表态", "", "| 房间 | 清单条目 | " + " | ".join(keys) + " | 其他 |", "|---|---|" + "---|" * (len(keys) + 1)]
        for sid, d in decisions.items():
            L.append(f"| {sid} | {sum(d.values())} | " + " | ".join(str(d.get(k, 0)) for k in keys)
                     + f" | {sum(v for k, v in d.items() if k not in keys)} |")
    out = PROJ / "results" / "test_opus_6rooms"
    (out / "checks.md").write_text("\n".join(L) + "\n")
    (out / "checks.json").write_text(json.dumps({"per_room": per_room, "decisions": decisions}, ensure_ascii=False, indent=1) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
