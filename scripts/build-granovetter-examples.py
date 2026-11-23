#!/usr/bin/env python3
"""Build the shipped Granovetter examples from one scene description.

All four files share one geometry so the light, dark, full-editorial and
traced variants can never drift apart:

    example-granovetter.html         minimal light (static)
    example-granovetter-dark.html    minimal dark (static)
    example-granovetter-full.html    full editorial (static)
    example-granovetter-traced.html  minimal light + the pinned trace controller

The traced variant copies the controller verbatim from template-trace.html,
which is the only way it can pass lint-skin, self_check and
verify-granovetter. Run from the repository root:

    python3 scripts/build-granovetter-examples.py
"""

from __future__ import annotations

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "skills/diagram-design/assets"
TEMPLATE = ASSETS / "template-trace.html"

FONT_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1'
    '&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
)

SKINS = {
    "light": {
        "paper": "#f5f5f5", "paper2": "#ececec", "ink": "#2d3142", "muted": "#4f5d75",
        "soft": "#5a6580", "accent": "#bf4520", "accent_tint": "rgba(191,69,32,0.08)",
        "node_fill": "#ffffff", "target_fill": "rgba(45,49,66,0.05)",
        "missing_fill": "rgba(45,49,66,0.02)", "rule": "rgba(45,49,66,0.12)",
        "chip_fill": "#ffffff", "link": "#2e5aa8",
    },
    "dark": {
        "paper": "#2d3142", "paper2": "#393e53", "ink": "#f5f5f5", "muted": "#bfc0c0",
        "soft": "#949eb2", "accent": "#f08a59", "accent_tint": "rgba(240,138,89,0.10)",
        "node_fill": "rgba(245,245,245,0.04)", "target_fill": "rgba(245,245,245,0.10)",
        "missing_fill": "rgba(245,245,245,0.03)", "rule": "rgba(245,245,245,0.12)",
        "chip_fill": "rgba(245,245,245,0.04)", "link": "#739fdf",
    },
}

TITLE = "Who can change production"
DESC = (
    "Granovetter diagram of production access: contributors drive the CI runner, the runner "
    "assumes the deploy role, and the deploy role writes to production. Cloud admins hold "
    "production directly and can extend the deploy role's trust, and break-glass users can "
    "assume the deploy role, with the control or missing control on each path."
)

R = 60
TARGET_R = 64
# id, label lines, sublabel, cx, cy, target?
NODES = [
    ("admins", ("Cloud admins",), "4 standing", 280, 180, False),
    ("breakglass", ("Break-glass", "users"), "2 named", 280, 360, False),
    ("contributors", ("Contributors",), "38 with push", 280, 560, False),
    ("deploy", ("Deploy role",), "cloud IAM role", 800, 240, False),
    ("ci", ("CI runner",), "self-hosted", 800, 560, False),
    ("prod", ("Production",), "cluster · data", 1120, 240, True),
]


def dx(dy: float, radius: float = R) -> float:
    return math.sqrt(radius * radius - dy * dy)


# Edge endpoints sit on the circles. Ends stop 1px short so the arrowhead tip
# touches the rim instead of covering it.
LEFT_IN = round(800 - dx(20), 1)          # deploy-role rim at y=220 / y=260
WRITERS_OUT = round(280 + dx(20), 1)      # contributors rim at y=540 / y=580
CI_IN = round(800 - dx(20), 1)            # ci rim at y=540 / y=580

