"""中期检查和报告用的汇总：漏斗各关的计数、跨场景合并、出图。"""
from smallobj.evaluate import BINS


# 用清单的实验组和它们的清单文件（perception/<id>/ 下）；没列出的组（A0、A1）没有"检测到"这一关
ARM_INVENTORY = {"P0": "inventory.json", "P0c": "inventory_clean.json", "A2": "inventory.json",
                 "A3r": "inventory.json", "A3v": "inventory.json", "A4": "inventory.json"}


def funnel_counts(rows, visible, key="D", detected=None):
    """每档：真值个数 n、看得见、[检测到]、建出来（宽松门槛内 = correct 或 misplaced）、建对了。

    "建出来"不要求"看得见"：agent 可能从别的帧或常识补出流程帧里看不清的物体。
    detected 是 gt_id → bool（清单在宽松门槛内配上了它）；为 None 时不出这一项。
    """
    out = {}
    for r in rows:
        d = out.setdefault(r["bin"], {"n": 0, "visible": 0, "built": 0, "correct": 0} if detected is None
                           else {"n": 0, "visible": 0, "detected": 0, "built": 0, "correct": 0})
        d["n"] += 1
        d["visible"] += bool(visible.get(r["gt_id"], {}).get("visible"))
        if detected is not None:
            d["detected"] += bool(detected.get(r["gt_id"]))
        d["built"] += r[key] in ("correct", "misplaced")
        d["correct"] += r[key] == "correct"
    return out


def missed_rows(gts, th):
    """没得到 .blend（或导出失败）的运行：每个真值都记 missed，照常进漏斗和召回（设计 §5 不剔除失败）。"""
    from smallobj import evaluate
    return [{"gt_id": g["object_id"], "category": g["category"], "bin": evaluate.size_bin(g, th["bin_edges_m"]),
             "I": "missed", "D": "missed", "dhat": None, "iou": None} for g in gts]


def built_by_bin(preds, gts, th, key="D"):
    """每档"建出来"的比例。和正式口径一样，全体真值一起配对后再按档切（预测会跨档竞争）。"""
    from smallobj import evaluate
    rows = evaluate.outcomes(preds, gts, th)
    out = {}
    for b in BINS:
        sub = [r for r in rows if r["bin"] == b]
        if sub:
            out[b] = sum(r[key] in ("correct", "misplaced") for r in sub) / len(sub)
    return out


def built_fraction(preds, gts, th, key="D", bin=None):
    """bin=None 时是全部真值的比例，否则是该档的比例（仍是全体真值一起配对）。"""
    from smallobj import evaluate
    rows = evaluate.outcomes(preds, gts, th)
    if bin is not None:
        rows = [r for r in rows if r["bin"] == bin]
    return sum(r[key] in ("correct", "misplaced") for r in rows) / max(1, len(rows))


