#!/usr/bin/env python3
"""Gera os cards HUD do perfil (stats + atividade) direto da API do GitHub.

Uso:
  GITHUB_TOKEN=... python3 scripts/hud_cards.py Cookie131223 dist
  python3 scripts/hud_cards.py --sample dist      # dados falsos, para testar o visual
"""
import datetime as dt
import json
import os
import random
import sys
import urllib.request
from collections import defaultdict
from xml.sax.saxutils import escape

GOLD = "#FFD700"
RED = "#C62828"
DARK_RED = "#8B0000"
TEXT = "#C9D1D9"
MUTED = "#8B949E"
FONT = "'Fira Code','JetBrains Mono',Consolas,'Courier New',monospace"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday contributionLevel } }
      }
    }
  }
}
"""


# ---------------------------------------------------------------- data
def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "hud-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    u = payload["data"]["user"]
    cc = u["contributionsCollection"]
    langs = defaultdict(int)
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] += e["size"]
    return {
        "repos": u["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "followers": u["followers"]["totalCount"],
        "commits": cc["totalCommitContributions"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "total": cc["contributionCalendar"]["totalContributions"],
        "weeks": [w["contributionDays"] for w in cc["contributionCalendar"]["weeks"]],
        "langs": dict(langs),
    }


def sample():
    levels = ["NONE"] * 8 + ["FIRST_QUARTILE"] * 3 + ["SECOND_QUARTILE"] * 2 + ["THIRD_QUARTILE", "FOURTH_QUARTILE"]
    start = dt.date.today() - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)  # domingo
    weeks, d = [], start
    while d <= dt.date.today():
        week = []
        for _ in range(7):
            if d > dt.date.today():
                break
            lv = random.choice(levels)
            week.append({"date": d.isoformat(), "weekday": (d.weekday() + 1) % 7,
                         "contributionLevel": lv,
                         "contributionCount": 0 if lv == "NONE" else random.randint(1, 9)})
            d += dt.timedelta(days=1)
        weeks.append(week)
    return {"repos": 8, "stars": 3, "followers": 5, "commits": 214, "prs": 6, "issues": 2,
            "total": sum(x["contributionCount"] for w in weeks for x in w), "weeks": weeks,
            "langs": {"JavaScript": 52000, "PHP": 30000, "CSS": 18000, "HTML": 12000, "C": 4000, "Python": 2500}}


# ---------------------------------------------------------------- shared svg bits
def frame(w, h, title, right_text=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="{FONT}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#140608"/><stop offset="100%" stop-color="#0d1117"/>
    </linearGradient>
    <linearGradient id="bar" x1="0" x2="1">
      <stop offset="0%" stop-color="{DARK_RED}"/><stop offset="100%" stop-color="{GOLD}"/>
    </linearGradient>
    <linearGradient id="beam" x1="0" x2="1">
      <stop offset="0%" stop-color="{GOLD}" stop-opacity="0"/><stop offset="100%" stop-color="{GOLD}" stop-opacity="0.35"/>
    </linearGradient>
    <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
      <path d="M24 0H0V24" fill="none" stroke="{GOLD}" stroke-opacity="0.05"/>
    </pattern>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect width="{w}" height="{h}" rx="14" fill="url(#bg)"/>
  <rect width="{w}" height="{h}" rx="14" fill="url(#grid)"/>
  <rect x="1" y="1" width="{w-2}" height="{h-2}" rx="14" fill="none" stroke="{DARK_RED}" stroke-opacity="0.7"/>
  <g stroke="{GOLD}" stroke-width="3" fill="none" stroke-linecap="round">
    <path d="M16 40V16H40"/><path d="M{w-40} 16H{w-16}V40"/>
    <path d="M16 {h-40}V{h-16}H40"/><path d="M{w-40} {h-16}H{w-16}V{h-40}"/>
  </g>
  <text x="40" y="46" fill="{GOLD}" font-size="15" letter-spacing="3" font-weight="700">◢ {escape(title)}</text>
  <text x="{w-40}" y="46" fill="{MUTED}" font-size="12" letter-spacing="2" text-anchor="end">{escape(right_text)}</text>
"""


def fmt(n):
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