EDGES = [
    # id, from, to, kind, d, label, label_xy, carries
    ("org-admin", "admins", "prod", "held",
     f"M 280,120 V 96 Q 280,88 288,88 H 1112 Q 1120,88 1120,96 V {240 - TARGET_R - 1}",
     "ORG ADMIN", (700, 74), None),
    ("edit-trust", "admins", "deploy", "introduce",
     f"M 340,180 H 592 Q 600,180 600,188 V 212 Q 600,220 608,220 H {LEFT_IN - 1}",
     "EDIT TRUST", (470, 156), "prod"),
    ("assume", "breakglass", "deploy", "obtain",
     f"M 340,360 H 632 Q 640,360 640,352 V 268 Q 640,260 648,260 H {LEFT_IN - 1}",
     "ASSUME ROLE", (470, 336), None),
    ("open-pr", "contributors", "ci", "held",
     f"M {WRITERS_OUT},540 H {CI_IN - 1}", "OPEN PR", (540, 516), None),
    ("merge", "contributors", "ci", "held",
     f"M {WRITERS_OUT},580 H {CI_IN - 1}", "MERGE", (540, 624), None),
    ("oidc", "ci", "deploy", "held",
     f"M 800,500 V {240 + R + 1}", None, None, None),
    ("deploy-write", "deploy", "prod", "held",
     f"M 860,240 H {1120 - TARGET_R - 1}", "WRITES", (958, 276), None),
]

# id, edge, state, text, x, y, w
GATES = [
    ("standing-admin", "edit-trust", "gap", "standing · no JIT", 396, 168, 148),
    ("mfa-ticket", "assume", "control", "MFA + ticket", 410, 348, 120),
    ("pr-workflows", "open-pr", "gap", "workflows run on PR", 432, 528, 216),
    ("reviews", "merge", "control", "2 reviews + CODEOWNERS", 432, 568, 216),
    ("oidc-main", "oidc", "control", "OIDC · main branch only", 704, 388, 192),
    ("session-policy", "deploy-write", "missing", "no session policy", 898, 228, 120),
]

# All-of principals: node id -> (start, end) angles in degrees, screen
# coordinates (0 = right, 90 = down), swept clockwise. The arc is drawn
# JOIN_GAP outside the rim and must span the tip of every arrow into the node.
JOINS: dict[str, tuple[float, float]] = {}
JOIN_GAP = 12

# edge, text, x, y, w
CHIPS = [("edit-trust", "carries Production", 612, 211, 112)]

LEGEND_Y = 680

REVOKE_LABELS = {
    "org-admin": "Org admin",
    "edit-trust": "Edit trust",
    "assume": "Assume role",
    "open-pr": "Open PR",
    "merge": "Merge",
    "oidc": "OIDC trust",
    "deploy-write": "Deploy writes",
}


def attrs(**pairs: object) -> str:
    return " ".join(f'{key.replace("_", "-")}="{value}"' for key, value in pairs.items())


