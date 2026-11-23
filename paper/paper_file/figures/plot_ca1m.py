"""Rebuild the manuscript figures from the saved CA-1M reconstructions and scores."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

FIGURES = Path(__file__).resolve().parent
RESULTS = FIGURES.parents[2] / "evan" / "results"
BASELINE_LABEL = "AHa-3D (baseline)"
VARIANTS = [
    ("A0", BASELINE_LABEL, "#454c59"),
    ("A1", "All objects", "#3979ac"),
    ("A2", "Inventory", "#008477"),
    ("A3r", "Required generation", "#ab5a0f"),
    ("A3v", "Selective generation", "#896296"),
]


def image_grid(rows, labels, name):
    fig, axes = plt.subplots(len(rows), 3, figsize=(7, 3.16))
    for row, row_axes in zip(rows, axes):
        for img, ax in zip(row, row_axes):
            ax.imshow(img, aspect="equal")
            ax.set_axis_off()
    for label, ax in zip(labels, axes[0]):
        ax.set_title(label, fontsize=11, pad=4)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=0.925, wspace=0.015, hspace=0.025)
    fig.savefig(FIGURES / name, dpi=250, bbox_inches="tight", pad_inches=0.01)
    plt.close(fig)


def scope_comparison():
    rows = []
    # Each archived sheet has a 150-pixel margin and 96-pixel title, then
    # three 768-by-576 views per row. Apply the same crop to all three panels.
    for scene, view, top in [("45261575", 0, 170), ("47331262", 1, 70)]:
        panels = []
        for variant, sheet_row in [("A0", 0), ("A0", 1), ("A1", 1)]:
            x = 150 + view * 768
            y = 96 + sheet_row * 576 + top
            with Image.open(RESULTS / "renders" / f"{variant}_{scene}.jpg") as sheet:
                panels.append(sheet.crop((x, y, x + 768, y + 406)))
        rows.append(panels)
    image_grid(rows, ["Input video frame", BASELINE_LABEL, "Ours (all objects)"], "ca1m-scope.pdf")


def experimental_settings():
    # First matched camera view in the held-out living-room sheet: input above
    # the All objects reconstruction. The original panels are 768 by 576.
    with Image.open(RESULTS / "renders" / "A1_42897538.jpg") as sheet:
        captured = [sheet.crop((150, y, 918, y + 576)) for y in (96, 672)]
    with Image.open(FIGURES / "ai2thor-source.png") as source:
        with Image.open(FIGURES / "ai2thor-reconstruction.png") as reconstruction:
            panels = [*captured, source.copy(), reconstruction.copy()]
    fig = plt.figure(figsize=(7, 1.45))
    pairs = fig.add_gridspec(1, 2, left=0, right=1, top=0.80, bottom=0.01, wspace=0.08)
    for pair_index, title in enumerate(("CA-1M", "AI2-THOR")):
        grid = pairs[0, pair_index].subgridspec(1, 2, wspace=0.015)
        for col in range(2):
            ax = fig.add_subplot(grid[0, col])
            ax.imshow(panels[2 * pair_index + col])
            ax.set_axis_off()
        bounds = pairs[0, pair_index].get_position(fig)
        fig.text((bounds.x0 + bounds.x1) / 2, 0.90, title, ha="center", va="center", fontsize=11)
    fig.savefig(FIGURES / "experimental-settings.pdf", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def coffee_table_physics():
    source = RESULTS / "showcase" / "42897538_A2" / "triptych_000616.jpg"
    with Image.open(source) as sheet:
        panel_width = sheet.width // 3
        # Identical crop in the input and scored geometry panels of the same frame.
        panels = [sheet.crop((i * panel_width + 86, 185, i * panel_width + 855, 600))
                  for i in (0, 1)]
    with Image.open(FIGURES / "coffee-rest.png") as simulation:
        panels.append(simulation.crop((80, 125, 575, 562)))
    with Image.open(FIGURES / "tissue-density.png") as density:
        panels.append(density.copy())

    labels = ["Input video frame", "Inventory reconstruction",
              "Rigid-body simulation", "Predicted tissue-box density"]
    fig, axes = plt.subplots(2, 2, figsize=(6.2, 3.65),
                             gridspec_kw={"height_ratios": [0.93, 1.07]})
    for ax, panel, label in zip(axes.flat, panels, labels):
        ax.imshow(panel)
        ax.set_title(label, fontsize=10, pad=3)
        ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0, top=0.94, wspace=0.03, hspace=0.2)
    fig.savefig(FIGURES / "ca1m-coffee-physics.pdf", dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def small_placement_by_room():
    runs = json.loads((RESULTS / "test_opus" / "summary.json").read_text())["runs"]
    rooms = ["42897538/0", "42898849/0", "42899617/0"]
    fig, ax = plt.subplots(figsize=(7.1, 1.8))
    centers = np.arange(len(rooms))
    for index, (arm, name, color) in enumerate(VARIANTS[:3]):
        counts = []
        for room in rooms:
            small = runs[arm][room]["summary_sim3"]["S"]
            counts.append(round(small["n"] * small["recall_D"]))
        bars = ax.bar(centers + (index - 1) * 0.22, counts, width=0.20,
                      label=name, color=color)
        ax.bar_label(bars, padding=2, fontsize=9)
    labels = [f"{label} ({runs['A0'][room]['summary_sim3']['S']['n']} targets)"
              for label, room in zip(["Living room", "Second room", "Third room"], rooms)]
    ax.set(xticks=centers, xticklabels=labels, yticks=[0, 5, 10, 15, 20], ylim=(0, 20))
    ax.set_ylabel("Correct placements", fontsize=10)
    ax.tick_params(length=0, labelsize=10)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#a5a7aa")
    ax.grid(axis="y", color="#dddddd", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", ncol=3,
               fontsize=10, frameon=False, handlelength=1.2)
    fig.subplots_adjust(left=0.09, right=0.99, bottom=0.14, top=0.78)
    fig.savefig(FIGURES / "ca1m-placement-by-room.pdf", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def recall_plot():
    arms = json.loads((FIGURES.parent / "existing-results.json").read_text())["arms"]
    fig, axes = plt.subplots(1, 2, sharey=True, figsize=(7, 2.78))
    bins = ["XS", "S", "M", "L"]
    positions = np.arange(len(bins))
    for ax, aggregation, title in zip(axes, ["pooled", "macro"], ["Pooled objects", "Equal room weight"]):
        for idx, (arm, name, color) in enumerate(VARIANTS):
            scores = arms[arm][aggregation]
            values = [scores[b]["recall"] if aggregation == "pooled" else scores[b] for b in bins]
            ax.bar(positions + (idx - 2) * 0.16, np.asarray(values) * 100, width=0.15,
                   color=color, label=name)
        ax.set(xticks=positions, xticklabels=["<20", "20–<50", "50–<150", "≥150"],
               ylim=(0, 52), yticks=range(0, 51, 10), title=title)
        ax.tick_params(length=0, pad=4, labelsize=9)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#a5a7aa")
        ax.grid(axis="y", color="#dedede", linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Correctly placed (%)", fontsize=10)
    fig.text(0.54, 0.24, "Longest annotated side (cm)", ha="center", fontsize=10)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3,
               fontsize=9, frameon=False, handlelength=1.1, columnspacing=1.6)
    fig.subplots_adjust(left=0.075, right=0.995, top=0.89, bottom=0.39, wspace=0.10)
    fig.savefig(FIGURES / "ca1m-recall.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    plt.rcParams.update({"pdf.fonttype": 42, "pdf.compression": 9, "axes.titlesize": 11})
    scope_comparison()
    experimental_settings()
    coffee_table_physics()
    small_placement_by_room()
    recall_plot()
