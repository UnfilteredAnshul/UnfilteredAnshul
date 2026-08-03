#!/usr/bin/env python3
"""Render data/contributions.json as an animated contribution heatmap GIF.

Frames sweep diagonally (line-by-line reveal), play once, then hold the full
grid. A GIF renders as a normal image on GitHub AND animates reliably.

Outputs: contrib-heatmap.gif
"""
import json
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
#               none -> 1       -> 2       -> 3       -> 4       -> 5(neon top)

INPUT = os.path.join("data", "contributions.json")
OUTPUT = "contrib-heatmap.gif"

CELL = 11
GAP = 3
WEEKS = 53
DAYS = 7
PAD_X = 14
HEADER_H = 26
BG = (13, 17, 23, 255)

WIDTH = PAD_X * 2 + WEEKS * (CELL + GAP) - GAP
HEIGHT = HEADER_H + DAYS * (CELL + GAP) - GAP + 46


def color_for(level: int) -> str:
    return PALETTE[level] if level < len(PALETTE) else PALETTE[-1]


def fmt_count(n: int) -> str:
    return f"{n:,}"


def font(size: int):
    for name in ("segoeui.ttc", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_frame(img, draw, cell_map, months, total, stats, cutoff: int):
    """cutoff: only cells with (ix+row) <= cutoff are drawn (reveal sweep)."""
    def cx(c): return PAD_X + c * (CELL + GAP)
    def cy(r): return HEADER_H + r * (CELL + GAP)

    for m, ix in months.items():
        draw.text((cx(ix) + CELL / 2, HEADER_H - 8), m,
                  font=font(10), fill="#8b949e", anchor="ms")
    for r, lab in [(2, "Wed"), (4, "Fri")]:
        draw.text((cx(0) - 5, cy(r) + CELL + 2), lab,
                  font=font(9), fill="#8b949e", anchor="ms")

    for ix in range(WEEKS):
        for row in range(DAYS):
            if (ix + row) > cutoff:
                continue
            day = cell_map.get((ix, row))
            if day is None:
                continue
            draw.rounded_rectangle(
                [cx(ix), cy(row), cx(ix) + CELL, cy(row) + CELL],
                radius=3, fill=color_for(day["level"]), outline=color_for(day["level"])
            )

    fy_title = HEIGHT - 28
    draw.text((PAD_X, fy_title), f"{fmt_count(total)} contributions in the last year",
              font=font(13), fill="#e6edf3")
    draw.text(
        (PAD_X, fy_title + 16),
        f"Best day: {fmt_count(stats['best_day']['count'])}  |  "
        f"Longest streak: {stats['longest_streak']} days  |  "
        f"Current streak: {stats['current_streak']} days",
        font=font(10), fill="#8b949e",
    )

    legend_y = fy_title + 30
    draw.text((PAD_X, legend_y), "Less", font=font(9), fill="#8b949e", anchor="lm")
    for i, c in enumerate(PALETTE[1:]):
        draw.rounded_rectangle(
            [PAD_X + 30 + i * (CELL + 3), legend_y - 5, PAD_X + 30 + i * (CELL + 3) + CELL, legend_y + 6],
            radius=3, fill=c, outline=c,
        )
    draw.text((PAD_X + 30 + 5 * (CELL + 3) + 4, legend_y), "More",
              font=font(9), fill="#8b949e", anchor="lm")


def main() -> None:
    with open(INPUT, encoding="utf-8") as fh:
        data = json.load(fh)
    days, stats = data["days"], data["stats"]

    cell_map = {}
    for day in days:
        col = day["ix"]
        row = datetime.strptime(day["date"], "%Y-%m-%d").weekday()
        cell_map[(col, row)] = day

    months = {}
    for day in days:
        m = day["date"][:7]
        if m not in months:
            months[m] = day["ix"]

    max_cutoff = WEEKS + DAYS
    step = 3
    frames = []
    for cutoff in range(0, max_cutoff + 1, step):
        img = Image.new("RGBA", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)
        build_frame(img, draw, cell_map, months, stats["total"], stats, cutoff)
        frames.append(img)

    # hold the completed grid for a couple seconds
    final = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    build_frame(final, ImageDraw.Draw(final), cell_map, months, stats["total"], stats, max_cutoff + 1)
    frames.append(final)
    frames.append(final)

    # GIF: palette + duration ~30ms/frame reveal, longer hold on final
    first = frames[0].convert("P", palette=Image.ADAPTIVE, colors=64)
    others = [f.convert("P", palette=first.getpalette()) for f in frames[1:]]
    durations = [28] * (len(frames) - 2) + [1600, 1600]
    first.save(
        OUTPUT, save_all=True, append_images=others,
        duration=durations, loop=1, disposal=2,
    )
    print(f"Wrote {OUTPUT} ({len(frames)} frames, {stats['total']} contributions)")


if __name__ == "__main__":
    main()