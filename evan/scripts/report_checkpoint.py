"""汇总开发（或测试）场景上的运行，出中期检查的图和表。

用法：PYTHONPATH=src .runtime/venv/bin/python scripts/report_checkpoint.py [--split dev|test] [--driver codex|claude] [--out results/checkpoint]
--driver claude 读 runs/<arm>-claude/（10-27 起的主实验：Opus 5.5、AHa-3D 原版规则）；默认 codex 读 runs/<arm>/（旧规则的对照）。
读 runs/<arm>/<scene>/<seed>/{score_sim3.json, score_noscale.json, run_log.json}；
"看得见"：A0/A1 按流程分辨率，有清单的组（P0、P0c、A2、A3、A4）按高清帧分辨率（设计 §9.5），各算一次，
缓存到 scenes/<scene>/gt/visibility_<W>x<H>_<像素上限>.json（由真值算出，不放在 agent 读得到的 perception/ 下）。
有清单的组多一关"检测到"：清单框对齐后在宽松门槛内配上的真值。
输出 recall_by_bin.png、funnel.png、funnel_pre_g1.png（对照：G1 之前的口径）、runs.md、sensitivity.md、summary.json。
"""
import argparse
import json
from pathlib import Path

from smallobj import align, boxes, evaluate, report, score, visibility

PROJ = Path(__file__).resolve().parent.parent


ARMS = ("A0", "A1", "A2", "A3r", "A3v", "A4", "P0", "P0c")


