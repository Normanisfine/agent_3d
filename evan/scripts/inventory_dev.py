"""开发集上两种清单的合理性检查（设计 §9.4 允许；不拿它调任何阈值）：每档"检测到"的比例。

用法：PYTHONPATH=src .runtime/venv/bin/python scripts/inventory_dev.py   输出 results/inventory_dev.md
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_checkpoint import vis_flags  # noqa: E402

from smallobj import align, boxes, evaluate, report, score  # noqa: E402

PROJ = Path(__file__).resolve().parent.parent


def main():
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    dev = json.loads((PROJ / "configs" / "splits.json").read_text())["dev"]
    lines = ["| 场景 | 清单 | 条目数 | 配上真值的条目 | XS 检测到 | S | M | L |", "|---|---|---|---|---|---|---|---|"]
    pooled, pooled30 = {}, {}
    th30 = {k: v for k, v in th.items() if k not in ("loose_abs_m", "strict_floor_m", "match_mode")}  # 对照：G1 之前的口径
    for sid in dev:
        gts = boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")
        tf = align.pipeline_to_gt(PROJ / "perception" / sid / "bundle", PROJ / "scenes" / sid, with_scale=True)
        flags = vis_flags(sid, th, hd=True)
        for name, fname in (("Boxer", "inventory.json"), ("干净对照", "inventory_clean.json")):
            path = PROJ / "perception" / sid / fname
            if not path.exists():
                continue
            items = json.loads(path.read_text())
            rows = score.score_inventory(items, gts, tf, th)
            det = {r["gt_id"]: r["D"] != "missed" for r in rows}
            f = report.funnel_counts(rows, flags, key="D", detected=det)
            pooled.setdefault(name, []).append(f)
            rows30 = score.score_inventory(items, gts, tf, th30)
            pooled30.setdefault(name, []).append(report.funnel_counts(
                rows30, flags, key="D", detected={r["gt_id"]: r["D"] != "missed" for r in rows30}))
            n_hit = sum(1 for r in rows if r["D"] != "missed")
            cells = [f"{f[b]['detected']}/{f[b]['n']}" if b in f else "-" for b in evaluate.BINS]
            lines.append(f"| {sid} | {name} | {len(items)} | {n_hit} | " + " | ".join(cells) + " |")
    lines += ["", "| 合计 | 清单 | 看得见（高清） XS | 检测到 XS | 看得见 S | 检测到 S | 看得见 M | 检测到 M | 看得见 L | 检测到 L |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for name, fs in pooled.items():
        m = report.merge_counts(fs)
        cells = []
        for b in evaluate.BINS:
            d = m.get(b, {"n": 0, "visible": 0, "detected": 0})
            cells += [f"{d['visible'] / max(1, d['n']):.0%}", f"{d['detected'] / max(1, d['n']):.0%}"]
        lines.append(f"| {len(fs)} 个场景 | {name} | " + " | ".join(cells) + " |")
    lines += ["", "同样的合计，但按 G1 之前的口径（不加 30 cm 门槛）：", "",
              "| 清单 | XS | S | M | L |", "|---|---|---|---|---|"]
    for name, fs in pooled30.items():
        m = report.merge_counts(fs)
        lines.append(f"| {name} | " + " | ".join(f"{m[b]['detected'] / max(1, m[b]['n']):.0%}" if b in m else "-"
                                                 for b in evaluate.BINS) + " |")
    out = PROJ / "results" / "inventory_dev.md"
    out.write_text("# 开发集上两种清单的\"检测到\"（判据 D 的宽松门槛，Sim(3) 对齐）\n\n"
                   "只做合理性检查，不拿来调阈值。正式口径（10-27 G1 冻结）已含 30 cm 门槛。Boxer 训练时用过 CA-1M 训练集（同源），干净对照没有。\n\n"
                   + "\n".join(lines) + "\n")
    print(out.read_text())


if __name__ == "__main__":
    main()
