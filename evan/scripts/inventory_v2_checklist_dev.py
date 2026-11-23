"""清单 v2 → 核对表（smallobj.checklist）在开发集上的阈值扫描（只用开发集，不碰测试集）。

网格：IoU 阈值 {0.15, 0.25, 0.4} × 中心距离比例 {0.35, 0.5} × 尺寸上限 {不设, 1.5 m, 0.5 m}，
另列清单 v2 原样和只做同类去重（不并组）两行做参照。网格里没有一格守得住 XS，所以又加了中心比例 0.2 的几行（EXTRA）。
输入是 perception/<id>/inventory_v2.json，不重建清单。
指标（判据 D、宽松门槛、Sim(3) 对齐，同 inventory_v2_dev.py）：
- 配上：只拿各组的代表去和真值一对一配对（就是 score.score_inventory 的配法），配上真值的代表占核对项的比例；
- 建对：同一次配对里，代表过了严格判据 D 的真值占比；
- 检测到：拿组去和真值一对一配对——组里任一成员过宽松门槛就算这组和这个真值能配，代价取成员里最小的
  （d̂ + |log 最长边之比|），配法同 thresholds.json 的 match_mode；配上的真值占比。一组最多算检测到一个真值。
  每组只有一个成员时（v2 原样、只同类去重）两种配对是同一回事。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/inventory_v2_checklist_dev.py
输出 results/inventory_v2_checklist_dev.md，并把选定配置（CHOSEN）的核对表写到 perception/<id>/inventory_v2_list.json。
"""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from smallobj import align, boxes, checklist, evaluate, inventory, score

PROJ = Path(__file__).resolve().parent.parent
IOUS, FRACS, SIDES = (0.15, 0.25, 0.4), (0.35, 0.5), (None, 1.5, 0.5)
EXTRA = [(0.15, 0.2, None), (0.25, 0.2, None), (0.4, 0.2, None), (0.4, 0.2, 1.5), (0.4, 0.2, 0.5)]  # 网格外加的
CHOSEN = dict(iou_min=0.4, center_frac=0.2, max_side=None)
IN_GRID = dict(iou_min=0.25, center_frac=0.35, max_side=None)  # 网格内 XS/S 掉得最少的一格，做对比
RAW, SAME = "清单 v2 原样", "只同类去重（IoU 0.25、中心 0.5，不并组）"
SAME_CHOSEN = "只同类去重（选定的阈值，不并组）"


def name_of(iou_min, center_frac, max_side):
    return f"IoU {iou_min}、中心 {center_frac}、" + ("不设上限" if max_side is None else f"< {max_side} m")


def pair_tables(moved, gts, th):
    """条目 × 真值：cost = d̂ + |log 最长边之比|（没过宽松门槛的是 inf），strict = 过了宽松门槛且过严格判据 D。"""
    cost = np.full((len(moved), len(gts)), np.inf)
    strict = np.zeros(cost.shape, bool)
    for i, p in enumerate(moved):
        for j, g in enumerate(gts):
            if evaluate._loose(p, g, th):
                cost[i, j] = evaluate.dhat(p, g) + evaluate._size_log_ratio(p, g)
                strict[i, j] = evaluate._strict_D(p, g, th)
    return cost, strict


def assign(cost, mode):
    """和 evaluate.match 同样的一对一配对，只是代价矩阵现成。返回 [(行, 真值)]。"""
    if cost.size == 0:
        return []
    ok = np.isfinite(cost)
    if mode == "greedy":
        pairs, used_r, used_g = [], set(), set()
        for i, j in sorted(zip(*np.nonzero(ok)), key=lambda ij: cost[ij]):
            if i not in used_r and j not in used_g:
                pairs.append((int(i), int(j)))
                used_r.add(i)
                used_g.add(j)
        return pairs
    rows, cols = linear_sum_assignment(np.where(ok, cost, 1e6))
    return [(int(i), int(j)) for i, j in zip(rows, cols) if ok[i, j]]