def vis_flags(sid, th, hd=False):
    """缓存名带分辨率和像素上限：换成 Betty 的 25.5 万像素感知后不会读到旧缓存。hd=True 按高清帧分辨率算。"""
    bundle = PROJ / "perception" / sid / "bundle"
    if hd:
        wh = tuple(json.loads((PROJ / "perception" / sid / "hd" / "cameras.json").read_text())["size_wh"])
    else:
        wh = tuple(json.loads((bundle / "alignment" / "cameras.json").read_text())["processed_size_wh"])
    perf = PROJ / "perception" / sid / "perf.json"
    pix = json.loads(perf.read_text()).get("pixel_limit", "na") if perf.exists() else "na"
    cache = PROJ / "scenes" / sid / "gt" / f"visibility_{wh[0]}x{wh[1]}_{pix}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    gts = boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")
    flags = visibility.visible_flags(gts, PROJ / "scenes" / sid, bundle, wh, th["visible_min_px"])
    cache.write_text(json.dumps(flags) + "\n")
    return flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--driver", default="codex", choices=["codex", "claude"])
    ap.add_argument("--out", default="results/checkpoint")
    args = ap.parse_args()
    out = PROJ / args.out
    out.mkdir(parents=True, exist_ok=True)
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    scenes = json.loads((PROJ / "configs" / "splits.json").read_text())[args.split]
    split_name = {"dev": "开发", "test": "测试"}[args.split]

    funnels, funnels_abs, rows_md, summary, sens_md = {}, {}, [], {}, []
    ref_vis = {}  # {arm: [流程分辨率下的计数]}，画漏斗里的参考线
    pooled_rows = {}  # {arm: {"sim3": rows, "noscale": rows}}，按物体合并算召回
    # 10-27 G1 冻结后，正式口径已含 30 cm 门槛、10 cm 下限和贪心配对；对照用 G1 之前的口径
    th_old = {k: v for k, v in th.items() if k not in ("loose_abs_m", "strict_floor_m", "match_mode")}
    for run in sorted((PROJ / "runs").glob("*/*/*")):
        arm, sid, seed = run.parts[-3], run.parts[-2], run.parts[-1]
        if args.driver == "claude":
            if not arm.endswith("-claude"):
                continue
            arm = arm[: -len("-claude")]
        if arm not in ARMS or sid not in scenes or not (run / "run_log.json").exists():
            continue  # 不是实验组、不在这个划分里，或者还在跑
        log = json.loads((run / "run_log.json").read_text())
        gts = boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")
        det = None
        if arm in report.ARM_INVENTORY:
            flags = vis_flags(sid, th, hd=True)
            ref_vis.setdefault(arm, []).append(report.funnel_counts(report.missed_rows(gts, th), vis_flags(sid, th)))
            items = json.loads((PROJ / "perception" / sid / report.ARM_INVENTORY[arm]).read_text())
            tf_inv = align.pipeline_to_gt(PROJ / "perception" / sid / "bundle", PROJ / "scenes" / sid, with_scale=True)
            det = {r["gt_id"]: r["D"] != "missed" for r in score.score_inventory(items, gts, tf_inv, th)}
        else:
            flags = vis_flags(sid, th)
        if not (run / "score_sim3.json").exists():
            # 没得到 .blend：所有真值记 missed，照常计入（设计 §5），不做敏感性分析
            rows = report.missed_rows(gts, th)
            funnels.setdefault(arm, []).append(report.funnel_counts(rows, flags, key="D", detected=det))
            funnels_abs.setdefault(arm, []).append(report.funnel_counts(rows, flags, key="D", detected=det))
            for k in ("sim3", "noscale"):
                pooled_rows.setdefault(arm, {}).setdefault(k, []).extend(rows)
            rows_md.append(f"| {arm} | {sid} | {seed} | {log['status']}（无 .blend） | "
                           f"{(log.get('wall_s') or 0)/60:.1f} | - | - | - | {log.get('weekly_delta')} | "
                           f"{log.get('primary_delta')} | 0 | - | 0 | 0 | 0 | 0 |")
            continue
        sc = {k: json.loads((run / f"score_{k}.json").read_text()) for k in ("sim3", "noscale")}
        funnels.setdefault(arm, []).append(report.funnel_counts(sc["sim3"]["rows"], flags, key="D", detected=det))
        for k in ("sim3", "noscale"):
            pooled_rows.setdefault(arm, {}).setdefault(k, []).extend(sc[k]["rows"])
        u = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, **(log.get("usage") or {})}
        rec = {b: round(v["recall_D"], 2) for b, v in sc["sim3"]["summary"].items()}
        al = sc["sim3"]["alignment"]
        flag = "" if score.alignment_ok(al, th) else " ⚠"
        rows_md.append(f"| {arm} | {sid} | {seed} | {log['status']} | {log['wall_s']/60:.1f} | "
                       f"{u['input_tokens']/1e6:.2f} | {u['cached_input_tokens']/1e6:.2f} | {u['output_tokens']/1e3:.0f} | "
                       f"{log.get('weekly_delta')} | {log.get('primary_delta')} | {sc['sim3']['n_pred']} | "
                       f"{100 * al['residual_median_m']:.1f} / {al['s']:.3f}{flag} | "
                       f"{rec.get('XS','-')} | {rec.get('S','-')} | {rec.get('M','-')} | {rec.get('L','-')} |")
        # 敏感性分析：正式口径 vs 30 cm 绝对门槛 vs 随机挪开 0.5–1.5 m 的碰巧基线（判据 D 的"建出来"）。
        # 和正式口径一样，全体真值一起配对后再按档切；正式那一列直接取 score_sim3.json 的结局。
        tf = align.pipeline_to_gt(PROJ / "perception" / sid / "bundle", PROJ / "scenes" / sid, with_scale=True)
        moved = score.prepare_predictions(boxes.load(run / "export" / "objects.json"), tf, th)
        gts = boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")
        rows_old = evaluate.outcomes(moved, gts, th_old)
        funnels_abs.setdefault(arm, []).append(report.funnel_counts(rows_old, flags, key="D", detected=det))
        real, chance = report.chance_by_bin(moved, gts, th, n=20, seed=0)
        sens = {}
        for b in evaluate.BINS:
            sub = [r for r in sc["sim3"]["rows"] if r["bin"] == b]
            if not sub:
                continue
            formal = sum(r["D"] in ("correct", "misplaced") for r in sub) / len(sub)
            old_sub = [r for r in rows_old if r["bin"] == b]
            old = sum(r["D"] in ("correct", "misplaced") for r in old_sub) / len(old_sub)
            sens[b] = {"n": len(sub), "built_pre_g1": old, "built_formal": formal, "chance_formal": chance[b]}
            sens_md.append(f"| {arm} | {sid} | {b} | {len(sub)} | {old:.2f} | {formal:.2f} | {chance[b]:.2f} |")
        summary.setdefault(arm, {})[f"{sid}/{seed}/sensitivity"] = sens
        summary.setdefault(arm, {})[f"{sid}/{seed}"] = {"log": log, "summary_sim3": sc["sim3"]["summary"],
                                                       "summary_noscale": sc["noscale"]["summary"],
                                                       "alignment_s": sc["sim3"]["alignment"]["s"]}
    merged = {arm: report.merge_counts(c) for arm, c in funnels.items()}
    merged_abs = {arm: report.merge_counts(c) for arm, c in funnels_abs.items()}
    ref = {arm: {b: d["visible"] / max(1, d["n"]) for b, d in report.merge_counts(c).items()} for arm, c in ref_vis.items()}
    if merged_abs:
        report.plot_funnel(merged_abs, out / "funnel_pre_g1.png",
                           "对照：G1 之前的口径（不加 30 cm 门槛和 10 cm 下限，匈牙利配对）", ref_visible=ref)
    pooled = {}
    if pooled_rows:
        pooled = report.plot_recall(pooled_rows, out / "recall_by_bin.png",
                                    f"每档召回，{sum(len(v) for v in funnels.values())} 次运行按物体合并（感知为笔记本 10 万像素）")
    if merged:
        report.plot_funnel(merged, out / "funnel.png",
                           f"{split_name}场景 {len(scenes)} 个中跑了 {len({k.split('/')[0] for v in summary.values() for k in v})} 个、"
                           f"共 {sum(len(v) for v in funnels.values())} 次（判据 D，Sim(3) 对齐；感知为笔记本 10 万像素）",
                           ref_visible=ref)
    head = ("| 组 | 场景 | 种子 | 状态 | 分钟 | 输入 M | 缓存 M | 输出 k | 每周 +pt | 5h +pt | 预测物体 | 对齐残差 cm / 尺度 | "
            "召回 XS | S | M | L |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    (out / "runs.md").write_text(head + "\n" + "\n".join(rows_md) + "\n\n召回为判据 D、Sim(3) 对齐。⚠ = 对齐不可信"
                                 f"（残差 > {100 * th['align_residual_max_m']:.0f} cm 或尺度超出 {th['align_scale_range']}）。\n")
    (out / "sensitivity.md").write_text(
        "| 组 | 场景 | 档 | 真值数 | 建出来（G1 之前的口径） | 建出来（正式口径，含 30 cm 门槛） | 随机挪开的碰巧基线（正式口径） |\n|---|---|---|---|---|---|---|\n"
        + "\n".join(sens_md) + "\n")
    (out / "summary.json").write_text(json.dumps({"funnel_D": merged, "funnel_D_pre_g1": merged_abs, "recall_pooled": pooled, "runs": summary}, indent=1) + "\n")
    print((out / "runs.md").read_text())
    print((out / "sensitivity.md").read_text())
    print(json.dumps(merged, indent=1))


if __name__ == "__main__":
    main()
