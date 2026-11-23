"""6 个测试房间的主表：各组每档建对 / 摆错 / 没建的个数，多建的物体数，以及按房间配对的比较。

只读各次运行已有的 score_sim3.json 和 run_log.json（判据 D、相机拟合尺度），不重新打分、不读真值。
缺运行的房间不进该组的合计，表里写明每组用了几个房间；配对比较只用两组都有的房间。
主表和配对比较只用种子 0；A5 的第二遍（种子 1）单列一节，看同一设置重跑一遍差多少。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/report_rooms.py [--out results/test_opus_6rooms]
"""
import argparse
import itertools
import json
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
ROOMS = ["42897538", "42898849", "42899617", "42899712", "42899729", "44358442"]
ARMS = [("A0-claude", "基线 AHa-3D（A0）"), ("A1-claude", "All objects（A1）"), ("A2-claude", "Inventory，Boxer 清单（A2）"),
        ("A5-claude", "逐项清单，清单 v2（A5）"), ("A1-claude-betty", "All objects + Betty 感知")]
BINS = ["XS", "S", "M", "L"]
PAIRS = [("A1-claude", "A0-claude"), ("A2-claude", "A1-claude"), ("A5-claude", "A1-claude"), ("A5-claude", "A2-claude"),
         ("A1-claude-betty", "A1-claude")]
SECOND = "A5-claude"  # 跑了第二遍（种子 1）的组


def load(arm, room, seed="0"):
    run = PROJ / "runs" / arm / room / seed
    if not (run / "score_sim3.json").exists():
        return None
    s, log = json.loads((run / "score_sim3.json").read_text()), json.loads((run / "run_log.json").read_text())
    out = {"n_pred": s["n_pred"], "minutes": log["wall_s"] / 60, "usd": log["usage"]["cost_usd_equiv"],
           "accepted": bool(log.get("aha_accepted")), "matched": sum(r["D"] != "missed" for r in s["rows"])}
    for b in BINS:
        rows = [r for r in s["rows"] if r["bin"] == b]
        out[b] = {k: sum(r["D"] == k for r in rows) for k in ("correct", "misplaced", "missed")} | {"n": len(rows)}
    return out


