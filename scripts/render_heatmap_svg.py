#!/usr/bin/env python3
"""Render data/contributions.json as a 53-week x 7-day PNG heatmap.

Draws the grid directly with Pillow (no SVG conversion), using GitHub's green
ramp, a Less->More legend, and a stats footer. Output: contrib-heatmap.png
"""
import json
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
#               none -> 1       -> 2       -> 3       -> 4       -> 5(neon top)

INPUT = os.path.join("data", "contributions.json")
OUTPUT = "contrib-heatmap.png"

CELL = 11
GAP = 3
WEEKS = 53
DAYS = 7
PAD_X = 14
HEADER_H = 26
SCALE = 1          # keep 1x; bump to 2 for retina
MULT = 2           # draw at 2x for crispness, then downscale
M = MULT


def color_for(level: int) -> str:
    return PALETTE[level] if level < len(PALETTE) else PALETTE[-1]


def fmt_count(n: int) -> str:
    return f"{n:,}"


def font(size: int):
    for name in ("segoeui.ttc", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size * M)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    with open(INPUT, encoding="utf-8") as fh:
        data = json.load(fh)
    days, stats = data["days"], data["stats"]

    grid_w = WEEKS * (CELL + GAP) - GAP
    grid_h = DAYS * (CELL + GAP) - GAP
    footer_h = 46
    width = PAD_X * 2 + grid_w
    height = HEADER_H + grid_h + footer_h

    img = Image.new("RGBA", (width * M, height * M), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cell = {}
    for day in days:
        col = day["ix"]
        row = datetime.strptime(day["date"], "%Y-%m-%d").weekday()  # Mon=0..Sun=6
        cell[(col, row)] = day

    def cx(c): return (PAD_X + c * (CELL + GAP)) * M
    def cy(r): return (HEADER_H + r * (CELL + GAP)) * M

    # month labels
    months = {}
    for day in days:
        m = day["date"][:7]
        if m not in months:
            months[m] = day["ix"]
    for m, ix in list(months.items())[1:]:
        d.text((cx(ix) + CELL * M / 2, HEADER_H * M - 14 * M), m,
               font=font(10), fill="#8b949e", anchor="ms")

    # weekday glyphs
    for r, lab in [(2, "Wed"), (4, "Fri")]:
        d.text((cx(0) - 5 * M, cy(r) + CELL * M + 4 * M), lab,
               font=font(9), fill="#8b949e", anchor="ms")

    # cells
    for ix in range(WEEKS):
        for row in range(DAYS):
            day = cell.get((ix, row))
            if day is None:
                continue
            d.rounded_rectangle(
                [cx(ix), cy(row), cx(ix) + CELL * M, cy(row) + CELL * M],
                radius=int(2.5 * M), fill=color_for(day["level"])
            )

    # footer
    fy_title = (HEADER_H + grid_h + 16) * M
    d.text((PAD_X * M, fy_title), f"{fmt_count(stats['total'])} contributions in the last year",
           font=font(13), fill="#e6edf3", anchor="ls")
    d.text(
        (PAD_X * M, fy_title + 16 * M),
        f"Best day: {fmt_count(stats['best_day']['count'])}  |  "
        f"Longest streak: {stats['longest_streak']} days  |  "
        f"Current streak: {stats['current_streak']} days",
        font=font(11), fill="#8b949e", anchor="ls",
    )

    # legend Less -> boxes -> More
    legend_y = fy_title + 30 * M
    d.text((PAD_X * M, legend_y), "Less", font=font(9), fill="#8b949e", anchor="lm")
    box_x = (PAD_X + 32) * M
    for i, c in enumerate(PALETTE[1:]):
        d.rounded_rectangle(
            [box_x + i * (CELL * M + 4 * M), legend_y - int(5 * M),
             box_x + i * (CELL * M + 4 * M) + CELL * M, legend_y + int(6 * M)],
            radius=int(2.5 * M), fill=c
        )
    d.text((box_x + 5 * (CELL * M + 4 * M) + 4 * M, legend_y), "More",
           font=font(9), fill="#8b949e", anchor="lm")

    img = img.resize((width, height), Image.LANCZOS)
    img.save(OUTPUT, "PNG")
    print(f"Wrote {OUTPUT} ({stats['total']} contributions)")


if __name__ == "__main__":
    main()