"""在 10 个开发物体上校准生成验收门（设计 §6、§8：生成验收门槛只在开发集上调）。

用法：PYTHONPATH=src .runtime/venv/bin/python scripts/calibrate_gate.py [--write]
步骤：固定种子从 5 个开发场景的 Boxer 清单里抽"检测到"了的 5 个 XS、5 个 S → 各生成 2 个候选 → place_mesh
→ 对齐到真值后，比较"摆好的网格框"和"清单框（方块版）"对同一个真值的 d̂ 和判据 D 结局。
门槛在小网格上搜：通过门槛的候选里，按判据 D 的结局没有一个比它的方块版差，在这个前提下放行最多的那组
（并列时取 d̂ 平均改善最大的）。--reselect 用存下的结果重选，不重新生成。
--write 时把选中的门槛写进 configs/gen_gate.json。结果写 results/gate_calibration.md。
"""
import argparse
import itertools
import json
import random
from pathlib import Path

from smallobj import align, boxes, evaluate, gen3d, place, score

PROJ = Path(__file__).resolve().parent.parent
SEED = 20261020


def pick_objects(th):
    dev = json.loads((PROJ / "configs" / "splits.json").read_text())["dev"]
    pool = {"XS": [], "S": []}
    for sid in dev:
        items = json.loads((PROJ / "perception" / sid / "inventory.json").read_text())
        gts = boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")
        tf = align.pipeline_to_gt(PROJ / "perception" / sid / "bundle", PROJ / "scenes" / sid, with_scale=True)
        moved = [align.apply(it, tf["s"], tf["R"], tf["t"]) for it in items]
        for i, j in evaluate.match(moved, gts, th):
            b = evaluate.size_bin(gts[j], th["bin_edges_m"])
            if b in pool:
                pool[b].append((sid, items[i]["item_id"], gts[j]["object_id"]))
    rng = random.Random(SEED)
    return [x for b in ("XS", "S") for x in rng.sample(sorted(pool[b]), min(5, len(pool[b])))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--reselect", action="store_true", help="不重新生成，用 results/gate_calibration.json 里存的结果重选门槛")
    args = ap.parse_args()
    if args.reselect:
        saved = json.loads((PROJ / "results" / "gate_calibration.json").read_text())
        best, grid = choose_gate(saved["rows"], json.loads((PROJ / "configs" / "gen_gate.json").read_text()))
        write_report(saved.get("chosen", []), saved["rows"], grid, best, args.write)
        return
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    chosen = pick_objects(th)
    rows = []
    for sid, iid, gid in chosen:
        gts = {g["object_id"]: g for g in boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")}
        g = gts[gid]
        tf = align.pipeline_to_gt(PROJ / "perception" / sid / "bundle", PROJ / "scenes" / sid, with_scale=True)
        item = next(it for it in json.loads((PROJ / "perception" / sid / "inventory.json").read_text()) if it["item_id"] == iid)
        box_gt = align.apply(item, tf["s"], tf["R"], tf["t"])
        box_d = evaluate.dhat(box_gt, g)
        box_D = evaluate.outcomes([box_gt], [g], th)[0]["D"]
        support = 0.0 if item["center"][2] - item["size"][2] / 2 < 0.05 else None
        for gen in gen3d.request(sid, [iid], n_candidates=2, max_gen=None, budget_name="budget_calibration"):
            row = {"scene": sid, "item": iid, "category": item["category"], "bin": evaluate.size_bin(g, th["bin_edges_m"]),
                   "candidate": gen["candidate_id"], "gen_status": gen["status"], "box_dhat": box_d, "box_D": box_D}
            if gen["status"] == "ok":
                pl = place.place_mesh(sid, iid, gen["candidate_id"], support_z=support)
                pb = align.apply(pl["placed_box"], tf["s"], tf["R"], tf["t"])
                row.update(status=pl["status"], fit=pl["fit"], longest=max(pl["placed_box"]["size"]), gen_dhat=evaluate.dhat(pb, g),
                           gen_D=evaluate.outcomes([pb], [g], th)[0]["D"])
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "fit"}), flush=True)
    best, grid = choose_gate(rows, json.loads((PROJ / "configs" / "gen_gate.json").read_text()))
    write_report(chosen, rows, grid, best, args.write)


RANK = {"correct": 2, "misplaced": 1, "missed": 0}