def sign_flip_p(diffs):
    """按房间配对的符号翻转检验（双侧，精确）：差值的符号全部枚举，统计量是差值之和的绝对值。"""
    obs = abs(sum(diffs))
    hits = sum(abs(sum(d * s for d, s in zip(diffs, signs))) >= obs - 1e-12
               for signs in itertools.product((1, -1), repeat=len(diffs)))
    return hits / 2 ** len(diffs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/test_opus_6rooms")
    out = PROJ / ap.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    data = {arm: {room: load(arm, room) for room in ROOMS} for arm, _ in ARMS}
    lines = ["# 6 个测试房间的主表（Opus 5.5，判据 D，相机拟合尺度）", "",
             "每格是 建对 / 摆错 / 没建。只合计该组已有运行的房间。", "",
             "| 组 | 房间数 | XS | S | M | L | 重建物体 | 配上目标 | 平均分钟 | 平均美元 | AHa 验收通过 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    summary = {"rooms": ROOMS, "arms": {}}
    for arm, name in ARMS:
        runs = [r for r in data[arm].values() if r]
        if not runs:
            continue
        cells = []
        for b in BINS:
            tot = {k: sum(r[b][k] for r in runs) for k in ("correct", "misplaced", "missed", "n")}
            cells.append(f"{tot['correct']} / {tot['misplaced']} / {tot['missed']}（共 {tot['n']}）")
        lines.append(f"| {name} | {len(runs)} | " + " | ".join(cells) + f" | {sum(r['n_pred'] for r in runs)} | {sum(r['matched'] for r in runs)} | "
                     f"{sum(r['minutes'] for r in runs) / len(runs):.0f} | {sum(r['usd'] for r in runs) / len(runs):.1f} | {sum(r['accepted'] for r in runs)} |")
        summary["arms"][arm] = {room: data[arm][room] for room in ROOMS}
    lines += ["", "## 各房间 50 cm 以下（XS + S）建对的个数", "", "| 组 | " + " | ".join(ROOMS) + " |", "|---|" + "---|" * len(ROOMS)]
    for arm, name in ARMS:
        if any(data[arm].values()):
            lines.append(f"| {name} | " + " | ".join(
                (f"{r['XS']['correct'] + r['S']['correct']} / {r['XS']['n'] + r['S']['n']}" if r else "—") for r in data[arm].values()) + " |")
    lines += ["", "## 按房间配对的比较（XS + S 建对数之差）", "",
              "符号翻转检验是双侧、精确的；n 个房间时最小的 p 值是 2 / 2^n（3 个房间 0.25，6 个房间 0.031）。", "",
              "| 比较 | 共同房间 | 各房间的差 | 差的合计 | p |", "|---|---|---|---|---|"]
    summary["paired"] = {}
    for a, b in PAIRS:
        rooms = [r for r in ROOMS if data[a][r] and data[b][r]]
        if not rooms:
            continue
        diffs = [sum(data[a][r][k]["correct"] for k in ("XS", "S")) - sum(data[b][r][k]["correct"] for k in ("XS", "S")) for r in rooms]
        p = sign_flip_p(diffs)
        lines.append(f"| {dict(ARMS)[a]} − {dict(ARMS)[b]} | {len(rooms)} | {', '.join(f'{d:+d}' for d in diffs)} | {sum(diffs):+d} | {p:.3f} |")
        summary["paired"][f"{a} - {b}"] = {"rooms": rooms, "diffs": diffs, "p_sign_flip": p}
    second = {room: load(SECOND, room, "1") for room in ROOMS}
    if any(second.values()):
        small = lambda r: r["XS"]["correct"] + r["S"]["correct"]
        both = [r for r in ROOMS if data[SECOND][r] and second[r]]
        lines += ["", f"## {dict(ARMS)[SECOND]} 跑两遍", "",
                  "同样的提示词、清单和设置各跑一遍（种子 0、种子 1）。每格是 XS + S 建对的个数。", "",
                  "| 遍 | " + " | ".join(both) + " | 合计 | 重建物体 | 配上目标 | 平均分钟 | 平均美元 |", "|---|" + "---|" * (len(both) + 5)]
        for label, runs in (("种子 0", [data[SECOND][r] for r in both]), ("种子 1", [second[r] for r in both])):
            lines.append(f"| {label} | " + " | ".join(str(small(r)) for r in runs) + f" | {sum(small(r) for r in runs)} | {sum(r['n_pred'] for r in runs)} | "
                         f"{sum(r['matched'] for r in runs)} | {sum(r['minutes'] for r in runs) / len(runs):.0f} | {sum(r['usd'] for r in runs) / len(runs):.1f} |")
        gap = [small(second[r]) - small(data[SECOND][r]) for r in both]
        lines.append("| 种子 1 − 种子 0 | " + " | ".join(f"{d:+d}" for d in gap) + f" | {sum(gap):+d} | | | | |")
        lines += ["", "种子 1 每档的 建对 / 摆错 / 没建：" + "；".join(
            f"{b} {sum(second[r][b]['correct'] for r in both)} / {sum(second[r][b]['misplaced'] for r in both)} / {sum(second[r][b]['missed'] for r in both)}" for b in BINS) + "。", "",
            "用种子 1 或两遍的平均去和别的组（种子 0）配对：", "", "| 比较 | 各房间的差 | 差的合计 | p |", "|---|---|---|---|"]
        summary["second_seed"] = {"arm": SECOND, "runs": {r: second[r] for r in ROOMS}, "seed1_minus_seed0": dict(zip(both, gap)), "paired": {}}
        for other in ("A1-claude", "A2-claude"):
            rooms = [r for r in both if data[other][r]]
            for label, mine in (("种子 1", lambda r: small(second[r])), ("两遍平均", lambda r: (small(second[r]) + small(data[SECOND][r])) / 2)):
                diffs = [mine(r) - small(data[other][r]) for r in rooms]
                p = sign_flip_p(diffs)
                lines.append(f"| {dict(ARMS)[SECOND]}（{label}） − {dict(ARMS)[other]} | {', '.join(f'{d:+g}' for d in diffs)} | {sum(diffs):+g} | {p:.3f} |")
                summary["second_seed"]["paired"][f"{label} - {other}"] = {"rooms": rooms, "diffs": diffs, "p_sign_flip": p}
    (out / "README.md").write_text("\n".join(lines) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