def svg_body(skin: dict[str, str], slug: str) -> str:
    s = skin
    out: list[str] = []
    add = out.append
    add(f'<svg viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-labelledby="{slug}-title {slug}-desc" data-diagram-type="granovetter">')
    add(f'  <title id="{slug}-title">{TITLE}</title>')
    add(f'  <desc id="{slug}-desc">{DESC}</desc>')
    add('  <defs>')
    add(f'    <marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{s["muted"]}"/></marker>')
    add(f'    <marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{s["accent"]}"/></marker>')
    add(f'    <marker id="arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{s["link"]}"/></marker>')
    add('  </defs>')
    add('')
    add(f'  <rect width="100%" height="100%" fill="{s["paper"]}"/>')
    add('')
    add('  <!-- Edges (drawn before everything else) -->')
    gap_edges = {edge for _, edge, state, *_ in GATES if state == "gap"}
    for edge_id, src, dst, kind, d, *_rest in EDGES:
        carries = _rest[2]
        focal = edge_id in gap_edges and kind == "held"
        stroke = s["accent"] if focal else s["muted"]
        marker = "arrow-accent" if focal else "arrow"
        dash = ' stroke-dasharray="5,4"' if kind != "held" else ""
        extra = f' data-gv-carries="{carries}"' if carries else ""
        width = "1.4" if focal else "1.2"
        add(f'  <path data-gv-edge="{edge_id}" data-gv-from="{src}" data-gv-to="{dst}" data-gv-kind="{kind}"{extra} '
            f'd="{d}" fill="none" stroke="{stroke}" stroke-width="{width}"{dash} marker-end="url(#{marker})"/>')
    add('')
    add('  <!-- Edge labels (masked) -->')
    for edge_id, _src, _dst, _kind, _d, label, xy, _carries in EDGES:
        if not label:
            continue
        x, y = xy
        width = max(48, 8 * len(label) + 12)
        width += width % 4 and 4 - width % 4
        color = s["accent"] if edge_id in gap_edges and _kind == "held" else s["soft"]
        add(f'  <g data-gv-for="{edge_id}">')
        add(f'    <rect x="{x - width // 2}" y="{y - 10}" width="{width}" height="14" rx="2" fill="{s["paper"]}"/>')
        add(f'    <text x="{x}" y="{y}" fill="{color}" font-size="8" font-family="\'Geist Mono\', monospace" text-anchor="middle" letter-spacing="0.06em">{label}</text>')
        add('  </g>')
    add('')
    add('  <!-- Control gates: control (solid), missing (dashed), gap (dashed accent, max 2) -->')
    for gate_id, edge, state, text, x, y, w in GATES:
        if state == "gap":
            fill, stroke, dash, color, sw = s["accent_tint"], s["accent"], ' stroke-dasharray="4,3"', s["accent"], "1.2"
        elif state == "missing":
            fill, stroke, dash, color, sw = s["missing_fill"], s["muted"], ' stroke-dasharray="4,3"', s["muted"], "1"
        else:
            fill, stroke, dash, color, sw = s["node_fill"], s["muted"], "", s["ink"], "1"
        add(f'  <g data-gv-gate="{gate_id}" data-gv-on="{edge}" data-gv-state="{state}">')
        add(f'    <rect x="{x}" y="{y}" width="{w}" height="24" rx="2" fill="{s["paper"]}"/>')
        add(f'    <rect x="{x}" y="{y}" width="{w}" height="24" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash}/>')
        add(f'    <text x="{x + w // 2}" y="{y + 15}" fill="{color}" font-size="9" font-family="\'Geist Mono\', monospace" text-anchor="middle">{text}</text>')
        add('  </g>')
    add('')
    add('  <!-- Carried references on introduce edges -->')
    for edge, text, x, y, w in CHIPS:
        add(f'  <g data-gv-chip="{edge}">')
        add(f'    <rect x="{x}" y="{y}" width="{w}" height="18" rx="9" fill="{s["paper"]}"/>')
        add(f'    <rect x="{x}" y="{y}" width="{w}" height="18" rx="9" fill="{s["chip_fill"]}" stroke="{s["muted"]}" stroke-width="1"/>')
        add(f'    <text x="{x + w // 2}" y="{y + 12}" fill="{s["ink"]}" font-size="8" font-family="\'Geist Mono\', monospace" text-anchor="middle">{text}</text>')
        add('  </g>')
    if JOINS:
        add('')
        add('  <!-- All-of joins: the arc ties together every arrow the principal needs -->')
        for node_id, lines, sub, cx, cy, target in NODES:
            if node_id in JOINS:
                radius = TARGET_R if target else R
                d = join_arc(cx, cy, radius, *JOINS[node_id])
                add(f'  <path data-gv-join-mark="{node_id}" d="{d}" fill="none" stroke="{s["ink"]}" stroke-width="1.4"/>')
    add('')
    add('  <!-- Principals (painted last) -->')
    for node_id, lines, sub, cx, cy, target in NODES:
        radius = TARGET_R if target else R
        fill = s["target_fill"] if target else s["node_fill"]
        width = "1.2" if target else "1"
        label = " ".join(lines)
        join = ' data-gv-join="all"' if node_id in JOINS else ""
        add(f'  <g data-gv-node="{node_id}" data-gv-label="{label}"{join}>')
        add(f'    <circle cx="{cx}" cy="{cy}" r="{radius}" fill="{s["paper"]}"/>')
        add(f'    <circle cx="{cx}" cy="{cy}" r="{radius}" fill="{fill}" stroke="{s["ink"]}" stroke-width="{width}"/>')
        top = cy - 4 - 7.5 * (len(lines) - 1)
        for index, line in enumerate(lines):
            add(f'    <text x="{cx}" y="{top + 15 * index:g}" fill="{s["ink"]}" font-size="12" font-weight="600" font-family="\'Geist\', sans-serif" text-anchor="middle">{line}</text>')
        add(f'    <text x="{cx}" y="{top + 15 * (len(lines) - 1) + 16:g}" fill="{s["muted"]}" font-size="9" font-family="\'Geist Mono\', monospace" text-anchor="middle">{sub}</text>')
        add('  </g>')
    add('')
    add('  <!-- Legend -->')
    ly = LEGEND_Y
    add(f'  <line x1="40" y1="{ly - 28}" x2="1240" y2="{ly - 28}" stroke="{s["rule"]}" stroke-width="0.8"/>')
    add(f'  <text x="40" y="{ly + 3}" fill="{s["muted"]}" font-size="8" font-family="\'Geist Mono\', monospace" letter-spacing="0.14em">LEGEND</text>')
    # Only the elements this diagram uses get a legend entry (§9: legend covers every type used, nothing extra).
    kinds = {kind for _e, _s, _d, kind, *_ in EDGES}
    states = {state for _g, _e, state, *_ in GATES}
    mono = "font-size=\"9\" font-family=\"'Geist Mono', monospace\""
    def entry(x: int, text_dx: int, swatch: str, text: str) -> None:
        add(swatch)
        add(f'  <text x="{x + text_dx}" y="{ly + 3}" fill="{s["muted"]}" {mono}>{text}</text>')
    x = 123
    entry(x, 25, f'  <circle cx="{x + 9}" cy="{ly}" r="9" fill="{s["node_fill"]}" stroke="{s["ink"]}" stroke-width="1"/>', "principal")
    x += 113
    entry(x, 44, f'  <line x1="{x}" y1="{ly}" x2="{x + 36}" y2="{ly}" stroke="{s["muted"]}" stroke-width="1.2" marker-end="url(#arrow)"/>', "holds")
    x += 100
    if kinds & {"obtain", "introduce"}:
        entry(x, 44, f'  <line x1="{x}" y1="{ly}" x2="{x + 36}" y2="{ly}" stroke="{s["muted"]}" stroke-width="1.2" stroke-dasharray="5,4" marker-end="url(#arrow)"/>', "one action away")
        x += 164
    if CHIPS:
        entry(x, 72, f'  <rect x="{x}" y="{ly - 9}" width="64" height="18" rx="9" fill="{s["chip_fill"]}" stroke="{s["muted"]}" stroke-width="1"/>', "carried reference")
        x += 208
    if JOINS:
        entry(x, 44, f'  <path d="M {x + 4},{ly + 6} A 14,14 0 0 1 {x + 32},{ly + 6}" fill="none" stroke="{s["ink"]}" stroke-width="1.4"/>', "needs every arrow in")
        x += 180
    if "control" in states:
        entry(x, 36, f'  <rect x="{x}" y="{ly - 8}" width="28" height="16" rx="2" fill="{s["node_fill"]}" stroke="{s["muted"]}" stroke-width="1"/>', "control")
        x += 112
    if "missing" in states:
        entry(x, 36, f'  <rect x="{x}" y="{ly - 8}" width="28" height="16" rx="2" fill="{s["missing_fill"]}" stroke="{s["muted"]}" stroke-width="1" stroke-dasharray="4,3"/>', "missing control")
        x += 156
    if "gap" in states:
        entry(x, 36, f'  <rect x="{x}" y="{ly - 8}" width="28" height="16" rx="2" fill="{s["accent_tint"]}" stroke="{s["accent"]}" stroke-width="1.2" stroke-dasharray="4,3"/>', "focal gap")
    add('</svg>')
    return "\n".join(out)


