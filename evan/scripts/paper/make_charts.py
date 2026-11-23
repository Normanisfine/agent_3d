"""论文里的结果图（一张三栏组合图，矢量 PDF），数来自 paper/smallobj/figures/data.json（scripts/paper/figure_data.py 写的）。

版式参考 github.com/ChenLiu-1996/figures4papers：竖条、无网格、只留左和下两条轴线、图例单放、本文方法用深蓝，其余用浅色。
a  四个尺寸档各一栏，四个组各一根条：实心是建对的比例，上面带斜线的一段是配上但摆错的；建对的个数标在条的正下方，每档最多的加粗
b  每个房间 50 cm 以下目标建对的比例，四个组各一根条；Checklist 的第二遍用菱形标在条上
c  横轴：重建实例（或清单条目）里配上标注目标的比例；纵轴：50 cm 以下建对的个数。空心方块是清单的框不经 agent 直接打分，
   箭头指向拿到这份清单的 agent 那一遍；空心菱形是 Checklist 的第二遍（和 b 一样）
用法：.runtime/venv/bin/python scripts/paper/make_charts.py   输出 paper/smallobj/figures/results.pdf
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

FIG = Path(__file__).resolve().parents[2] / "paper" / "smallobj" / "figures"
D = json.loads((FIG / "data.json").read_text())
ROOMS, BINS, SMALL = D["rooms"], ["XS", "S", "M", "L"], ("XS", "S")
BIN_TITLE = {"XS": "< 20 cm", "S": "20 – 50 cm", "M": "0.5 – 1.5 m", "L": "≥ 1.5 m"}
ARMS = ["A0", "A1", "A2", "A5"]
NAME = {"A0": "AHa-3D baseline", "A1": "All objects", "A2": "Inventory", "A5": "Checklist (ours)"}
FILL = {"A0": "#CFCECE", "A1": "#AADCA9", "A2": "#E9A6A1", "A5": "#3775BA"}
DARK = {"A0": "#767676", "A1": "#4E9A4D", "A2": "#B64342", "A5": "#0F4D92"}
INK = "#272727"

plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Nimbus Sans", "Helvetica", "Arial", "Liberation Sans", "DejaVu Sans"],
                     "font.size": 7.5, "axes.spines.right": False, "axes.spines.top": False, "axes.linewidth": 0.9,
                     "axes.edgecolor": INK, "xtick.color": INK, "ytick.color": INK, "text.color": INK, "axes.labelcolor": INK,
                     "xtick.major.width": 0.9, "ytick.major.width": 0.9, "xtick.major.size": 3, "ytick.major.size": 3,
                     "legend.frameon": False, "pdf.fonttype": 42, "hatch.linewidth": 0.6, "savefig.pad_inches": 0.01})


def total(arm, b, key):
    return sum(D["arms"][arm][s][b][key] for s in ROOMS)


def small_correct(group, name, s):
    return sum(D[group][name][s][b]["correct"] for b in SMALL)


def panel_letter(fig, ax, letter, dx=-0.02):
    box = ax.get_position()
    fig.text(box.x0 + dx, box.y1 + 0.035, letter, fontsize=11, fontweight="bold", ha="right", va="bottom")


def by_size(fig, gs):
    axes = [fig.add_subplot(gs[0, i]) for i in range(4)]
    for ax, b in zip(axes, BINS):
        n = total("A0", b, "n")
        best = max(total(arm, b, "correct") for arm in ARMS)
        for i, arm in enumerate(ARMS):
            c, m = 100 * total(arm, b, "correct") / n, 100 * total(arm, b, "misplaced") / n
            ax.bar(i, c, width=0.74, color=FILL[arm], edgecolor=DARK[arm], linewidth=0.8, zorder=3)
            ax.bar(i, m, bottom=c, width=0.74, color="white", edgecolor=DARK[arm], linewidth=0.8, hatch="//////", zorder=2)
            # 建对的个数标在条的正下方（标在条顶上会被读成实心加斜线的合计）
            ax.text(i, -2.6, str(total(arm, b, "correct")), ha="center", va="top", fontsize=7.5,
                    fontweight="bold" if total(arm, b, "correct") == best else "normal", color=DARK[arm] if arm != "A0" else INK)
        ax.set_xticks([])
        ax.set_xlim(-0.75, 3.75)
        ax.set_ylim(0, 72)
        ax.set_yticks([0, 20, 40, 60])
        ax.set_title(BIN_TITLE[b], fontsize=8.5, pad=11)
        ax.text(0.5, 1.02, f"{n} targets", transform=ax.transAxes, ha="center", va="bottom", fontsize=7, color="#767676")
        if ax is not axes[0]:
            ax.set_yticklabels([])
    axes[0].set_ylabel("targets (%)")
    axes[0].text(-0.95, -2.6, "correct", ha="right", va="top", fontsize=7, color="#767676")
    return axes


def legend(fig, ax):
    ax.set_axis_off()
    hs = [plt.Rectangle((0, 0), 1, 1, fc=FILL[a], ec=DARK[a], lw=0.8) for a in ARMS]
    lg = ax.legend(hs, [NAME[a] for a in ARMS], loc="upper left", bbox_to_anchor=(-0.12, 1.13), fontsize=7.5, handlelength=1.3, handleheight=0.9,
                   labelspacing=0.55, borderaxespad=0)
    lg.get_texts()[-1].set_fontweight("bold")
    ax.add_artist(lg)
    hs2 = [plt.Rectangle((0, 0), 1, 1, fc="#8a8a8a", ec=INK, lw=0.8), plt.Rectangle((0, 0), 1, 1, fc="white", ec=INK, lw=0.8, hatch="//////")]
    ax.legend(hs2, ["correctly placed", "matched, misplaced"], loc="lower left", bbox_to_anchor=(-0.12, -0.04), fontsize=7,
              handlelength=1.3, handleheight=0.9, labelspacing=0.55, borderaxespad=0)


def by_room(fig, ax):
    n = {s: sum(D["targets"][s][b] for b in SMALL) for s in ROOMS}
    w = 0.19
    for g, s in enumerate(ROOMS):
        for i, arm in enumerate(ARMS):
            x = g + (i - 1.5) * w
            ax.bar(x, 100 * small_correct("arms", arm, s) / n[s], width=w * 0.92, color=FILL[arm], edgecolor=DARK[arm], linewidth=0.8, zorder=3)
        x5, a, b = g + 1.5 * w, 100 * small_correct("arms", "A5", s) / n[s], 100 * small_correct("arms", "A5s1", s) / n[s]
        ax.plot([x5, x5], [a, b], color=DARK["A5"], lw=1.0, zorder=4)
        ax.plot(x5, b, marker="D", ms=3.6, mfc="white", mec=DARK["A5"], mew=1.0, zorder=5)
    ax.set_xticks(range(len(ROOMS)), [f"Room {i + 1}\n$n$ = {n[s]}" for i, s in enumerate(ROOMS)], fontsize=7)
    ax.tick_params(axis="x", length=0, pad=3)
    ax.set_xlim(-0.55, len(ROOMS) - 0.45)
    ax.set_ylim(0, 62)
    ax.set_yticks([0, 20, 40, 60])
    ax.set_ylabel("correct, < 50 cm (%)")
    ax.plot([], [], marker="D", ms=3.6, mfc="white", mec=DARK["A5"], mew=1.0, ls="none", label="Checklist, second run")
    ax.legend(loc="upper left", bbox_to_anchor=(0.25, 1.10), fontsize=7, handletextpad=0.3, borderaxespad=0)


def tradeoff(fig, ax):
    def point(group, name):
        d = D[group][name]
        return 100 * sum(d[s]["matched"] for s in ROOMS) / sum(d[s]["n"] for s in ROOMS), sum(small_correct(group, name, s) for s in ROOMS)

    pts = {k: point("arms", k) for k in ARMS + ["A5s1"]} | {k: point("lists", k) for k in ("boxer", "checklist")}
    for src, dst, arm in (("boxer", "A2", "A2"), ("checklist", "A5", "A5")):
        ax.annotate("", xy=pts[dst], xytext=pts[src], arrowprops=dict(arrowstyle="-|>", color=DARK[arm], lw=1.0, shrinkA=4.5, shrinkB=5, mutation_scale=8))
    ax.plot(*pts["boxer"], marker="s", mfc="white", mec=DARK["A2"], mew=1.1, ms=4.6, ls="none", zorder=4)
    ax.plot(*pts["checklist"], marker="s", mfc="white", mec=DARK["A5"], mew=1.1, ms=4.6, ls="none", zorder=4)
    for arm in ARMS:
        ax.plot(*pts[arm], marker="o", mfc=FILL[arm], mec=DARK[arm], mew=0.9, ms=6.2, ls="none", zorder=5)
    ax.plot(*pts["A5s1"], marker="D", mfc="white", mec=DARK["A5"], mew=1.1, ms=4.4, ls="none", zorder=5)
    labels = {"A0": ("Baseline", (0, 9), "center"), "A1": ("All objects", (7, 0), "left"), "A2": ("Inventory", (7, 2), "left"),
              "A5": ("Checklist", (-10, -1), "right"), "A5s1": ("2nd run", (7, 3), "left"),
              "boxer": ("Boxer boxes,\nno agent", (-8, -7), "right"), "checklist": ("Checklist boxes,\nno agent", (10, 5), "left")}
    for k, (text, off, ha) in labels.items():
        ax.annotate(text, pts[k], xytext=off, textcoords="offset points", ha=ha, va="center", fontsize=7, linespacing=0.95,
                    fontweight="bold" if k == "A5" else "normal")
    ax.set_xlim(0, 122)  # 右边留给三个组名；轴线只画到 100
    ax.spines["bottom"].set_bounds(0, 100)
    ax.set_ylim(0, 235)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_yticks([0, 50, 100, 150, 200])
    ax.set_xlabel("instances matching a target (%)", x=0.41)
    ax.set_ylabel("correct, < 50 cm (count)")
    return pts


def main():
    fig = plt.figure(figsize=(5.5, 3.3))
    top = GridSpec(1, 5, figure=fig, left=0.085, right=0.995, top=0.887, bottom=0.565, wspace=0.16, width_ratios=[1, 1, 1, 1, 1.12])
    axes = by_size(fig, top)
    legend(fig, fig.add_subplot(top[0, 4]))
    bottom = GridSpec(1, 2, figure=fig, left=0.085, right=0.995, top=0.405, bottom=0.122, wspace=0.25, width_ratios=[1.5, 1])
    ax_b, ax_c = fig.add_subplot(bottom[0, 0]), fig.add_subplot(bottom[0, 1])
    by_room(fig, ax_b)
    pts = tradeoff(fig, ax_c)
    panel_letter(fig, axes[0], "a", dx=-0.045)
    panel_letter(fig, ax_b, "b", dx=-0.045)
    panel_letter(fig, ax_c, "c", dx=-0.05)
    fig.savefig(FIG / "results.pdf")
    plt.close(fig)
    print({k: (round(x, 1), y) for k, (x, y) in pts.items()})


if __name__ == "__main__":
    main()
