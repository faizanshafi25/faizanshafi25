"""Generate assets/stats.svg (stats + streaks) from the GitHub GraphQL API.
Standard library only."""
import datetime as dt
import json
import os
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


def streaks(days):
    """days: list of (date, count). Returns (current, longest, longest_start, longest_end)."""
    days = sorted(days)
    longest = run = 0
    run_start = None
    best = (None, None)
    for d, n in days:
        if n > 0:
            if run == 0:
                run_start = d
            run += 1
            if run > longest:
                longest, best = run, (run_start, d)
        else:
            run = 0
    # Current streak: today may still be empty, so then it counts from yesterday.
    current = 0
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1
    while i >= 0 and days[i][1] > 0:
        current += 1
        i -= 1
    return current, longest, best[0], best[1]


def build(total, commits, prs, repos, days):
    cur, lon, ls, le = streaks(days)
    return {"total": total, "commits": commits, "prs": prs, "repos": repos,
            "current": cur, "longest": lon, "longest_start": ls, "longest_end": le}


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload or not payload.get("data", {}).get("user"):
        raise SystemExit(f"GitHub API error: {payload.get('errors', payload)}")
    u = payload["data"]["user"]
    c = u["contributionsCollection"]
    cal = c["contributionCalendar"]
    days = [(d["date"], d["contributionCount"])
            for w in cal["weeks"] for d in w["contributionDays"]]
    # Drop future days in the last (partial) week, if any.
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    days = [x for x in days if x[0] <= today]
    return build(cal["totalContributions"], c["totalCommitContributions"],
                 c["totalPullRequestContributions"], u["repositories"]["totalCount"], days)


def mock():
    if os.environ["MOCK"] == "blank":
        return {k: "-" for k in ["total", "commits", "prs", "repos", "current", "longest"]} | \
               {"longest_start": None, "longest_end": None}
    base = dt.date(2026, 11, 2)
    counts = [3, 1, 0, 2, 5, 4, 1, 0, 0, 2, 1, 1, 6, 2]  # newest last
    days = [((base - dt.timedelta(days=len(counts) - 1 - i)).isoformat(), n) for i, n in enumerate(counts)]
    return build(45, 31, 2, 3, days)


def fmt_day(s):
    d = dt.date.fromisoformat(s)
    return f"{d.strftime('%b')} {d.day}"


def render(s):
    SANS = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
    top = [("Contributions", s["total"]), ("Commits", s["commits"]),
           ("Pull requests", s["prs"]), ("Public repos", s["repos"])]
    out = []
    for i, (label, value) in enumerate(top):
        x = 40 + i * 142
        out.append(
            f'  <rect x="{x}" y="76" width="130" height="86" rx="12" fill="#0E2A40" fill-opacity="0.55" stroke="#123B55"/>\n'
            f'  <text x="{x+65}" y="119" text-anchor="middle" font-family="{SANS}" font-size="36" font-weight="700" fill="#38BDF8">{escape(str(value))}</text>\n'
            f'  <text x="{x+65}" y="147" text-anchor="middle" font-family="{SANS}" font-size="15" fill="#94A3B8">{escape(label)}</text>\n')

    def unit(n):
        return "-" if n == "-" else f"{n} {'day' if n == 1 else 'days'}"

    cur_sub = "Days in a row with a contribution"
    if s["longest_start"]:
        lon_sub = (fmt_day(s["longest_start"]) if s["longest_start"] == s["longest_end"]
                   else f'{fmt_day(s["longest_start"])} - {fmt_day(s["longest_end"])}')
    else:
        lon_sub = "Best run in the last 12 months"
    for x, label, value, sub, accent in [
        (40, "Current streak", unit(s["current"]), cur_sub, "#F59E0B"),
        (326, "Longest streak", unit(s["longest"]), lon_sub, "#38BDF8")]:
        out.append(
            f'  <rect x="{x}" y="174" width="274" height="92" rx="12" fill="#0E2A40" fill-opacity="0.55" stroke="#123B55"/>\n'
            f'  <rect x="{x}" y="174" width="5" height="92" rx="2.5" fill="{accent}"/>\n'
            f'  <text x="{x+26}" y="206" font-family="{SANS}" font-size="15" fill="#94A3B8">{escape(label)}</text>\n'
            f'  <text x="{x+26}" y="240" font-family="{SANS}" font-size="32" font-weight="700" fill="{accent}">{escape(value)}</text>\n'
            f'  <text x="{x+26}" y="258" font-family="{SANS}" font-size="12" fill="#64748B">{escape(sub)}</text>\n')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 316" role="img" aria-label="GitHub stats and streaks for {escape(USER)}">
  <defs>
    <linearGradient id="bar" x1="0" x2="1"><stop offset="0" stop-color="#0E7490"/><stop offset="1" stop-color="#38BDF8"/></linearGradient>
    <clipPath id="c"><rect x="1.5" y="1.5" width="637" height="313" rx="16"/></clipPath>
  </defs>
  <rect x="1.5" y="1.5" width="637" height="313" rx="16" fill="#0B1120" stroke="#123B55" stroke-width="2"/>
  <g clip-path="url(#c)"><rect x="0" y="0" width="640" height="6" fill="url(#bar)"/></g>
  <text x="40" y="50" font-family="{SANS}" font-size="22" font-weight="700" fill="#E2F3FF">GitHub stats</text>
  <text x="600" y="50" text-anchor="end" font-family="{SANS}" font-size="15" fill="#94A3B8">last 12 months · updated daily</text>
{"".join(out)}  <text x="40" y="293" font-family="{SANS}" font-size="13" fill="#64748B">Source: GitHub contribution data for @{escape(USER)}</text>
</svg>
'''


if __name__ == "__main__":
    stats = mock() if os.environ.get("MOCK") else fetch()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(stats))
    print("wrote", OUT, stats)