# ---------------------------------------------------------------- stats card
def stats_svg(d):
    w, h = 1000, 270
    today = dt.date.today().strftime("%d.%m.%Y")
    out = [frame(w, h, "SYSTEM DIAGNOSTICS", f"SCAN {today}")]

    metrics = [("CONTRIBUTIONS", d["total"], "last 12 months"), ("COMMITS", d["commits"], "last 12 months"),
               ("PUBLIC REPOS", d["repos"], "owned"), ("PULL REQUESTS", d["prs"], "last 12 months"),
               ("STARS", d["stars"], "earned"), ("FOLLOWERS", d["followers"], "allies")]
    for i, (label, value, sub) in enumerate(metrics):
        col, row = i % 3, i // 3
        x, y = 40 + col * 150, 84 + row * 82
        delay = 0.15 * i
        out.append(f"""  <g opacity="0">
    <animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.6s" fill="freeze"/>
    <rect x="{x}" y="{y}" width="136" height="72" rx="6" fill="#0d1117" stroke="{GOLD}" stroke-opacity="0.18"/>
    <rect x="{x}" y="{y}" width="3" height="72" fill="{RED}"/>
    <text x="{x+14}" y="{y+20}" fill="{MUTED}" font-size="10" letter-spacing="1.5">{label}</text>
    <text x="{x+14}" y="{y+48}" fill="{GOLD}" font-size="26" font-weight="700" filter="url(#glow)">{fmt(value)}</text>
    <text x="{x+14}" y="{y+63}" fill="#6e7681" font-size="9">{sub}</text>
  </g>""")

    out.append(f'  <line x1="510" y1="84" x2="510" y2="236" stroke="{GOLD}" stroke-opacity="0.15"/>')
    out.append(f'  <text x="540" y="92" fill="{MUTED}" font-size="11" letter-spacing="2">LANGUAGE CORE // TOP 5</text>')

    total = sum(d["langs"].values()) or 1
    top = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:5]
    bar_w = 250
    for i, (name, size) in enumerate(top):
        pct = size / total
        y = 118 + i * 24
        bw = max(4, pct * bar_w)
        out.append(f"""  <text x="540" y="{y+9}" fill="{TEXT}" font-size="12">{escape(name)}</text>
  <rect x="640" y="{y}" width="{bar_w}" height="10" rx="5" fill="#21262d"/>
  <rect x="640" y="{y}" width="0" height="10" rx="5" fill="url(#bar)">
    <animate attributeName="width" from="0" to="{bw:.1f}" begin="{0.3 + i*0.15:.2f}s" dur="1.2s" fill="freeze"/>
  </rect>
  <text x="960" y="{y+9}" fill="{GOLD}" font-size="11" text-anchor="end">{pct*100:.1f}%</text>""")
    if not top:
        out.append(f'  <text x="540" y="130" fill="{MUTED}" font-size="12">no public code yet</text>')
    out.append("</svg>\n")
    return "\n".join(out)


# ---------------------------------------------------------------- activity card
LEVEL = {"NONE": "#1c1417", "FIRST_QUARTILE": "#4a0d0d", "SECOND_QUARTILE": "#8b1a1a",
         "THIRD_QUARTILE": RED, "FOURTH_QUARTILE": GOLD}


def streaks(days):
    days = sorted(days, key=lambda x: x["date"])
    best = cur = 0
    for x in days:
        cur = cur + 1 if x["contributionCount"] > 0 else 0
        best = max(best, cur)
    current = 0
    for i, x in enumerate(reversed(days)):
        if x["contributionCount"] > 0:
            current += 1
        elif i == 0:  # hoje ainda sem contribuição não quebra a sequência
            continue
        else:
            break
    return current, best