def join_arc(cx: float, cy: float, radius: float, start: float, end: float) -> str:
    rr = radius + JOIN_GAP
    span = (end - start) % 360
    point = lambda deg: (round(cx + rr * math.cos(math.radians(deg)), 1), round(cy + rr * math.sin(math.radians(deg)), 1))
    (x1, y1), (x2, y2) = point(start), point(end)
    return f"M {x1:g},{y1:g} A {rr:g},{rr:g} 0 {int(span > 180)} 1 {x2:g},{y2:g}"


def indent(block: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line else line for line in block.splitlines())


def minimal_page(skin_name: str, slug: str, traced: bool = False) -> str:
    s = SKINS[skin_name]
    trace_css = ""
    controls = ""
    script = ""
    if traced:
        trace_css = TRACE_CSS
        controls = trace_controls()
        script = "\n" + controller_block() + "\n"
    body = indent(svg_body(s, slug), 8)
    root_open = '<div data-trace-root>' if traced else '<div>'
    eyebrow = "Granovetter · traced · Diagram Design" if traced else "Granovetter · Diagram Design"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{TITLE} · Granovetter</title>
  {FONT_LINK}
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --color-paper:   {s["paper"]};
      --color-ink:     {s["ink"]};
      --color-muted:   {s["muted"]};
      --color-accent:  {s["accent"]};
      --font-sans:     'Geist', system-ui, sans-serif;
      --font-serif:    'Instrument Serif', serif;
      --font-mono:     'Geist Mono', ui-monospace, monospace;
    }}

    body {{
      font-family: var(--font-sans);
      background: var(--color-paper);
      color: var(--color-ink);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 3rem 2rem;
    }}

    .frame {{ max-width: 1280px; width: 100%; }}
    .diagram-container {{ width: 100%; overflow-x: auto; }}

    .eyebrow {{
      font-family: var(--font-mono);
      font-size: 0.66rem;
      font-weight: 500;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--color-muted);
      margin-bottom: 0.5rem;
    }}

    h1 {{
      font-family: var(--font-serif);
      font-size: clamp(1.5rem, 2.4vw + 0.75rem, 2rem);
      font-weight: 400;
      letter-spacing: -0.02em;
      line-height: 1.15;
      color: var(--color-ink);
      margin-bottom: 1.5rem;
    }}

    svg {{ width: 100%; min-width: 1280px; display: block; }}
{trace_css}
    @media print {{
      .diagram-container {{ overflow-x: visible; }}
      svg {{ min-width: 0; }}
    }}
  </style>