def tally(groups, cost, strict, bins, mode):
    """groups：[[代表的下标, 成员下标, …]]。matched = 配上真值的代表数；每档 n、detected（按组配）、correct（代表建对）。"""
    reps = [g[0] for g in groups]
    rep_pairs = assign(cost[reps], mode) if groups else []
    grp_pairs = assign(np.stack([cost[g].min(0) for g in groups]), mode) if groups else []
    t = {"items": len(groups), "matched": len(rep_pairs)}
    for b in evaluate.BINS:
        t[b] = {"n": bins.count(b), "detected": sum(bins[j] == b for _, j in grp_pairs),
                "correct": sum(bins[j] == b and bool(strict[reps[r], j]) for r, j in rep_pairs)}
    return t


def groups_of(entries, index):
    return [[index[m] for m in e["members"]] for e in entries]


def rates(ts):
    """各场景的 tally 合起来：{档: (检测到, 建对)}，占真值的比例。"""
    out = {}
    for b in evaluate.BINS:
        n = max(1, sum(t[b]["n"] for t in ts))
        out[b] = (sum(t[b]["detected"] for t in ts) / n, sum(t[b]["correct"] for t in ts) / n)
    return out


def cells(ts, digits=0):
    return [f"{d:.{digits}%} / {c:.{digits}%}" for d, c in rates(ts).values()]


def total(ts):
    return sum(t["items"] for t in ts)


def row(name, ts):
    per = [t["items"] for t in ts]
    return (f"| {name} | {sum(per)} | {min(per)} / {int(np.median(per))} / {max(per)} | "
            f"{sum(t['matched'] for t in ts) / max(1, sum(per)):.0%} | " + " | ".join(cells(ts)) + " |")