def activity_svg(d):
    w, h = 1000, 230
    cell, gap = 12, 3
    step = cell + gap
    weeks = d["weeks"][-53:]
    x0, y0 = 1000 - 40 - len(weeks) * step + gap, 78
    scan = 7.0
    days = [x for wk in weeks for x in wk]
    current, best = streaks(days)
    best_day = max(days, key=lambda x: x["contributionCount"]) if days else None

    out = [frame(w, h, "COMBAT LOG // LAST 365 DAYS", f"{d['total']} CONTRIBUTIONS")]

    # meses
    last_month = None
    for i, wk in enumerate(weeks):
        m = dt.date.fromisoformat(wk[0]["date"]).month
        if m != last_month and i < len(weeks) - 2:
            label = dt.date(2000, m, 1).strftime("%b").upper()
            out.append(f'  <text x="{x0 + i*step}" y="{y0-8}" fill="{MUTED}" font-size="9">{label}</text>')
            last_month = m
    for wd, label in ((1, "MON"), (3, "WED"), (5, "FRI")):
        out.append(f'  <text x="{x0-8}" y="{y0 + wd*step + 9}" fill="{MUTED}" font-size="9" text-anchor="end">{label}</text>')

    n = len(weeks)
    for i, wk in enumerate(weeks):
        x = x0 + i * step
        t = min(max(i / max(n - 1, 1) * 0.92 + 0.04, 0.03), 0.95)
        for day in wk:
            y = y0 + day["weekday"] * step
            color = LEVEL.get(day["contributionLevel"], LEVEL["NONE"])
            if day["contributionCount"] > 0:
                kt = f"0;{t-0.02:.3f};{t:.3f};{t+0.04:.3f};1"
                out.append(f'  <rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{color}">'
                           f'<animate attributeName="fill" values="{color};{color};#FFF6C2;{color};{color}" '
                           f'keyTimes="{kt}" dur="{scan}s" repeatCount="indefinite"/></rect>')
            else:
                out.append(f'  <rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{color}"/>')

    # feixe de varredura
    gx0, gx1 = x0 - 4, x0 + n * step - gap + 4
    gh = 7 * step - gap + 8
    out.append(f"""  <clipPath id="gridclip"><rect x="{gx0}" y="{y0-4}" width="{gx1-gx0+2}" height="{gh}"/></clipPath>
  <g clip-path="url(#gridclip)">
    <rect x="{gx0 - 60}" y="{y0-4}" width="60" height="{gh}" fill="url(#beam)">
      <animate attributeName="x" values="{gx0-60};{gx1-60}" dur="{scan}s" repeatCount="indefinite"/>
    </rect>
    <rect x="{gx0}" y="{y0-4}" width="2" height="{gh}" fill="{GOLD}" filter="url(#glow)">
      <animate attributeName="x" values="{gx0};{gx1}" dur="{scan}s" repeatCount="indefinite"/>
    </rect>
  </g>""")

    # rodapé
    fy = y0 + 7 * step + 26
    bd = (f"BEST DAY: {best_day['contributionCount']} ({dt.date.fromisoformat(best_day['date']).strftime('%d %b').upper()})"
          if best_day and best_day["contributionCount"] else "BEST DAY: —")
    out.append(f'  <text x="{x0}" y="{fy}" fill="{TEXT}" font-size="11" letter-spacing="1.5">'
               f'<tspan fill="{GOLD}">●</tspan> CURRENT STREAK: {current}d   '
               f'<tspan fill="{GOLD}">●</tspan> LONGEST: {best}d   '
               f'<tspan fill="{GOLD}">●</tspan> {bd}</text>')
    lx = 1000 - 40 - 5 * 16 - 70
    out.append(f'  <text x="{lx}" y="{fy}" fill="{MUTED}" font-size="9">LESS</text>')
    for k, key in enumerate(LEVEL):
        out.append(f'  <rect x="{lx + 30 + k*16}" y="{fy-10}" width="12" height="12" rx="2.5" fill="{LEVEL[key]}"/>')
    out.append(f'  <text x="{lx + 30 + 5*16 + 4}" y="{fy}" fill="{MUTED}" font-size="9">MORE</text>')
    out.append("</svg>\n")
    return "\n".join(out)


# ---------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    if args and args[0] == "--sample":
        data, outdir = sample(), args[1] if len(args) > 1 else "dist"
    else:
        login, outdir = args[0], args[1] if len(args) > 1 else "dist"
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN não definido")
        data = fetch(login, token)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "hud-stats.svg"), "w", encoding="utf-8") as f:
        f.write(stats_svg(data))
    with open(os.path.join(outdir, "hud-activity.svg"), "w", encoding="utf-8") as f:
        f.write(activity_svg(data))
    print(f"ok: {data['total']} contributions, {len(data['langs'])} languages -> {outdir}")


if __name__ == "__main__":
    main()
