"""论文里的表格行（LaTeX），数来自 paper/smallobj/figures/data.json，避免手抄。写到 paper/smallobj/tables/。

main_rows.tex    主表：50 cm 以下 建对 / 摆错 / 没建，实例数，配上标注的比例，平均分钟和美元
paired_rows.tex  按房间配对的差和精确符号翻转检验
rooms_rows.tex   附录：每个房间每个组的建对数
用法：.runtime/venv/bin/python scripts/paper/make_tables.py
"""
import itertools
import json
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "paper" / "smallobj"
D = json.loads((P / "figures" / "data.json").read_text())
ROOMS, SMALL = D["rooms"], ("XS", "S")


def get(group, name):
    d = D[group][name]
    out = {k: sum(d[s][b][k] for s in ROOMS for b in SMALL) for k in ("correct", "misplaced", "missed")}
    out["n"], out["matched"] = sum(d[s]["n"] for s in ROOMS), sum(d[s]["matched"] for s in ROOMS)
    if group == "arms":
        out["min"], out["usd"] = (sum(d[s][k] for s in ROOMS) / len(ROOMS) for k in ("minutes", "usd"))
    return out


def per_room(name):
    return [sum(D["arms"][name][s][b]["correct"] for b in SMALL) for s in ROOMS]


def sign_flip_p(diffs):
    obs = abs(sum(diffs))
    hits = sum(abs(sum(d * s for d, s in zip(diffs, signs))) >= obs - 1e-12 for signs in itertools.product((1, -1), repeat=len(diffs)))
    return hits / 2 ** len(diffs)


def main():
    (P / "tables").mkdir(exist_ok=True)
    rows = []
    for label, group, name in (("AHa-3D baseline", "arms", "A0"), ("All objects", "arms", "A1"), ("Inventory", "arms", "A2"),
                               ("Checklist (ours)", "arms", "A5"), ("Checklist, second run", "arms", "A5s1"),
                               ("Boxer boxes, no agent", "lists", "boxer"), ("Checklist boxes, no agent", "lists", "checklist")):
        g = get(group, name)
        if name == "boxer":
            rows.append("\\midrule")
        cost = f"{g['min']:.0f} & {g['usd']:.2f}" if group == "arms" else "-- & --"
        c = f"\\textbf{{{g['correct']}}}" if name in ("A5", "A5s1") else str(g["correct"])
        n = f"{g['n']:,}".replace(",", "{,}")
        rows.append(f"{label} & {c} & {g['misplaced']} & {g['missed']} & {n} & {100 * g['matched'] / g['n']:.0f}\\% & {cost} \\\\")
    (P / "tables" / "main_rows.tex").write_text("\n".join(rows) + "\n")

    pairs = [("All objects $-$ baseline", per_room("A1"), per_room("A0")), ("Inventory $-$ All objects", per_room("A2"), per_room("A1")),
             ("Checklist $-$ All objects", per_room("A5"), per_room("A1")), ("Checklist $-$ Inventory", per_room("A5"), per_room("A2")),
             None,
             ("Second run $-$ All objects", per_room("A5s1"), per_room("A1")), ("Second run $-$ Inventory", per_room("A5s1"), per_room("A2")),
             ("Second run $-$ first run", per_room("A5s1"), per_room("A5"))]
    rows = []
    for p in pairs:
        if p is None:
            rows.append("\\midrule")
            continue
        label, a, b = p
        diffs = [x - y for x, y in zip(a, b)]
        rows.append(f"{label} & " + " & ".join(f"${d:+d}$" for d in diffs) + f" & ${sum(diffs):+d}$ & {sign_flip_p(diffs):.3f} \\\\")
    (P / "tables" / "paired_rows.tex").write_text("\n".join(rows) + "\n")

    n = [sum(D["targets"][s][b] for b in SMALL) for s in ROOMS]
    rows = ["Targets under 50\\,cm & " + " & ".join(map(str, n)) + f" & {sum(n)} \\\\", "\\midrule"]
    for label, name in (("AHa-3D baseline", "A0"), ("All objects", "A1"), ("Inventory", "A2"), ("Checklist (ours)", "A5"), ("Checklist, second run", "A5s1")):
        v = per_room(name)
        rows.append(f"{label} & " + " & ".join(map(str, v)) + f" & {sum(v)} \\\\")
    rows.append("\\midrule")
    for label, name in (("Instances, Checklist", "A5"), ("\\quad matching a target", "A5")):
        v = [D["arms"][name][s]["matched" if "matching" in label else "n"] for s in ROOMS]
        rows.append(f"{label} & " + " & ".join(map(str, v)) + f" & {sum(v)} \\\\")
    dec = [D["arms"]["A5"][s]["decisions"] for s in ROOMS]
    for k in ("built", "duplicate", "part", "skipped"):
        v = [d.get(k, 0) for d in dec]
        rows.append(f"Checklist entries: {k} & " + " & ".join(map(str, v)) + f" & {sum(v):,} \\\\".replace(",", "{,}"))
    (P / "tables" / "rooms_rows.tex").write_text("\n".join(rows) + "\n")
    for f in sorted((P / "tables").glob("*.tex")):
        print("==", f.name)
        print(f.read_text())


if __name__ == "__main__":
    main()
