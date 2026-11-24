#!/usr/bin/env python3
"""Run Granovetter diagrams in Chromium: the trace controller and label fit.

verify-granovetter.py reads markup only. Two things it cannot settle without
a browser are settled here:

* Trace behaviour. For every principal, with one-action-away arrows off and on,
  with nothing revoked and with each arrow revoked in turn, the set of
  principals the controller marks reached must equal the set an independent
  model of the reach rules (below) computes from the same markup. Every
  all-of principal's join mark must follow its principal, and the status line
  must report a partly reachable join. One click-driven pass covers the
  buttons, the intro toggle, Reset and Escape, as the URL drives the rest.
* Label fit. Every name and sublabel drawn in a principal must sit at least
  ``LABEL_INSET`` px inside the rim, measured with getBBox() once the
  webfonts have loaded. verify-granovetter.py only estimates this.

Pages: the shipped Granovetter examples, plus a builder fixture with an
all-of principal. ``--self-test`` proves both checks fire on broken copies.

Requires Playwright and its Chromium; prints ``SKIP:`` without them.

    python3 scripts/test-granovetter-browser.py
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "skills/diagram-design/assets"
BUILDER = ROOT / "scripts/build-granovetter-examples.py"
SVG_RE = re.compile(r"<svg\b.*?</svg>", re.DOTALL)
LABEL_INSET = 2.0  # px of clear paper between a label's box and the rim
FONT_TIMEOUT_MS = 15_000


# ---------------------------------------------------------------- reach model

def scene(source: str) -> tuple[dict[str, dict], list[dict]]:
    svg = ET.fromstring(SVG_RE.search(source).group())
    nodes = {
        el.get("data-gv-node"): {"label": el.get("data-gv-label"), "join": el.get("data-gv-join") == "all"}
        for el in svg.iter() if el.get("data-gv-node")
    }
    edges = [
        {"id": el.get("data-gv-edge"), "from": el.get("data-gv-from"), "to": el.get("data-gv-to"),
         "kind": el.get("data-gv-kind"), "carries": el.get("data-gv-carries", "")}
        for el in svg.iter() if el.get("data-gv-edge")
    ]
    return nodes, edges


def model(nodes: dict, edges: list[dict], source: str, intro: bool, revoked: set[str]) -> set[str]:
    """Least fixed point of the reach rules in references/type-granovetter.md."""
    live = [e for e in edges if e["id"] not in revoked and (e["kind"] == "held" or intro)]
    seen = {source}
    while True:
        before = len(seen)
        for edge in live:
            if edge["from"] not in seen:
                continue
            if edge["kind"] == "introduce":
                if edge["to"] in seen and edge["carries"] in nodes:
                    seen.add(edge["carries"])
            elif not nodes[edge["to"]]["join"]:
                seen.add(edge["to"])
        for node_id, node in nodes.items():
            inputs = [e for e in edges if e["to"] == node_id and e["kind"] != "introduce"]
            if node["join"] and inputs and all(e in live and e["from"] in seen for e in inputs):
                seen.add(node_id)
        if len(seen) == before:
            return seen


def pending(nodes: dict, edges: list[dict], seen: set[str], intro: bool, revoked: set[str]) -> dict[str, int]:
    out = {}
    for node_id, node in nodes.items():
        if node["join"] and node_id not in seen:
            inputs = [e for e in edges if e["to"] == node_id and e["kind"] != "introduce"]
            ready = sum(1 for e in inputs if e["id"] not in revoked and (e["kind"] == "held" or intro) and e["from"] in seen)
            if ready:
                out[node["label"]] = ready
    return out


# ---------------------------------------------------------------- browser

STATE_JS = """() => ({
  reached: [...document.querySelectorAll('[data-gv-node].is-source, [data-gv-node].is-reached')].map(el => el.dataset.gvNode),
  marks: [...document.querySelectorAll('[data-gv-join-mark]')].map(el => [el.dataset.gvJoinMark, el.classList.contains('is-reached'), el.classList.contains('is-dim')]),
  status: document.querySelector('[data-trace-status]').textContent,
  hidden: document.querySelector('[data-trace-controls]').hidden,
})"""

FIT_JS = """(inset) => [...document.querySelectorAll('[data-gv-node]')].flatMap(g => {
  const c = [...g.querySelectorAll('circle')].filter(el => el.getAttribute('stroke')).pop();
  const cx = +c.getAttribute('cx'), cy = +c.getAttribute('cy'), r = +c.getAttribute('r');
  return [...g.querySelectorAll('text')].flatMap(t => {
    const b = t.getBBox();
    const far = Math.max(...[[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]]
      .map(([x, y]) => Math.hypot(x - cx, y - cy)));
    return far > r - inset ? [`${g.dataset.gvNode}: '${t.textContent}' reaches ${(far - r + inset).toFixed(1)}px past the ${inset}px inset`] : [];
  });
})"""


def fonts_ready(page) -> bool:
    page.evaluate("() => document.fonts.ready")
    return page.evaluate("() => document.fonts.check('600 12px Geist') && document.fonts.check('9px \"Geist Mono\"')")


def check_fit(page, url: str) -> list[str]:
    page.goto(url)
    page.wait_for_load_state("networkidle", timeout=FONT_TIMEOUT_MS)
    if not fonts_ready(page):
        return [f"{url}: Geist and Geist Mono did not load, so labels cannot be measured"]
    return [f"{url}: {problem}" for problem in page.evaluate(FIT_JS, LABEL_INSET)]


def check_trace(page, url: str, source: str) -> list[str]:
    nodes, edges = scene(source)
    errors: list[str] = []
    page.route("**/*", lambda route: route.abort() if not route.request.url.startswith("file:") else route.continue_())
    revocations = [set()] + [{e["id"]} for e in edges]
    for start in nodes:
        for intro in (False, True):
            for revoked in revocations:
                query = f"?trace={start}&intro={int(intro)}&revoke={','.join(sorted(revoked))}"
                page.goto(url + query)
                got = page.evaluate(STATE_JS)
                want = model(nodes, edges, start, intro, revoked)
                case = f"{Path(url).name}{query}"
                if got["hidden"]:
                    errors.append(f"{case}: trace controls stayed hidden")
                if set(got["reached"]) != want:
                    errors.append(f"{case}: controller reached {sorted(got['reached'])}, model {sorted(want)}")
                for node_id, lit, dim in got["marks"]:
                    if (lit, dim) != (node_id in want, node_id not in want):
                        errors.append(f"{case}: join mark on {node_id} is not following its principal")
                for label, ready in pending(nodes, edges, want, intro, revoked).items():
                    if f"{label} needs " not in got["status"] or f"; {ready} reachable." not in got["status"]:
                        errors.append(f"{case}: status {got['status']!r} does not report {label} with {ready} reachable")
    page.unroute("**/*")
    return errors


def check_clicks(page, url: str, source: str) -> list[str]:
    """The URL drives the sweep; this pass proves the controls drive the same state."""
    nodes, edges = scene(source)
    page.goto(url)
    errors: list[str] = []
    buttons = page.locator("[data-trace-select]")
    if buttons.count() != len(nodes):
        return [f"{url}: expected {len(nodes)} trace buttons, found {buttons.count()}"]
    start = buttons.first.get_attribute("data-trace-select")
    buttons.first.click()
    if page.evaluate(STATE_JS)["reached"] and set(page.evaluate(STATE_JS)["reached"]) != model(nodes, edges, start, False, set()):
        errors.append(f"{url}: clicking {start}'s button traced the wrong set")
    intro = page.locator("[data-trace-intro]")
    if intro.count():
        intro.check()
        if set(page.evaluate(STATE_JS)["reached"]) != model(nodes, edges, start, True, set()):
            errors.append(f"{url}: the intro toggle did not widen the trace")
    revoke = page.locator("[data-trace-revoke]")
    if revoke.count():
        edge = revoke.first.get_attribute("data-trace-revoke")
        revoke.first.click()
        if set(page.evaluate(STATE_JS)["reached"]) != model(nodes, edges, start, bool(intro.count()), {edge}):
            errors.append(f"{url}: revoking {edge} did not cut the trace")
    page.locator("[data-trace-reset]").click()
    state = page.evaluate(STATE_JS)
    if state["reached"] or state["status"] != "Pick a principal to trace.":
        errors.append(f"{url}: Reset left {state['reached']} / {state['status']!r}")
    buttons.first.click()
    page.keyboard.press("Escape")
    if page.evaluate(STATE_JS)["reached"]:
        errors.append(f"{url}: Escape did not clear the trace")
    return errors


# ---------------------------------------------------------------- pages

def joined_fixture() -> str:
    spec = importlib.util.spec_from_file_location("granovetter_builder", BUILDER)
    assert spec and spec.loader
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.JOINS = {"ci": (150, 210)}
    return builder.minimal_page("light", "granovetter-joined", traced=True)


def run(browser, pages: dict[str, str]) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, source in pages.items():
            path = Path(tmp) / name
            path.write_text(source, encoding="utf-8")
            url = path.as_uri()
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            errors += check_fit(page, url)
            if "data-diagram-trace" in source:
                errors += check_trace(page, url, source)
                errors += check_clicks(page, url, source)
            page.close()
    return errors


def shipped() -> dict[str, str]:
    pages = {path.name: path.read_text(encoding="utf-8") for path in sorted(ASSETS.glob("example-granovetter*.html"))}
    pages["fixture-granovetter-joined.html"] = joined_fixture()
    return pages


def self_test(browser) -> list[str]:
    """Each broken copy must be caught; a gate that cannot fail proves nothing."""
    joined = joined_fixture()
    mutants = {
        "join rule dropped": joined.replace("if (joins.has(edge.to)) {", "if (false) {", 1),
        "revocation ignored": joined.replace("if (revoked.has(edge.id) || !seen.has(edge.from)", "if (!seen.has(edge.from)", 1),
        "intro toggle ignored": joined.replace("if (edge.kind !== 'held' && !withIntro) return;", "", 1),
        "join marks never lit": joined.replace("mark.el.classList.toggle('is-reached', seen.has(mark.node));", "", 1),
        "pending join not reported": joined.replace("needs ${count} arrows in", "waits", 1),
        "reset kept the trace": joined.replace("pinned = null;\n          preview = null;\n          revoked.clear();", "revoked.clear();", 1),
        "sublabel past the rim": re.sub(r'(<g data-gv-node="ci"[^>]*>(?:(?!</g>).)*?font-size="9"[^>]*>)[^<]+', r"\1self-hosted on every laptop", joined, count=1, flags=re.DOTALL),
    }
    failures = []
    for label, source in mutants.items():
        if source == joined:
            failures.append(f"{label}: the mutation did not apply; update the self-test anchor")
            continue
        if not run(browser, {f"mutant-{label.replace(' ', '-')}.html": source}):
            failures.append(f"{label}: the broken copy passed")
        else:
            print(f"OK: caught {label}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true", help="prove each check fires on a broken copy")
    args = parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP: playwright is not installed; Granovetter browser checks skipped")
        return 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        errors = self_test(browser) if args.self_test else run(browser, shipped())
        browser.close()
    for error in errors:
        print(f"FAIL: {error}")
    if errors:
        return 1
    print("All Granovetter self-test cases caught" if args.self_test else "All Granovetter browser checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