def choose_gate(rows, base):
    """门槛网格：放行的候选里，按判据 D 的结局没有一个比它的方块版差（计划 Task 10）；在这个前提下放行最多，
    并列时取 d̂ 平均改善最大的。返回 (选中的组或 None, 整个网格)。"""
    placed = [r for r in rows if "fit" in r]
    grid = []
    for iou_min, margin, ch_rel in itertools.product((0.4, 0.5, 0.6, 0.7), (0.0, 0.03, 0.05, 0.1), (0.1, 0.2)):
        gate = dict(base, sil_iou_min=iou_min, sil_margin=margin, chamfer_rel=ch_rel)
        passed = [r for r in placed if place.gate(r["fit"], r["fit"]["size_ratio"], r["fit"]["penetration_m"], r["longest"], gate)]
        worse = [r for r in passed if RANK[r["gen_D"]] < RANK[r["box_D"]]]
        grid.append({"sil_iou_min": iou_min, "sil_margin": margin, "chamfer_rel": ch_rel, "n_pass": len(passed),
                     "n_worse": len(worse), "mean_gain_dhat": (sum(r["box_dhat"] - r["gen_dhat"] for r in passed) / len(passed)) if passed else 0.0})
    ok = [g for g in grid if g["n_worse"] == 0 and g["n_pass"] > 0]
    # 放行一样多、改善一样大时取最严的那组（IoU 下限高、要求比方块版高出更多、Chamfer 容差小）
    best = max(ok, key=lambda g: (g["n_pass"], round(g["mean_gain_dhat"], 6), g["sil_iou_min"], g["sil_margin"], -g["chamfer_rel"])) if ok else None
    return best, grid


def write_report(chosen, rows, grid, best, write):
    base = json.loads((PROJ / "configs" / "gen_gate.json").read_text())
    lines = ["# 生成验收门在开发物体上的校准", "",
             f"物体：{len(chosen) or len({(r['scene'], r['item']) for r in rows})} 个（固定种子 {SEED}，5 个开发场景 Boxer 清单里检测到的 XS、S 各至多 5 个），每个 2 个候选，"
             "后端 Hunyuan3D-2mini（只生成形状）。d̂ 越小越好；\"方块版\"是清单框本身。", "",
             "| 场景 | 物体 | 类别 | 档 | 候选 | 生成 | 放置 | 剪影 IoU | 方块 IoU | Chamfer cm | 尺寸比 | 网格 d̂ / D | 方块 d̂ / D |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        f = r.get("fit", {})
        lines.append(f"| {r['scene']} | {r['item']} | {r['category']} | {r['bin']} | {r['candidate']} | {r['gen_status']} | "
                     f"{r.get('status', '-')} | {f.get('sil_iou_mean', float('nan')):.2f} | {f.get('primitive_sil_iou', float('nan')):.2f} | "
                     f"{f.get('chamfer_obs2mesh_cm', float('nan')):.1f} | {[round(x, 2) for x in f.get('size_ratio', [])]} | "
                     f"{r.get('gen_dhat', float('nan')):.2f} / {r.get('gen_D', '-')} | {r['box_dhat']:.2f} / {r['box_D']} |")
    lines += ["", "门槛网格（只列放行数 > 0 的）：", "", "| sil_iou_min | sil_margin | chamfer_rel | 放行 | 比方块差 | 平均 d̂ 改善 |", "|---|---|---|---|---|---|"]
    lines += [f"| {g['sil_iou_min']} | {g['sil_margin']} | {g['chamfer_rel']} | {g['n_pass']} | {g['n_worse']} | {g['mean_gain_dhat']:.3f} |"
              for g in grid if g["n_pass"] > 0]
    if best:
        lines += ["", f"**选定**：sil_iou_min={best['sil_iou_min']}，sil_margin={best['sil_margin']}，chamfer_rel={best['chamfer_rel']}"
                  f"（放行 {best['n_pass']} 个、没有一个比方块版差）。"]
    else:
        lines += ["", "**没有一组门槛能放行而不出现比方块版差（判据 D 的结局）的候选**：保留设计 §6 的初值。"]
    (PROJ / "results" / "gate_calibration.md").write_text("\n".join(lines) + "\n")
    (PROJ / "results" / "gate_calibration.json").write_text(json.dumps({"chosen": chosen, "rows": rows, "grid": grid, "best": best}, indent=1) + "\n")
    if write and best:
        cfg = dict(base, sil_iou_min=best["sil_iou_min"], sil_margin=best["sil_margin"], chamfer_rel=best["chamfer_rel"],
                   note="10-26 在开发物体上校准后冻结（results/gate_calibration.md）")
        (PROJ / "configs" / "gen_gate.json").write_text(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
    print("\n".join(lines[-3:]))


if __name__ == "__main__":
    main()
