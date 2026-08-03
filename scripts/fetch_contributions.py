#!/usr/bin/env python3
"""Fetch a GitHub user's contribution calendar (no token needed).

GitHub serves the contribution calendar as public HTML at:
    https://github.com/users/<username>/contributions
Parse the day cells and write data/contributions.json with raw days plus
derived stats (current streak, longest streak, best day, monthly totals).
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

USERNAME = sys.argv[1] if len(sys.argv) > 1 else "UnfilteredAnshul"
OUT_FILE = os.path.join("data", "contributions.json")
URL = f"https://github.com/users/{USERNAME}/contributions"

DAY = timedelta(days=1)


def fetch_days() -> list[dict]:
    resp = requests.get(URL, headers={"User-Agent": "contrib-heatmap/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cells = soup.select("td.ContributionCalendar-day[data-date]")
    tips = {t["for"]: t.get_text(" ", strip=True) for t in soup.select("tool-tip[for]")}

    days = []
    for cell in cells:
        tip_text = tips.get(cell.get("id"), "")
        match = re.search(r"(\d+) contributions?", tip_text)
        days.append({
            "ix": int(cell.get("data-ix") or 0),
            "date": cell.get("data-date"),
            "level": int(cell.get("data-level") or 0),
            "count": int(match.group(1)) if match else 0,
        })
    return days


def current_streak(active: set[str]) -> int:
    if not active:
        return 0
    cursor = max(datetime.strptime(d, "%Y-%m-%d") for d in active)
    streak = 0
    while cursor.strftime("%Y-%m-%d") in active:
        streak += 1
        cursor -= DAY
    return streak


def longest_streak(active: set[str]) -> int:
    if not active:
        return 0
    ordered = sorted(active)
    longest = cur = 1
    for prev, nxt in zip(ordered, ordered[1:]):
        if (datetime.strptime(nxt, "%Y-%m-%d") - datetime.strptime(prev, "%Y-%m-%d")).days == 1:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 1
    return longest


def compute_stats(days: list[dict]) -> dict:
    active = {d["date"] for d in days if d["count"] > 0}
    best = max(days, key=lambda d: d["count"])
    monthly: dict[str, int] = {}
    for d in days:
        monthly[d["date"][:7]] = monthly.get(d["date"][:7], 0) + d["count"]
    return {
        "total": sum(d["count"] for d in days),
        "current_streak": current_streak(active),
        "longest_streak": longest_streak(active),
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly_totals": dict(sorted(monthly.items())),
    }


def main() -> None:
    days = fetch_days()
    stats = compute_stats(days)
    os.makedirs("data", exist_ok=True)
    payload = {"username": USERNAME, "stats": stats, "days": days}
    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"Wrote {len(days)} days -> {OUT_FILE} ({stats['total']} contributions)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        USERNAME = sys.argv[1]
        URL = f"https://github.com/users/{USERNAME}/contributions"
        OUT_FILE = os.path.join("data", "contributions.json")
    main()