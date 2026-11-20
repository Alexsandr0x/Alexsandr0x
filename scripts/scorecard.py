#!/usr/bin/env python3
"""Gera o scorecard HUD (alexsandro.dev) a partir da API do GitHub.

Uso:  GH_PAT=<token> python3 scorecard.py   (imprime o SVG em stdout)
"""

import datetime as _dt
import json
import os
import sys
import urllib.request

TOKEN = os.environ.get("GH_PAT", "").strip()
API = "https://api.github.com"
USER = "Alexsandr0x"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "alexsandro-scorecard",
}
if TOKEN:
    HEADERS["Authorization"] = "Bearer " + TOKEN

# Nome detectado pelo linguist -> rótulo final. None = ignora (markup/config/glue).
ALIAS = {
    "HTML": None,
    "CSS": None,
    "SCSS": None,
    "Sass": None,
    "Less": None,
    "Markdown": None,
    "YAML": None,
    "JSON": None,
    "JSON5": None,
    "TOML": None,
    "CSV": None,
    "Text": None,
    "SVG": None,
    "XML": None,
    "Dockerfile": None,
    "Makefile": None,
    "CMake": None,
    "Batchfile": None,
    "PowerShell": None,
    "Go Template": None,
    "Mako": None,
    "Jinja": None,
    "Gherkin": None,
    "Procfile": None,
    "Ignore List": None,
    # aliases
    "Jupyter Notebook": "Python",
    "PLpgSQL": "SQL",
    "TSQL": "SQL",
    "SQLPL": "SQL",
    "HCL": "Terraform",
}

COLORS = {
    "Python": "#3572A5",
    "Java": "#b07219",
    "Terraform": "#844FBA",
    "SQL": "#336790",
    "Shell": "#89e051",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "C++": "#f34b7d",
    "C": "#555555",
    "C#": "#178600",
    "Ruby": "#701516",
    "Kotlin": "#A97BFF",
    "Scala": "#c22d40",
    "Elixir": "#6e4a7e",
    "Clojure": "#db5855",
    "R": "#198CE7",
    "Lua": "#000080",
    "Dart": "#00B4AB",
}
FALLBACK_COLOR = "#8a979c"


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _paginate(path, pages=4):
    items = []
    for page in range(1, pages + 1):
        sep = "&" if "?" in path else "?"
        batch = _get(f"{API}{path}{sep}per_page=100&page={page}")
        items.extend(batch)
        if len(batch) < 100:
            break
    return items


def _graphql(query):
    req = urllib.request.Request(
        API + "/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def collect():
    user = _get(f"{API}/users/{USER}")
    repos = _paginate(f"/users/{USER}/repos", pages=3)
    stars = sum(r.get("stargazers_count", 0) for r in repos)

    contrib = 0
    if TOKEN:
        try:
            data = _graphql(
                '{ user(login: "%s") { '
                "contributionsCollection { contributionCalendar { totalContributions } } } }"
                % USER
            )
            contrib = data["data"]["user"]["contributionsCollection"][
                "contributionCalendar"
            ]["totalContributions"]
        except Exception:
            contrib = 0

    events = _paginate(f"/users/{USER}/events", pages=3)
    if TOKEN:
        try:
            events += _paginate(f"/users/{USER}/events/private", pages=3)
        except Exception:
            pass

    seen = set()
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=30)
    pushes = {}
    for e in events:
        eid = e.get("id")
        if eid in seen:
            continue
        seen.add(eid)
        if e.get("type") != "PushEvent":
            continue
        try:
            when = _dt.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        if when < cutoff:
            continue
        pushes[e["repo"]["name"]] = pushes.get(e["repo"]["name"], 0) + 1

    lang_weight = {}
    for repo, weight in pushes.items():
        try:
            sizes = _get(f"{API}/repos/{repo}/languages")
        except Exception:
            continue
        total = sum(sizes.values())
        if not total:
            continue
        for name, size in sizes.items():
            key = ALIAS.get(name, name)
            if key is None:
                continue
            lang_weight[key] = lang_weight.get(key, 0.0) + (size / total) * weight

    return {
        "repos": user["public_repos"],
        "stars": stars,
        "followers": user["followers"],
        "contrib": contrib,
        "since": user["created_at"][:4],
        "langs": lang_weight,
    }


def _row(x_dot, y, name, color, pct, barw):
    label = name[:12]
    return (
        f'    <rect x="{x_dot}" y="{y + 1}" width="6" height="6" fill="{color}"/>\n'
        f'    <text x="{x_dot + 16}" y="{y + 10}" fill="#ece6d8">{label}</text>\n'
        f'    <rect x="890" y="{y}" width="{barw}" height="6" fill="{color}"/>\n'
        f'    <text x="1140" y="{y + 10}" text-anchor="end" font-size="12" fill="#8a979c">{pct}%</text>\n'
    )