def main(write=True):
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    dev = json.loads((PROJ / "configs" / "splits.json").read_text())["dev"]
    mode = th.get("match_mode", "hungarian")
    grid = [dict(iou_min=i, center_frac=f, max_side=s) for s in SIDES for i in IOUS for f in FRACS]
    extra = [dict(iou_min=i, center_frac=f, max_side=s) for i, f, s in EXTRA]
    pooled, same_chosen, lists, raw_labels = {}, [], {}, {}
    for sid in dev:
        P = PROJ / "perception" / sid
        items = inventory.load(P / "inventory_v2.json")
        index = {it["item_id"]: k for k, it in enumerate(items)}
        gts = boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")
        tf = align.pipeline_to_gt(P / "bundle", PROJ / "scenes" / sid, with_scale=True)
        moved = [align.apply(it, tf["s"], tf["R"], tf["t"]) for it in items]
        bins = [evaluate.size_bin(g, th["bin_edges_m"]) for g in gts]
        cost, strict = pair_tables(moved, gts, th)
        raw = tally([[k] for k in range(len(items))], cost, strict, bins, mode)
        ref = score.score_inventory(items, gts, tf, th)  # 这里自己写的配对要和正式打分对得上
        assert raw["matched"] == len({r["pred_id"] for r in ref if r.get("pred_id")}), sid
        for b in evaluate.BINS:
            sub = [r for r in ref if r["bin"] == b]
            assert (raw[b]["detected"], raw[b]["correct"]) == (sum(r["D"] != "missed" for r in sub),
                                                               sum(r["D"] == "correct" for r in sub)), (sid, b)
        pooled.setdefault(RAW, []).append(raw)
        same = checklist.build(items, cross_label=False)
        pooled.setdefault(SAME, []).append(tally(groups_of(same, index), cost, strict, bins, mode))
        for kw in grid + extra:
            entries = checklist.build(items, **kw)
            pooled.setdefault(name_of(**kw), []).append(tally(groups_of(entries, index), cost, strict, bins, mode))
            if kw == CHOSEN:
                lists[sid] = entries
        same = checklist.build(items, cross_label=False, **CHOSEN)
        same_chosen.append(tally(groups_of(same, index), cost, strict, bins, mode))
        raw_labels[sid] = {}
        for it in items:
            raw_labels[sid][it["category"]] = raw_labels[sid].get(it["category"], 0) + 1
        print(sid, "done", flush=True)

    chosen, in_grid = name_of(**CHOSEN), name_of(**IN_GRID)
    extra_names = {name_of(**kw) for kw in extra}
    lines = [f"# 清单 v2 整理成核对表：开发集上的阈值扫描（{len(dev)} 个场景：{' '.join(dev)}）", "",
             "核对表（`smallobj.checklist.build`）只按几何整理清单 v2，不看真值、不用 VLM：同类别的重复去掉，"
             "不同类别叠在一起的并成一组（代表 = 分数最高的，其余类别列为备选），落在更大的框里面的不去掉；"
             "可选的尺寸上限只留最长边小于它的条目。\"重叠\" = 3D IoU > 阈值，或大小相当（最长边之比 ≤ 3）且中心距离 "
             "< 比例 × 两个框里较短的对角线。", "",
             "判据 D、宽松门槛、Sim(3) 对齐，同 `inventory_v2_dev.md`。每格是\"检测到 / 建对\"占真值的比例：", "",
             "- **配上**：只拿各组的代表和真值一对一配对（`score_inventory` 的配法），配上真值的代表占核对项的比例。",
             "- **建对**：同一次配对里，代表过了严格判据 D 的真值占比。",
             "- **检测到**：拿组和真值一对一配对，组里任一成员过宽松门槛就算这组能配这个真值，代价取成员里最小的；"
             "配上的真值占比。一组最多算一个真值；每组只有一个成员时（前两行）和代表配对是同一回事。", "",
             "\"每间房\"是 5 间房核对项数的 最少 / 中位 / 最多。标\"网格外\"的几行是原定网格之外加的（中心比例 0.2）。", "",
             "| 配置 | 核对项 | 每间房 | 配上 | XS | S | M | L |", "|---|---|---|---|---|---|---|---|"]
    for name, ts in pooled.items():
        shown = name + ("（网格外）" if name in extra_names else "")
        lines.append(row(f"**{shown}（选定）**" if name == chosen else shown, ts))
    n_gt = {b: sum(t[b]["n"] for t in pooled[RAW]) for b in evaluate.BINS}
    lines += ["", "真值数：" + "、".join(f"{b} {n}" for b, n in n_gt.items()), ""]

    raw_ts, ch_ts, ig_ts = pooled[RAW], pooled[chosen], pooled[in_grid]
    r0, r1, r2 = rates(raw_ts), rates(ch_ts), rates(ig_ts)
    grid_names = [name_of(**kw) for kw in grid]
    best_xs = max(rates(pooled[n])["XS"][0] for n in grid_names)
    cap15, cap05 = pooled[name_of(**{**CHOSEN, "max_side": 1.5})], pooled[name_of(**{**CHOSEN, "max_side": 0.5})]

    def pair(r, b):
        return f"{r[b][0]:.0%} / {r[b][1]:.0%}"
    lines += [f"## 选定：{chosen}", "",
              f"原定网格里没有一格能把 XS、S 的\"检测到 / 建对\"都守在 v2 原样的 2 个点上下：XS 检测到最好的一格也掉 "
              f"{100 * (r0['XS'][0] - best_xs):.1f} 个点；IoU 阈值在中心比例 0.35、0.5 下几乎不起作用（条目数只差几条到几十条），"
              f"起作用的是中心距离那一条。所以在网格外加了中心比例 0.2，选 **{chosen}**：核对项 {total(raw_ts)} → {total(ch_ts)}"
              f"（少 {1 - total(ch_ts) / total(raw_ts):.0%}），XS {pair(r0, 'XS')} → {pair(r1, 'XS')}，"
              f"S {pair(r0, 'S')} → {pair(r1, 'S')}，四个数都在 2 个点上下（S 建对差 "
              f"{100 * (r0['S'][1] - r1['S'][1]):.1f} 个点，最多）。"
              f"M、L 的代价：M {pair(r0, 'M')} → {pair(r1, 'M')}，L {pair(r0, 'L')} → {pair(r1, 'L')}。"
              f"尺寸上限不设：1.5 m 只再少 {total(ch_ts) - total(cap15)} 条，L 建对却掉到 {rates(cap15)['L'][1]:.0%}；"
              f"0.5 m 再少 {1 - total(cap05) / total(ch_ts):.0%}，但 S 检测到再掉 "
              f"{100 * (r1['S'][0] - rates(cap05)['S'][0]):.1f} 个点，M 只剩 {pair(rates(cap05), 'M')}、L 全没了，"
              f"大家具要留给 agent 的话，写提示词时按 size 筛就行，不必在核对表里丢掉。"
              f"更看重条目数的话，网格内可以退到 {in_grid}：{total(ig_ts)} 条（少 {1 - total(ig_ts) / total(raw_ts):.0%}），"
              f"XS {pair(r2, 'XS')}、S {pair(r2, 'S')}。", "",
              "| | 核对项 | 配上 | XS | S | M | L |", "|---|---|---|---|---|---|---|"]
    for name, ts in ((RAW, raw_ts), (SAME_CHOSEN, same_chosen), (f"**{chosen}（选定）**", ch_ts), (in_grid, ig_ts)):
        lines.append(f"| {name} | {total(ts)} | {sum(t['matched'] for t in ts) / total(ts):.0%} | "
                     + " | ".join(cells(ts, 1)) + " |")
    lines += ["", "\"只同类去重\"那一行和选定配置的差距就是并组的代价：两个挨着的真物体并成一组只能算检测到一个，"
              "代表（分数最高的）的框也不一定是组里最准的。", "",
              "## 选定配置的各场景", "",
              "| 场景 | v2 条目 | 核对项 | 多成员的组 | 核对项里最多的三个类别（v2 里的条数） | XS | S | M | L |",
              "|---|---|---|---|---|---|---|---|---|"]
    for sid, t in zip(dev, ch_ts):
        top = {}
        for e in lists[sid]:
            top[e["label"]] = top.get(e["label"], 0) + 1
        top = sorted(top.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        lines.append(f"| {sid} | {sum(raw_labels[sid].values())} | {len(lists[sid])} | {sum(e['n_members'] > 1 for e in lists[sid])} | "
                     + "、".join(f"{k} {v}（{raw_labels[sid][k]}）" for k, v in top) + " | "
                     + " | ".join(f"{t[b]['detected']}/{t[b]['correct']}/{t[b]['n']}" for b in evaluate.BINS) + " |")
    lines += ["", "各场景的格子是 检测到/建对/真值数。", "",
              "选定配置的核对表在 `perception/<id>/inventory_v2_list.json`，按代表的 score 从高到低（同分按 item_id）。"
              "每项的键：`item_id`（代表条目的 item_id，和 `inventory_v2.json`、`item_masks_inventory_v2/` 对得上）、`label`、`alt_labels`、"
              "`n_members`、`members`（成员的 item_id，代表在最前），后面是代表条目原样的键（`object_id`、`category`、`center`、"
              "`yaw`、`size`、`confidence`、`source`、`score`、`best_frame`、`bbox2d_xyxy`、`n_frames`、`det_sources`、`n_views`、"
              "`settled_on`，有的还有 `same_size_group`）。`settled_on` 指的支撑物可能已经在同类去重时去掉了，按 `inventory_v2.json` 查。"]
    text = "\n".join(lines) + "\n"
    if write:
        (PROJ / "results" / "inventory_v2_checklist_dev.md").write_text(text)
        for sid, entries in lists.items():
            inventory.save(entries, PROJ / "perception" / sid / "inventory_v2_list.json")
    print(text)
    return pooled


if __name__ == "__main__":
    main()