def chance_by_bin(preds, gts, th, n=20, seed=0, key="D", shift=(0.5, 1.5)):
    """碰巧配上的基线：把每个预测物体沿水平方向随机挪开 shift 米（方向随机，尺寸朝向不变），
    算每档"建出来"的比例。房间里小物体越密，挪开后越容易碰上别的真值，这个基线就越高。

    返回 (每档真实比例, 每档随机挪开 n 次的平均比例)。
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    real = built_by_bin(preds, gts, th, key)
    draws = []
    for _ in range(n):
        moved = []
        for p in preds:
            ang = rng.uniform(0, 2 * np.pi)
            r = rng.uniform(*shift)
            c = np.asarray(p["center"], float) + [r * np.cos(ang), r * np.sin(ang), 0.0]
            moved.append(dict(p, center=c.tolist()))
        draws.append(built_by_bin(moved, gts, th, key))
    chance = {b: float(np.mean([d.get(b, 0.0) for d in draws])) if draws else 0.0 for b in real}
    return real, chance


def chance_built(preds, gts, th, n=20, seed=0, key="D", shift=(0.5, 1.5), bin=None):
    """chance_by_bin 的单档（bin=None 时为全部真值）版本，返回 (真实比例, 基线比例)。"""
    import numpy as np
    if bin is not None:
        real, chance = chance_by_bin(preds, gts, th, n, seed, key, shift)
        return real.get(bin, 0.0), chance.get(bin, 0.0)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        moved = [dict(p, center=(np.asarray(p["center"], float) + [r * np.cos(a), r * np.sin(a), 0.0]).tolist())
                 for p in preds for a, r in [(rng.uniform(0, 2 * np.pi), rng.uniform(*shift))]]
        vals.append(built_fraction(moved, gts, th, key))
    return built_fraction(preds, gts, th, key), float(np.mean(vals)) if vals else 0.0


def merge_counts(per_scene):
    out = {}
    for c in per_scene:
        for b, d in c.items():
            m = out.setdefault(b, {})
            for k, v in d.items():
                m[k] = m.get(k, 0) + v
    return out


def plot_funnel(counts_by_arm, out_png, title, ref_visible=None):
    """每个实验组、每档一组柱：看得见 / [检测到] / 建出来 / 建对了占真值的比例。

    有清单的组多一根"检测到"。ref_visible = {arm: {bin: 比例}} 时，在"看得见"那根柱上画一条黑线，
    表示流程分辨率下看得见的比例（设计 §9.5：两者之差是高清帧带来的空间）。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "Noto Sans CJK TC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    import numpy as np

    arms = list(counts_by_arm)
    bins = [b for b in BINS if any(b in counts_by_arm[a] for a in arms)]
    all_stages = ("visible", "detected", "built", "correct")
    labels = {"visible": "看得见 visible", "detected": "检测到 detected", "built": "建出来 built", "correct": "建对了 correct"}
    colors = {"visible": "C0", "detected": "C3", "built": "C1", "correct": "C2"}
    fig, axes = plt.subplots(1, len(arms), figsize=(4.2 * len(arms), 3.6), sharey=True, squeeze=False)
    legend = {}
    for ax, arm in zip(axes[0], arms):
        x = np.arange(len(bins))
        stages = [st for st in all_stages if any(st in counts_by_arm[arm].get(b, {}) for b in bins)]
        width = 0.8 / len(stages)
        for k, st in enumerate(stages):
            vals = [counts_by_arm[arm].get(b, {}).get(st, 0) / max(1, counts_by_arm[arm].get(b, {}).get("n", 0)) for b in bins]
            off = (k - (len(stages) - 1) / 2) * width
            legend[st] = ax.bar(x + off, vals, width=width * 0.95, color=colors[st], label=labels[st])
            if st == "visible" and ref_visible and arm in ref_visible:
                ref = [ref_visible[arm].get(b, np.nan) for b in bins]
                h = ax.hlines(ref, x + off - width / 2, x + off + width / 2, colors="k", linewidth=1.5)
                legend["ref"] = h
        ax.set_xticks(x, [f"{b}\n(n={counts_by_arm[arm].get(b, {}).get('n', 0)})" for b in bins])
        ax.set_title(arm); ax.set_ylim(0, 1.05); ax.grid(axis="y", alpha=0.3)
    axes[0][0].set_ylabel("占真值物体的比例")
    names = {**labels, "ref": "流程分辨率下看得见"}
    keys = [k for k in (*all_stages, "ref") if k in legend]
    fig.legend([legend[k] for k in keys], [names[k] for k in keys], loc="lower center", ncol=len(keys), fontsize=8, frameon=False)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def plot_recall(rows_by_arm, out_png, title):
    """每档召回（建对了的比例），跨场景按物体合并；判据 I、D × Sim(3) 对齐、不修尺度对齐四根柱。

    rows_by_arm: {arm: {"sim3": rows, "noscale": rows}}，rows 是 evaluate.outcomes 的输出拼起来。
    返回 {arm: {"sim3": summarize(...), "noscale": summarize(...)}}。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "Noto Sans CJK TC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    import numpy as np
    from smallobj.evaluate import summarize

    pooled = {arm: {k: summarize(v) for k, v in d.items()} for arm, d in rows_by_arm.items()}
    arms = list(pooled)
    series = [("sim3", "I", "判据 I（IoU≥0.25），Sim(3)"), ("sim3", "D", "判据 D（距离+尺寸），Sim(3)"),
              ("noscale", "I", "判据 I，不修尺度"), ("noscale", "D", "判据 D，不修尺度")]
    fig, axes = plt.subplots(1, len(arms), figsize=(4.6 * len(arms), 3.6), sharey=True, squeeze=False)
    for ax, arm in zip(axes[0], arms):
        bins = [b for b in BINS if b in pooled[arm].get("sim3", {})]
        x = np.arange(len(bins))
        for k, (al, crit, lab) in enumerate(series):
            vals = [pooled[arm].get(al, {}).get(b, {}).get(f"recall_{crit}", 0.0) for b in bins]
            ax.bar(x + (k - 1.5) * 0.2, vals, width=0.19, label=lab, hatch="//" if al == "noscale" else None)
        ax.set_xticks(x, [f"{b}\n(n={pooled[arm]['sim3'][b]['n']})" for b in bins])
        ax.set_title(arm); ax.set_ylim(0, 1.05); ax.grid(axis="y", alpha=0.3)
    axes[0][0].set_ylabel("召回（建对了的比例）")
    handles, labs = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labs, loc="lower center", ncol=2, fontsize=8, frameon=False)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return pooled
