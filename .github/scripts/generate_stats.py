"""Generate assets/stats.svg from the GitHub GraphQL API (standard library only)."""
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
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""

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
    return [
        ("Contributions", c["contributionCalendar"]["totalContributions"]),
        ("Commits", c["totalCommitContributions"]),
        ("Pull requests", c["totalPullRequestContributions"]),
        ("Public repos", u["repositories"]["totalCount"]),
    ]

def mock():
    # Used only for local preview: MOCK=demo (sample numbers) or MOCK=blank (dashes)
    if os.environ["MOCK"] == "demo":
        vals = [45, 31, 2, 3]
    else:
        vals = ["-", "-", "-", "-"]
    return list(zip(["Contributions", "Commits", "Pull requests", "Public repos"], vals))

def render(stats):
    SANS = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
    tiles = []
    for i, (label, value) in enumerate(stats):
        x = 40 + i * 142
        tiles.append(
            f'  <rect x="{x}" y="78" width="130" height="92" rx="12" fill="#0E2A40" fill-opacity="0.55" stroke="#123B55"/>\n'
            f'  <text x="{x+65}" y="125" text-anchor="middle" font-family="{SANS}" font-size="38" font-weight="700" fill="#38BDF8">{escape(str(value))}</text>\n'
            f'  <text x="{x+65}" y="153" text-anchor="middle" font-family="{SANS}" font-size="15" fill="#94A3B8">{escape(label)}</text>\n'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 220" role="img" aria-label="GitHub stats for {escape(USER)}">
  <defs>
    <linearGradient id="bar" x1="0" x2="1"><stop offset="0" stop-color="#0E7490"/><stop offset="1" stop-color="#38BDF8"/></linearGradient>
    <clipPath id="c"><rect x="1.5" y="1.5" width="637" height="217" rx="16"/></clipPath>
  </defs>
  <rect x="1.5" y="1.5" width="637" height="217" rx="16" fill="#0B1120" stroke="#123B55" stroke-width="2"/>
  <g clip-path="url(#c)"><rect x="0" y="0" width="640" height="6" fill="url(#bar)"/></g>
  <text x="40" y="52" font-family="{SANS}" font-size="22" font-weight="700" fill="#E2F3FF">GitHub stats</text>
  <text x="600" y="52" text-anchor="end" font-family="{SANS}" font-size="15" fill="#94A3B8">last 12 months · updated daily</text>
{"".join(tiles)}  <text x="40" y="198" font-family="{SANS}" font-size="13" fill="#64748B">Counts what GitHub reports for @{escape(USER)}</text>
</svg>
'''

if __name__ == "__main__":
    stats = mock() if os.environ.get("MOCK") else fetch()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(stats))
    print("wrote", OUT, stats)
