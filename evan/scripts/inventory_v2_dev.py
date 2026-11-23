"""清单 v2 在开发集上的消融（docs/plans/2026-10-29-scenerig-detection.md；只用开发集，不碰测试集）。

每个版本在上一个的基础上加一项：
  整帧 + 固定表 → + 放大窗口 → + 开放词表 → + MoGe 深度 → + 同尺寸、贴支撑面（= v2）。
另列旧的干净对照（inventory_clean.json）和 Boxer 做参照。"整帧 + 固定表"和旧干净对照用同样的 SAM 3 提示，应该差不多。
指标（判据 D、宽松门槛、Sim(3) 对齐，同 inventory_dev.py）：每档"检测到"（没漏掉）和"建对"（清单框本身就摆对）；
另报条目数和配上真值的条目比例，免得靠多报框把检测率堆上去。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/inventory_v2_dev.py   输出 results/inventory_v2_dev.md，
并把完整的 v2 写到 perception/<id>/inventory_v2.json。
"""
import json
from pathlib import Path

from smallobj import align, boxes, clean_inventory, evaluate, inventory, score

PROJ = Path(__file__).resolve().parent.parent
VARIANTS = [("整帧 + 固定表", dict(tiles=False, open_vocab=False, depth_name="depth", post=False)),
            ("+ 放大窗口", dict(tiles=True, open_vocab=False, depth_name="depth", post=False)),
            ("+ 开放词表", dict(tiles=True, open_vocab=True, depth_name="depth", post=False)),
            ("+ MoGe 深度", dict(tiles=True, open_vocab=True, depth_name="depth_moge", post=False)),
            ("+ 同尺寸、贴支撑面（v2）", dict(tiles=True, open_vocab=True, depth_name="depth_moge", post=True))]


def tally(rows, items):
    t = {"items": len(items), "matched": len({r["pred_id"] for r in rows if r["D"] != "missed" and r.get("pred_id")})}
    for b in evaluate.BINS:
        sub = [r for r in rows if r["bin"] == b]
        t[b] = {"n": len(sub), "detected": sum(r["D"] != "missed" for r in sub), "correct": sum(r["D"] == "correct" for r in sub)}
    return t


def main():
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    dev = json.loads((PROJ / "configs" / "splits.json").read_text())["dev"]
    pooled, per_scene, done = {}, [], []
    for sid in dev:
        P = PROJ / "perception" / sid
        if not (P / "sam3_objects_v2" / "index.json").exists() or not (P / "hd" / "depth_moge" / "align.json").exists():
            print(sid, "还没有 v2 掩码或 MoGe 深度，跳过")
            continue
        done.append(sid)
        gts = boxes.load(PROJ / "scenes" / sid / "gt" / "boxes.json")
        tf = align.pipeline_to_gt(P / "bundle", PROJ / "scenes" / sid, with_scale=True)
        versions = [("Boxer（参照）", inventory.load(P / "inventory.json")),
                    ("旧干净对照", inventory.load(P / "inventory_clean.json"))]
        versions += [(name, clean_inventory.build_v2(sid, root=PROJ, **kw)) for name, kw in VARIANTS]
        inventory.save(versions[-1][1], P / "inventory_v2.json")
        for name, items in versions:
            t = tally(score.score_inventory(items, gts, tf, th), items)
            pooled.setdefault(name, []).append(t)
            per_scene.append((sid, name, t))
    lines = [f"# 清单 v2 在开发集上的消融（{len(done)} 个场景：{' '.join(done)}）", "",
             "判据 D、宽松门槛、Sim(3) 对齐。每格是\"检测到 / 建对\"占真值的比例；每一行在上一行的基础上加一项。"
             "\"配上\"是配上真值的条目占清单条目的比例。", "",
             "| 版本 | 条目数 | 配上 | XS | S | M | L |", "|---|---|---|---|---|---|---|"]
    for name, ts in pooled.items():
        n_items, n_match = sum(t["items"] for t in ts), sum(t["matched"] for t in ts)
        cells = []
        for b in evaluate.BINS:
            n = sum(t[b]["n"] for t in ts)
            cells.append(f"{sum(t[b]['detected'] for t in ts) / max(1, n):.0%} / {sum(t[b]['correct'] for t in ts) / max(1, n):.0%}")
        lines.append(f"| {name} | {n_items} | {n_match / max(1, n_items):.0%} | " + " | ".join(cells) + " |")
    n_gt = {b: sum(t[b]["n"] for t in pooled[next(iter(pooled))]) for b in evaluate.BINS} if pooled else {}
    lines += ["", "真值数：" + "、".join(f"{b} {n}" for b, n in n_gt.items()), "", "## 各场景", "",
              "| 场景 | 版本 | 条目数 | XS | S | M | L |", "|---|---|---|---|---|---|---|"]
    for sid, name, t in per_scene:
        lines.append(f"| {sid} | {name} | {t['items']} | " + " | ".join(
            f"{t[b]['detected']}/{t[b]['correct']}/{t[b]['n']}" for b in evaluate.BINS) + " |")
    lines += ["", "各场景的格子是 检测到/建对/真值数。"]
    out = PROJ / "results" / "inventory_v2_dev.md"
    out.write_text("\n".join(lines) + "\n")
    print(out.read_text())


if __name__ == "__main__":
    main()
