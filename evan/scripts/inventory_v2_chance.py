"""清单 v2 的碰巧基线（只用开发集）：v2 的框是旧干净对照的 3 倍，看提升是不是靠多报框碰上的。

每个框沿水平方向随机挪开 0.5–1.5 米（方向随机，尺寸朝向不变，同 report.chance_by_bin），挪 20 次取平均，
算每档"检测到"和"建对"的比例。真实比例远高于碰巧比例，才算检测本身的提升。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/inventory_v2_chance.py   输出 results/inventory_v2_chance.md
"""
import json
from pathlib import Path

import numpy as np

from smallobj import align, boxes, clean_inventory, evaluate, inventory

PROJ = Path(__file__).resolve().parent.parent
VERSIONS = [("旧干净对照", lambda sid, P: inventory.load(P / "inventory_clean.json")),
            ("v2 不加后处理", lambda sid, P: clean_inventory.build_v2(sid, root=PROJ, depth_name="depth_moge", post=False))]


def counts(preds, gts, th):
    rows = evaluate.outcomes(preds, gts, th)
    return {b: (sum(r["D"] != "missed" for r in rows if r["bin"] == b), sum(r["D"] == "correct" for r in rows if r["bin"] == b),
                sum(r["bin"] == b for r in rows)) for b in evaluate.BINS}


def main(n=20, seed=0, shift=(0.5, 1.5)):
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    dev = json.loads((PROJ / "configs" / "splits.json").read_text())["dev"]
    acc = {name: {b: np.zeros(5) for b in evaluate.BINS} for name, _ in VERSIONS}  # 检测到、建对、真值数、碰巧检测到、碰巧建对
    for sid in dev:
        P = PROJ / "perception" / sid
        gts = boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")
        tf = align.pipeline_to_gt(P / "bundle", PROJ / "scenes" / sid, with_scale=True)
        for name, load in VERSIONS:
            preds = [align.apply(it, tf["s"], tf["R"], tf["t"]) for it in load(sid, P)]
            rng = np.random.default_rng(seed)
            for b, (det, cor, tot) in counts(preds, gts, th).items():
                acc[name][b][:3] += (det, cor, tot)
            for _ in range(n):
                moved = [dict(p, center=(np.asarray(p["center"], float) + [r * np.cos(a), r * np.sin(a), 0.0]).tolist())
                         for p in preds for a, r in [(rng.uniform(0, 2 * np.pi), rng.uniform(*shift))]]
                for b, (det, cor, _) in counts(moved, gts, th).items():
                    acc[name][b][3:] += (det / n, cor / n)
        print(sid, "done", flush=True)
    lines = [f"# 清单 v2 的碰巧基线（开发集 {len(dev)} 个场景：{' '.join(dev)}）", "",
             f"判据 D、宽松门槛、Sim(3) 对齐。每个框水平随机挪开 {shift[0]}–{shift[1]} 米、挪 {n} 次取平均（seed {seed}）。"
             "每格是 真实 / 碰巧，占真值的比例。", "",
             "| 版本 | 指标 | " + " | ".join(evaluate.BINS) + " |", "|---|---|" + "---|" * len(evaluate.BINS)]
    for name, _ in VERSIONS:
        for k, label in ((0, "检测到"), (1, "建对")):
            lines.append(f"| {name} | {label} | " + " | ".join(
                f"{a[k] / a[2]:.0%} / {a[k + 3] / a[2]:.0%}" for a in (acc[name][b] for b in evaluate.BINS)) + " |")
    out = PROJ / "results" / "inventory_v2_chance.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
