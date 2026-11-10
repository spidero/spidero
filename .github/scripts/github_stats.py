#!/usr/bin/env python3
"""Generate a simple GitHub stats card (SVG, light + dark) using only the stdlib.

Usage: GITHUB_TOKEN=... python3 github_stats.py <login> <output_dir>
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

API = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $from: DateTime!, $cursor: String) {
  user(login: $login) {
    name
    login
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(
      first: 1
      contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, PULL_REQUEST_REVIEW]
    ) { totalCount }
    thisYear: contributionsCollection(from: $from) { totalCommitContributions }
    lastYear: contributionsCollection {
      contributionCalendar { totalContributions }
    }
    repositories(
      first: 100, after: $cursor, ownerAffiliations: OWNER,
      isFork: false, privacy: PUBLIC
    ) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { stargazerCount forkCount }
    }
  }
}
"""

THEMES = {
    "light": {
        "bg": "#ffffff", "border": "#d0d7de", "title": "#0969da",
        "label": "#57606a", "value": "#1f2328", "accent": "#0969da",
        "track": "#d8e6f8",
    },
    "dark": {
        "bg": "#0d1117", "border": "#30363d", "title": "#58a6ff",
        "label": "#8b949e", "value": "#e6edf3", "accent": "#58a6ff",
        "track": "#1c2a3d",
    },
}


def graphql(token, variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-card",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def fetch_stats(token, login):
    year = dt.datetime.now(dt.timezone.utc).year
    variables = {"login": login, "from": f"{year}-01-01T00:00:00Z", "cursor": None}
    stars = forks = 0
    while True:
        user = graphql(token, variables)
        repos = user["repositories"]
        stars += sum(r["stargazerCount"] for r in repos["nodes"])
        forks += sum(r["forkCount"] for r in repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        variables["cursor"] = repos["pageInfo"]["endCursor"]
    return {
        "name": user["name"] or user["login"],
        "year": year,
        "stars": stars,
        "forks": forks,
        "repos": repos["totalCount"],
        "commits": user["thisYear"]["totalCommitContributions"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "contributions": user["lastYear"]["contributionCalendar"]["totalContributions"],
    }


def human(n):
    for div, suffix in ((1_000_000, "M"), (1_000, "k")):
        if n >= div:
            return f"{n / div:.1f}".rstrip("0").rstrip(".") + suffix
    return str(n)


def render(s, theme):
    c = THEMES[theme]
    rows = [
        ("Total stars", s["stars"]),
        (f"Commits ({s['year']})", s["commits"]),
        ("Pull requests", s["prs"]),
        ("Issues", s["issues"]),
        ("Contributed to (last year)", s["contributed"]),
        ("Public repos", s["repos"]),
    ]
    font = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
    lines = []
    for i, (label, value) in enumerate(rows):
        y = 70 + i * 22
        lines.append(
            f'<g class="row" style="animation-delay:{150 + i * 120}ms">'
            f'<rect x="25" y="{y - 9}" width="8" height="8" rx="2" fill="{c["accent"]}"/>'
            f'<text x="43" y="{y}" class="label">{escape(label)}:</text>'
            f'<text x="235" y="{y}" class="value">{human(value)}</text></g>'
        )
    # Ring: decorative full circle with yearly contributions in the middle
    cx, cy, r = 400, 112, 50
    circ = 2 * 3.14159 * r
    title = escape(f"{s['name']}'s GitHub Stats")
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="210" viewBox="0 0 495 210" role="img" aria-label="{title}">
<title>{title}</title>
<style>
  .title {{ font: 600 18px {font}; fill: {c["title"]}; }}
  .label {{ font: 600 13px {font}; fill: {c["label"]}; }}
  .value {{ font: 700 13px {font}; fill: {c["value"]}; }}
  .big {{ font: 700 22px {font}; fill: {c["value"]}; }}
  .small {{ font: 400 10px {font}; fill: {c["label"]}; }}
  .row {{ opacity: 0; animation: fade .5s ease-in-out forwards; }}
  .ring {{ stroke-dasharray: {circ:.1f}; stroke-dashoffset: {circ:.1f}; animation: draw 1.2s ease-out forwards; }}
  @keyframes fade {{ to {{ opacity: 1; }} }}
  @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
</style>
<rect x="0.5" y="0.5" width="494" height="209" rx="6" fill="{c["bg"]}" stroke="{c["border"]}"/>
<text x="25" y="35" class="title">{title}</text>
{''.join(lines)}
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{c["track"]}" stroke-width="8"/>
<circle class="ring" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{c["accent"]}" stroke-width="8" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>
<text x="{cx}" y="{cy + 4}" text-anchor="middle" class="big">{s["contributions"] if s["contributions"] < 10000 else human(s["contributions"])}</text>
<text x="{cx}" y="{cy + 20}" text-anchor="middle" class="small">contributions</text>
<text x="{cx}" y="{cy + 32}" text-anchor="middle" class="small">last year</text>
<text x="470" y="200" text-anchor="end" class="small">updated {updated}</text>
</svg>
"""


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    login, out_dir = sys.argv[1], sys.argv[2]
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")
    stats = fetch_stats(token, login)
    print(json.dumps(stats, indent=2))
    os.makedirs(out_dir, exist_ok=True)
    for theme, suffix in (("light", ""), ("dark", "-dark")):
        path = os.path.join(out_dir, f"github-stats{suffix}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render(stats, theme))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
