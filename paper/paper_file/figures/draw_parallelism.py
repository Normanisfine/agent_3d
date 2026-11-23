#!/usr/bin/python3
"""Draw Figure 2 and export the editable SVG, web preview, and print assets."""
from pathlib import Path
from html import escape

from subprocess import run

OUT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1040, 535
INK, LINE = "#183746", "#44616b"
TEAL, BLUE = "#006f68", "#28588a"
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
       f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
       '<title id="title">Control of planning, construction, and repair</title>',
       '<desc id="desc">Original AHa-3D builds and revises a room scene. AHA-driven '
       'and AHA-auto convert an object inventory into a task dependency graph. An '
       'agent or a Python scheduler dispatches workers and handles repairs. All '
       'three pipelines lead to room-level review.</desc>',
       '<rect width="100%" height="100%" fill="white"/>']


def label(x, y, text, size, *, color=INK, bold=False, anchor="start"):
    svg.append(f'<text x="{x}" y="{y}" fill="{color}" text-anchor="{anchor}" '
               f'font-family="DejaVu Sans, sans-serif" font-size="{size}" '
               f'font-weight="{700 if bold else 400}">{escape(text)}</text>')


def line(path, color=LINE):
    svg.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.5" '
               'stroke-linecap="round" stroke-linejoin="round"/>')


def rect(x, y, w, h, fill, stroke="none", radius=7):
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')


def down(x, y1, y2, color=LINE):
    line(f"M{x} {y1} V{y2} m-5 -6 5 6 5 -6", color)


def task(x, y, name, color):
    rect(x, y, 75, 31, "white", color, 5)
    label(x + 37.5, y + 22, name, 20, anchor="middle")


def graph(x, color):
    # Only the lamp consumes the desk's completed geometry.
    task(x, 131, "Desk", color)
    line(f"M{x+75} 147 h40 m-6 -5 6 5 -6 5", color)
    task(x + 118, 131, "Lamp", color)
    task(x, 171, "Chair", color)


# Each method runs from top to bottom. The left margin aligns like stages.
columns = [
    (120, "Original AHa-3D", "#4d5d69", "#f0f2f4"),
    (427, "AHA-driven", TEAL, "#eaf4f0"),
    (734, "AHA-auto", BLUE, "#edf3f9"),
]
for x, name, color, tint in columns:
    center = x + 145
    rect(x, 6, 290, 49, color)
    label(center, 40, name, 30, color="white", bold=True, anchor="middle")
    down(center, 56, 76)

rect(120, 82, 290, 131, columns[0][3])
label(7, 152, "Plan", 26, bold=True)
label(265, 114, "Scene workflow skill", 25, bold=True, anchor="middle")
label(265, 157, "Major objects", 24, anchor="middle")
label(265, 187, "in one room plan", 23, anchor="middle")

rect(427, 82, 597, 131, "#edf4f3")
label(725, 113, "Planning agent", 25, bold=True, anchor="middle")
label(451, 165, "Object inventory", 23)
line("M634 157 h47 m-6 -5 6 5 -6 5")
graph(726, LINE)

# Only the original and driven execution stages have an agent in control.
rect(109, 238, 617, 218, "white", LINE, 11)
rect(333, 223, 169, 31, "white")
label(417, 245, "Agent control", 23, color=INK, bold=True, anchor="middle")
for x, name, color, tint in columns:
    center = x + 145
    down(center, 214, 260)
    rect(x, 266, 290, 73, tint)
    down(center, 340, 363)
    rect(x, 369, 290, 69, tint)
    line(f"M{center} 439 V467")

svg.append('<g transform="translate(0,22)">')
for y, stage in [(288, "Build"), (389, "Repair")]:
    label(7, y, stage, 26, bold=True)
for x, heading, detail in [
        (265, "Scene authoring agent", "Builds objects in sequence"),
        (572, "Supervising agent", "Delegates to workers"),
        (879, "Python scheduler", "Dispatches parallel builds")]:
    label(x, 275, heading, 24, bold=True, anchor="middle")
    label(x, 303, detail, 22, anchor="middle")

for x, heading, detail in [
        (265, "Scene authoring agent", "Revises the room"),
        (572, "Supervising agent", "Chooses object repairs"),
        (879, "Python scheduler", "Retries, escalates or blocks")]:
    label(x, 377, heading, 24, bold=True, anchor="middle")
    label(x, 404, detail, 22, anchor="middle")

line("M265 445 H879")
down(572, 445, 461)
rect(397, 466, 350, 42, INK)
label(572, 495, "Room-level review", 26, bold=True, color="white", anchor="middle")
svg.append('</g>')

svg.append('</svg>')
art = "\n".join(svg)
(OUT / "parallelism.svg").write_text(art + "\n")
(OUT / "parallelism.html").write_text(
    '<!doctype html><html lang="en"><meta charset="utf-8"><title>Reconstruction controllers</title>'
    '<style>svg{display:block;width:100%;max-width:1040px;height:auto;margin:auto}</style>'
    f'<body>{art}</body></html>\n'
)

# MuPDF preserves vector paths and searchable labels in the print edition.
run(["mutool", "draw", "-q", "-F", "pdf", "-o", str(OUT / "parallelism.pdf"),
     str(OUT / "parallelism.svg")], check=True)
run(["pdftoppm", "-singlefile", "-png", "-scale-to", str(WIDTH * 3),
     str(OUT / "parallelism.pdf"), str(OUT / "parallelism")], check=True)