</head>
<body>
  <div class="frame">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{TITLE}</h1>

    {root_open}
      <div class="diagram-container">
{body}
      </div>
{controls}    </div>
  </div>
{script}</body>
</html>
"""


TRACE_CSS = """
    [data-trace-root][data-trace-active="true"] .is-dim { opacity: 0.16; }
    [data-trace-root] .is-revoked { opacity: 0.12; }
    [data-gv-node] { cursor: pointer; }
    @media (prefers-reduced-motion: no-preference) {
      [data-gv-node], [data-gv-edge], [data-gv-gate], [data-gv-for], [data-gv-chip], [data-gv-join-mark] { transition: opacity 160ms ease; }
    }

    .trace-controls {
      display: flex;
      flex-wrap: wrap;
      gap: 12px 24px;
      align-items: flex-start;
      margin-top: 16px;
      font-family: var(--font-mono);
      font-size: 0.72rem;
      color: var(--color-muted);
    }
    .trace-controls[hidden] { display: none; }
    .trace-controls fieldset { border: 0; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
    .trace-controls legend { float: left; margin-right: 8px; letter-spacing: 0.12em; text-transform: uppercase; font-size: 0.62rem; }
    .trace-controls button {
      font: inherit;
      color: var(--color-ink);
      background: #ffffff;
      border: 1px solid rgba(45,49,66,0.30);
      border-radius: 4px;
      padding: 4px 8px;
      cursor: pointer;
    }
    .trace-controls button[aria-pressed="true"] { border-color: var(--color-ink); background: rgba(45,49,66,0.08); }
    .trace-controls button:focus-visible, .trace-controls input:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
    .trace-controls label { display: inline-flex; gap: 6px; align-items: center; }
    .trace-status { min-height: 1.4em; margin-top: 8px; font-family: var(--font-mono); font-size: 0.72rem; color: var(--color-ink); }
    /* Hosts pin chat and presence widgets to the bottom corners; when the controls end the page, leave room to scroll them clear. */
    [data-trace-root]:last-child { padding-bottom: 96px; }
    @media print {
      .trace-controls, .trace-status { display: none; }
      [data-trace-root]:last-child { padding-bottom: 0; }
    }
"""


def trace_controls() -> str:
    names = {node_id: " ".join(lines) for node_id, lines, *_ in NODES}
    lines = ['      <div class="trace-controls" data-trace-controls hidden>',
             '        <fieldset>',
             '          <legend>Trace reach from</legend>']
    for node_id, *_ in NODES:
        lines.append(f'          <button type="button" data-trace-select="{node_id}" aria-pressed="false">{names[node_id]}</button>')
    lines.append('        </fieldset>')
    if any(kind != "held" for _e, _s, _d, kind, *_ in EDGES):
        lines.append('        <label><input type="checkbox" data-trace-intro> Include one-action-away arrows</label>')
    lines += ['        <fieldset>',
              '          <legend>Revoke</legend>']
    for edge_id, src, dst, _kind, _d, label, *_ in EDGES:
        text = REVOKE_LABELS.get(edge_id) or f"{names[src]} → {names[dst]}"
        lines.append(f'          <button type="button" data-trace-revoke="{edge_id}" aria-pressed="false">{text}</button>')
    lines += ['        </fieldset>',
              '        <button type="button" data-trace-reset>Reset</button>',
              '      </div>',
              '      <p class="trace-status" data-trace-status role="status" aria-live="polite" aria-atomic="true"></p>']
    return "\n".join(lines) + "\n"


def controller_block() -> str:
    source = TEMPLATE.read_text(encoding="utf-8")
    match = re.search(r"  <script data-diagram-trace>.*?</script>", source, re.DOTALL)
    if not match:
        raise SystemExit("template-trace.html has no data-diagram-trace controller")
    return match.group()


CARDS = """
    <div class="cards">
      <div class="card">
        <p class="eyebrow">THE HEADLINE</p>
        <div class="card-header"><span class="card-dot coral"></span><h3>Two gaps, both upstream of review</h3></div>
        <p>Workflows run on every pull request with the runner's identity, before anyone reviews them. Cloud admins can rewrite the deploy role's trust without a just-in-time step.</p>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-dot ink"></span><h3>Read the arrows</h3></div>
        <ul>
          <li>Solid: a permission held today.</li>
          <li>Dashed: one action away. The chip names the reference an introduction hands over.</li>
          <li>Reach is every circle you can walk to along solid arrows.</li>
        </ul>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-dot muted"></span><h3>Controls on the path</h3></div>
        <p>Every box sits on the arrow it gates. A dashed box is a control that would belong there and does not exist.</p>
      </div>
    </div>
"""


def full_page() -> str:
    s = SKINS["light"]
    body = indent(svg_body(s, "granovetter-full"), 6)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{TITLE} · Granovetter</title>
  {FONT_LINK}
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{ --color-paper:{s["paper"]}; --color-paper-2:{s["paper2"]}; --color-ink:{s["ink"]}; --color-muted:{s["muted"]}; --color-soft:{s["soft"]}; --color-rule:{s["rule"]}; --color-accent:{s["accent"]}; --color-link:{s["link"]}; --font-sans:'Geist',system-ui,sans-serif; --font-serif:'Instrument Serif',serif; --font-mono:'Geist Mono',ui-monospace,monospace; }}
    body {{ font-family: var(--font-sans); background: var(--color-paper); min-height: 100vh; padding: 3rem 2rem; color: var(--color-ink); }}
    .container {{ max-width: 1360px; margin: 0 auto; }}
    .header {{ margin-bottom: 2.5rem; }}
    .header-eyebrow {{ font-family: var(--font-mono); font-size: 0.66rem; font-weight: 500; letter-spacing: 0.18em; text-transform: uppercase; color: var(--color-muted); margin-bottom: 0.75rem; }}
    h1 {{ font-family: var(--font-serif); font-size: clamp(1.75rem, 3vw + 1rem, 2.5rem); font-weight: 400; letter-spacing: -0.02em; line-height: 1.1; margin-bottom: 0.5rem; }}
    .subtitle {{ font-size: 1rem; line-height: 1.55; color: var(--color-muted); max-width: 62ch; }}
    .diagram-container {{ background: var(--color-paper-2); border-radius: 8px; border: 1px solid var(--color-rule); padding: 1.5rem; overflow-x: auto; }}
    svg {{ width: 100%; min-width: 1280px; display: block; }}
    .cards {{ display: grid; grid-template-columns: 1.1fr 1fr 0.9fr; gap: 1rem; margin-top: 1.5rem; }}
    @media (max-width: 820px) {{ .cards {{ grid-template-columns: 1fr; }} }}
    .card {{ background: #fff; border-radius: 6px; border: 1px solid var(--color-rule); padding: 1.25rem; }}
    .card .eyebrow {{ font-family: var(--font-mono); font-size: 0.5rem; letter-spacing: 0.18em; text-transform: uppercase; color: var(--color-muted); margin-bottom: 0.5rem; }}
    .card-header {{ display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.875rem; padding-bottom: 0.875rem; border-bottom: 1px solid rgba(45,49,66,0.08); }}
    .card-dot {{ width: 7px; height: 7px; border-radius: 50%; }}
    .card-dot.ink {{ background: var(--color-ink); }} .card-dot.muted {{ background: var(--color-muted); }} .card-dot.coral {{ background: var(--color-accent); }}
    .card h3 {{ font-size: 0.875rem; font-weight: 600; }}
    .card p, .card ul {{ color: var(--color-muted); font-size: 0.8125rem; line-height: 1.55; list-style: none; }}
    .card li {{ margin-bottom: 0.3rem; padding-left: 0.875rem; position: relative; }}
    .card li::before {{ content: '—'; position: absolute; left: 0; color: rgba(45,49,66,0.25); font-size: 0.75rem; }}
    .footer {{ margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid rgba(45,49,66,0.10); font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.06em; color: var(--color-soft); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; }}
    @media print {{
      .diagram-container {{ overflow-x: visible; }}
      svg {{ min-width: 0; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <p class="header-eyebrow">Granovetter · Diagram Design</p>
      <h1>{TITLE}</h1>
      <p class="subtitle">Six principals and the permissions between them. Each arrow is a reference someone holds; each box on an arrow is the control that gates it. Coral is spent on the two gaps that sit upstream of review.</p>
    </div>
    <div class="diagram-container">
{body}
    </div>
{CARDS}
    <div class="footer">
      <span>Granovetter diagram · capability reach</span>
      <span>Diagram Design</span>
    </div>
  </div>
</body>
</html>
"""


def main() -> None:
    outputs = {
        "example-granovetter.html": minimal_page("light", "granovetter"),
        "example-granovetter-dark.html": minimal_page("dark", "granovetter-dark"),
        "example-granovetter-full.html": full_page(),
        "example-granovetter-traced.html": minimal_page("light", "granovetter-traced", traced=True),
    }
    for name, text in outputs.items():
        (ASSETS / name).write_text(text, encoding="utf-8")
        print(f"wrote {ASSETS / name}")


if __name__ == "__main__":
    main()
