#!/usr/bin/env python3
"""Generate assets/stats.svg: a clean GitHub stats + streak card.

Uses only the Python standard library and the GitHub GraphQL API.
If anything fails, the script exits with an error and leaves the
existing card untouched.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "faizanshafi25")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT", "assets/stats.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

# ---------------------------------------------------------------- data


def compute_streaks(days):
    """days: iterable of (iso_date, count).

    Returns (current, longest, longest_start, longest_end).
    A day with no contribution yet today does not break the current streak.
    """
    days = sorted(days)
    longest = run = 0
    run_start = None
    best = (None, None)
    for date, count in days:
        if count > 0:
            if run == 0:
                run_start = date
            run += 1
            if run > longest:
                longest, best = run, (run_start, date)
        else:
            run = 0

    current = 0
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1
    while i >= 0 and days[i][1] > 0:
        current += 1
        i -= 1
    return current, longest, best[0], best[1]


def request_json(payload, attempts=3):
    last = None
    for n in range(attempts):
        try:
            req = urllib.request.Request(
                "https://api.github.com/graphql",
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"bearer {TOKEN}",
                    "Content-Type": "application/json",
                    "User-Agent": "profile-stats-card",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(2 * (n + 1))
    raise SystemExit(f"Could not reach the GitHub API: {last}")


def fetch_stats():
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN is not set.")
    data = request_json({"query": QUERY, "variables": {"login": USER}})
    user = (data.get("data") or {}).get("user")
    if "errors" in data or not user:
        raise SystemExit(f"GitHub API error: {data.get('errors', data)}")

    coll = user["contributionsCollection"]
    cal = coll["contributionCalendar"]
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    days = [
        (d["date"], d["contributionCount"])
        for week in cal["weeks"]
        for d in week["contributionDays"]
        if d["date"] <= today
    ]
    current, longest, start, end = compute_streaks(days)
    return {
        "contributions": cal["totalContributions"],
        "commits": coll["totalCommitContributions"],
        "pull_requests": coll["totalPullRequestContributions"],
        "repos": user["repositories"]["totalCount"],
        "current": current,
        "longest": longest,
        "longest_range": (start, end),
    }


def demo_stats(kind):
    """Local previews only: MOCK=demo or MOCK=blank."""
    if kind == "blank":
        return {k: "-" for k in
                ("contributions", "commits", "pull_requests", "repos", "current", "longest")} | {
                    "longest_range": (None, None)}
    base = dt.date(2026, 11, 2)
    counts = [3, 1, 0, 2, 5, 4, 1, 0, 0, 2, 1, 1, 6, 2]
    days = [((base - dt.timedelta(days=len(counts) - 1 - i)).isoformat(), n)
            for i, n in enumerate(counts)]
    current, longest, start, end = compute_streaks(days)
    return {"contributions": 45, "commits": 31, "pull_requests": 2, "repos": 3,
            "current": current, "longest": longest, "longest_range": (start, end)}

# ------------------------------------------------------------- rendering

SANS = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
BG, BORDER, TILE = "#0B1120", "#123B55", "#0E2A40"
CYAN, TEXT, MUTED, DIM = "#38BDF8", "#E2F3FF", "#94A3B8", "#64748B"


def short_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.strftime('%b')} {d.day}"


def days_label(n):
    if n == "-":
        return "-"
    return f"{n} day" if n == 1 else f"{n} days"


def tile(col, row, label, value, note=""):
    x = 40 + col * 192
    y = 78 + row * 100
    note_svg = (
        f'<text x="{x + 20}" y="{y + 77}" font-family="{SANS}" font-size="12" fill="{DIM}">{escape(note)}</text>'
        if note else ""
    )
    return (
        f'  <rect x="{x}" y="{y}" width="176" height="88" rx="12" fill="{TILE}" fill-opacity="0.6" stroke="{BORDER}"/>\n'
        f'  <text x="{x + 20}" y="{y + 28}" font-family="{SANS}" font-size="14" fill="{MUTED}">{escape(label)}</text>\n'
        f'  <text x="{x + 20}" y="{y + 58}" font-family="{SANS}" font-size="32" font-weight="700" fill="{CYAN}">{escape(str(value))}</text>\n'
        f'  {note_svg}\n'
    )


def render(s):
    start, end = s["longest_range"]
    if start and end:
        note = short_date(start) if start == end else f"{short_date(start)} - {short_date(end)}"
    else:
        note = ""
    tiles = "".join([
        tile(0, 0, "Contributions", s["contributions"]),
        tile(1, 0, "Commits", s["commits"]),
        tile(2, 0, "Pull requests", s["pull_requests"]),
        tile(0, 1, "Public repositories", s["repos"]),
        tile(1, 1, "Current streak", days_label(s["current"])),
        tile(2, 1, "Longest streak", days_label(s["longest"]), note),
    ])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 320" role="img" aria-label="GitHub stats and streaks for {escape(USER)}">
  <defs>
    <linearGradient id="bar" x1="0" x2="1"><stop offset="0" stop-color="#0E7490"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>
    <clipPath id="c"><rect x="1.5" y="1.5" width="637" height="317" rx="16"/></clipPath>
  </defs>
  <rect x="1.5" y="1.5" width="637" height="317" rx="16" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>
  <g clip-path="url(#c)"><rect x="0" y="0" width="640" height="6" fill="url(#bar)"/></g>
  <text x="40" y="50" font-family="{SANS}" font-size="22" font-weight="700" fill="{TEXT}">GitHub activity</text>
  <text x="600" y="50" text-anchor="end" font-family="{SANS}" font-size="14" fill="{MUTED}">@{escape(USER)} · last 12 months</text>
{tiles}  <text x="40" y="296" font-family="{SANS}" font-size="12" fill="{DIM}">Source: GitHub contribution data. Updated daily.</text>
</svg>
'''

# ------------------------------------------------------------------ main


def main():
    mock = os.environ.get("MOCK")
    stats = demo_stats(mock) if mock else fetch_stats()
    svg = render(stats)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print("Wrote", OUT, stats)


if __name__ == "__main__":
    sys.exit(main())
