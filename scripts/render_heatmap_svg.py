#!/usr/bin/env python3
"""Render data/contributions.json as a 53-week x 7-day heatmap SVG.

Uses GitHub's green contribution ramp, a one-shot diagonal slide-down reveal
animation on load, a Less->More legend, and a stats footer. Output is
written to contrib-heatmap.svg in the current directory.
"""
import json
import os
from collections import OrderedDict
from datetime import datetime

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
#               none -> 1       -> 2       -> 3       -> 4       -> 5 (neon top)

INPUT = os.path.join("data", "contributions.json")
OUTPUT = "contrib-heatmap.svg"

CELL = 11          # cell dimension (px)
GAP = 3            # gap between cells (px)
WEEKS = 53
DAYS = 7
PAD_X = 14         # left/right padding for the grid
HEADER_H = 26      # room above grid for month labels
WIDTH = PAD_X * 2 + WEEKS * (CELL + GAP) - GAP
HEIGHT = HEADER_H + DAYS * (CELL + GAP) - GAP + 46   # room for footer
FOOTER_Y = HEADER_H + DAYS * (CELL + GAP) + 2


def color_for(level: int) -> str:
    return PALETTE[level] if level < len(PALETTE) else PALETTE[-1]


def fmt_count(n: int) -> str:
    return f"{n:,}"


def month_labels(days: list[dict]) -> list[dict]:
    """Approximate month start positions for the header (skip first)."""
    labels = OrderedDict()
    for d in days:
        m = d["date"][:7]
        if m not in labels:
            labels[m] = d["ix"]
    items = list(labels.items())[1:]   # skip first (aligned to left edge)
    return [{"label": m, "col": ix} for m, ix in items]


def build_svg(days: list[dict], stats: dict, username: str) -> str:
    cell = {}
    for d in days:
        col = d["ix"]
        row = datetime.strptime(d["date"], "%Y-%m-%d").weekday()  # Mon=0..Sun=6
        cell[(col, row)] = d

    def cx(c: int) -> int:
        return PAD_X + c * (CELL + GAP)

    def cy(r: int) -> int:
        return HEADER_H + r * (CELL + GAP)

    month_markup = "".join(
        f'<text x="{cx(m["col"]) + CELL / 2}" y="{HEADER_H - 8}" text-anchor="middle" '
        f'font-family="Segoe UI,Arial" font-size="10" fill="#8b949e">{m["label"]}</text>'
        for m in month_labels(days)
    )

    edge_marks = []
    for r, lab in [(2, "Wed"), (4, "Fri")]:
        edge_marks.append(
            f'<text x="{cx(0) - 6}" y="{cy(r) + CELL + 2}" text-anchor="end" '
            f'font-family="Segoe UI,Arial" font-size="9" fill="#8b949e">{lab}</text>'
        )

    # cells + diagonal-ordered reveal delay
    rects = []
    for ix in range(WEEKS):
        for row in range(DAYS):
            d = cell.get((ix, row))
            if d is None:
                continue
            delay = (row + ix) * 0.012
            rects.append(
                f'<rect data-date="{d["date"]}" x="{cx(ix)}" y="{cy(row)}" '
                f'width="{CELL}" height="{CELL}" rx="2.5" fill="{color_for(d["level"])}" '
                f'class="slide" style="animation-delay:{delay:.3f}s">'
                f'<title>{d["count"]} contributions on {d["date"]}</title></rect>'
            )
    rects = "".join(rects)

    css = """<style>
      svg { background: transparent; }
      .slide { opacity: 0; transform: translateY(14px); animation: slip 0.5s ease forwards; }
      @keyframes slip { to { opacity: 1; transform: translateY(0); } }
    </style>"""

    # legend (Less -> boxes -> More)
    legend_x = PAD_X
    legend_y = FOOTER_Y + 18
    legend = (
        f'<text x="{legend_x}" y="{legend_y}" font-family="Segoe UI,Arial" font-size="10" '
        f'fill="#8b949e">Less</text>'
    )
    legend_boxes = "".join(
        f'<rect x="{legend_x + 34 + i * (CELL + 3)}" y="{legend_y - 9}" width="{CELL}" '
        f'height="{CELL}" rx="2.5" fill="{c}"/>'
        for i, c in enumerate(PALETTE[1:])
    )
    legend += legend_boxes + (
        f'<text x="{legend_x + 34 + 5 * (CELL + 3) + 4}" y="{legend_y}" font-family="Segoe UI,Arial" '
        f'font-size="10" fill="#8b949e">More</text>'
    )

    total = fmt_count(stats["total"])
    footer = (
        f'<text x="{PAD_X}" y="{FOOTER_Y}" font-family="Segoe UI,Arial" font-size="13" '
        f'font-weight="600" fill="#e6edf3">{total} contributions in the last year</text>'
    )
    stats_line = (
        f'<text x="{PAD_X}" y="{FOOTER_Y + 18}" font-family="Segoe UI,Arial" font-size="11" '
        f'fill="#8b949e">Best day: {fmt_count(stats["best_day"]["count"])} '
        f'&middot; Longest streak: {stats["longest_streak"]} days '
        f'&middot; Current streak: {stats["current_streak"]} days</text>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
{css}
{month_markup}
{''.join(edge_marks)}
{rects}
{legend}
{footer}
{stats_line}
</svg>
"""


def main() -> None:
    with open(INPUT, encoding="utf-8") as fh:
        data = json.load(fh)
    days, stats, username = data["days"], data["stats"], data["username"]
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write(build_svg(days, stats, username))
    print(f"Wrote {OUTPUT} ({len(days)} days, {stats['total']} contributions)")


if __name__ == "__main__":
    main()