def render(data):
    top = sorted(data["langs"].items(), key=lambda kv: -kv[1])[:5]
    total = sum(v for _, v in top) or 1.0
    maxv = top[0][1] if top else 1.0

    rows = []
    ys = [100, 116, 132, 148, 164]
    tracks = "".join(
        f'    <rect x="890" y="{y}" width="160" height="6" fill="#26343c"/>\n'
        for y in ys
    )
    for i, y in enumerate(ys):
        if i < len(top):
            name, val = top[i]
            color = COLORS.get(name, FALLBACK_COLOR)
            pct = round(val / total * 100)
            barw = max(2, round(val / maxv * 160)) if val > 0 else 0
            rows.append(_row(770, y, name, color, pct, barw))
        else:
            rows.append(f'    <rect x="770" y="{y + 1}" width="6" height="6" fill="#26343c"/>\n')

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="200" viewBox="0 0 1180 200" font-family="Chakra Petch, Rajdhani, 'Segoe UI', system-ui, sans-serif" role="img" aria-label="Alexsandro — perfil GitHub">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#121a1f"/>
      <stop offset="1" stop-color="#0d1519"/>
    </linearGradient>
  </defs>

  <path d="M0 0 L1164 0 L1180 16 L1180 200 L0 200 Z" fill="url(#bg)" stroke="#26343c" stroke-width="1"/>
  <line x1="1164" y1="0" x2="1180" y2="16" stroke="#ffb000" stroke-width="1.5"/>

  <g stroke="#46d9e8" stroke-width="1.5" fill="none" opacity="0.85">
    <path d="M13 13 h20 M13 13 v20"/>
    <path d="M13 187 h20 M13 187 v-20"/>
    <path d="M1167 187 h-20 M1167 187 v-20"/>
  </g>

  <line x1="44" y1="18" x2="1136" y2="18" stroke="#8a979c" stroke-width="10" stroke-dasharray="1 12" opacity="0.28"/>
  <line x1="44" y1="18" x2="1136" y2="18" stroke="#46d9e8" stroke-width="10" stroke-dasharray="1 59" opacity="0.5"/>

  <text x="44" y="44" font-size="21" font-weight="700" fill="#ece6d8">alexsandro<tspan fill="#ffb000">.dev</tspan></text>

  <g fill="#46d9e8" opacity="0.9">
    <rect x="980" y="30" width="3" height="6"/>
    <rect x="988" y="26" width="3" height="10"/>
    <rect x="996" y="28" width="3" height="8"/>
    <rect x="1004" y="24" width="3" height="12"/>
  </g>
  <text x="1136" y="40" text-anchor="end" font-size="12" letter-spacing="2" fill="#8a979c" font-weight="600">SYS.ONLINE</text>

  <g stroke="#26343c" stroke-width="1">
    <line x1="140" y1="96" x2="140" y2="150"/>
    <line x1="340" y1="96" x2="340" y2="150"/>
    <line x1="540" y1="96" x2="540" y2="150"/>
    <line x1="740" y1="82" x2="740" y2="176"/>
  </g>

  <g font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-weight="700" font-size="44" fill="#ffb000">
    <text x="40" y="126">{data['repos']}</text>
    <text x="240" y="126">{data['stars']}</text>
    <text x="440" y="126">{data['followers']}</text>
    <text x="640" y="126">{data['contrib']}</text>
  </g>

  <g font-size="12" letter-spacing="2" font-weight="600" fill="#8a979c">
    <text x="40" y="156">REPOS</text>
    <text x="240" y="156">STARS</text>
    <text x="440" y="156">FOLLOWERS</text>
    <text x="640" y="156">CONTRIBS</text>
  </g>

  <text x="770" y="84" font-size="11" letter-spacing="2" font-weight="600" fill="#8a979c">LINGUAGENS · 30D</text>

  <g font-family="JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">
{tracks}  </g>

  <g font-size="13">
{''.join(rows)}  </g>

  <rect x="40" y="179" width="7" height="7" fill="#46d9e8"/>
  <text x="54" y="186" font-size="11" letter-spacing="2" font-weight="600" fill="#8a979c">SINCE {data['since']}</text>
  <text x="1136" y="186" text-anchor="end" font-size="11" letter-spacing="1" fill="#8a979c">github.com/{USER}</text>
</svg>
"""
    return svg


def main():
    data = collect()
    sys.stdout.write(render(data))


if __name__ == "__main__":
    main()
