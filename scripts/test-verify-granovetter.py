#!/usr/bin/env python3
"""Adversarial cases for the Granovetter checker: every rule fails when broken."""

from __future__ import annotations

import importlib.util
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERIFIER = ROOT / "scripts/verify-granovetter.py"
BUILDER = ROOT / "scripts/build-granovetter-examples.py"
STATIC = ROOT / "skills/diagram-design/assets/example-granovetter.html"
TRACED = ROOT / "skills/diagram-design/assets/example-granovetter-traced.html"


def load():
    spec = importlib.util.spec_from_file_location("verify_granovetter", VERIFIER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect(module, source: str, old: str, new: str, needle: str, label: str) -> None:
    assert old in source, f"{label}: fixture text not found: {old!r}"
    errors = module.check_source(source.replace(old, new, 1))
    assert any(needle in error for error in errors), f"{label}: expected {needle!r}, got {errors}"


def joined_fixture() -> str:
    spec = importlib.util.spec_from_file_location("granovetter_builder", BUILDER)
    assert spec and spec.loader
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.JOINS = {"ci": (150, 210)}
    return builder.minimal_page("light", "granovetter-joined", traced=True)


def main() -> None:
    module = load()
    static = STATIC.read_text(encoding="utf-8")
    traced = TRACED.read_text(encoding="utf-8")
    assert module.check_source(static) == [], module.check_source(static)
    assert module.check_source(traced) == [], module.check_source(traced)

    cases = [
        # Diagram identity and principals
        ('data-diagram-type="granovetter"', 'data-diagram-type="dependency"', "data-diagram-type=granovetter", "type"),
        ('data-gv-node="breakglass"', 'data-gv-node="admins"', "duplicate principal", "duplicate node"),
        ('<circle cx="280" cy="360" r="60" fill="#ffffff"', '<circle cx="280" cy="360" r="90" fill="#ffffff"', "radius", "radius"),
        ('data-gv-label="Deploy role"', 'data-gv-label="Release role"', "data-gv-label", "label mismatch"),
        ('<g data-gv-node="ci"', '<g transform="translate(4,0)" data-gv-node="ci"', "transform", "moved node"),
        # Labels must fit inside their circle (circles are r=60 here)
        ('text-anchor="middle">self-hosted</text>', 'text-anchor="middle">self-hosted on every laptop</text>', "runs past the circle", "long sublabel"),
        ('text-anchor="middle">Contributors</text>', 'text-anchor="middle">Contributors and maintainers</text>', "runs past the circle", "long name"),
        ('text-anchor="middle">self-hosted</text>', 'text-anchor="start">self-hosted</text>', "runs past the circle", "label anchored off centre"),
        # Edges
        ('data-gv-edge="merge" data-gv-from="contributors"', 'data-gv-edge="merge" data-gv-from="nobody"', "two different principals", "unknown source"),
        ('data-gv-edge="assume" data-gv-from="breakglass" data-gv-to="deploy" data-gv-kind="obtain"',
         'data-gv-edge="assume" data-gv-from="breakglass" data-gv-to="deploy" data-gv-kind="owns"', "data-gv-kind", "bad kind"),
        ('data-gv-kind="introduce" data-gv-carries="prod"', 'data-gv-kind="introduce" data-gv-carries="deploy"', "carry a principal other than its target", "carries target"),
        ('data-gv-kind="introduce" data-gv-carries="prod"', 'data-gv-kind="introduce"', "carry a principal", "missing carries"),
        ('data-gv-edge="oidc" data-gv-from="ci" data-gv-to="deploy" data-gv-kind="held" d="M 800,500 V 301" fill="none" stroke="#4f5d75" stroke-width="1.2"',
         'data-gv-edge="oidc" data-gv-from="ci" data-gv-to="deploy" data-gv-kind="held" d="M 800,500 V 301" fill="none" stroke="#4f5d75" stroke-width="1.2" stroke-dasharray="5,4"',
         "drawn solid", "dashed held"),
        ('d="M 800,500 V 301"', 'd="M 800,520 V 301"', "start on the rim", "start off rim"),
        ('d="M 800,500 V 301"', 'd="M 800,500 V 330"', "end on the rim", "end off rim"),
        ('d="M 800,500 V 301"', 'd="M 800,500 C 800,400 800,350 800,301"', "absolute M/L/H/V/Q", "unparseable path"),
        # Gates
        ('data-gv-gate="mfa-ticket" data-gv-on="assume"', 'data-gv-gate="mfa-ticket" data-gv-on="nowhere"', "must name an arrow", "gate on unknown edge"),
        ('data-gv-gate="mfa-ticket" data-gv-on="assume" data-gv-state="control"', 'data-gv-gate="mfa-ticket" data-gv-on="assume" data-gv-state="maybe"', "data-gv-state", "bad state"),
        ('data-gv-gate="reviews" data-gv-on="merge"', 'data-gv-gate="reviews" data-gv-on="open-pr"', "one gate per arrow", "two gates one edge"),
        ('<rect x="410" y="348" width="120" height="24" rx="2" fill="#ffffff"', '<rect x="410" y="300" width="120" height="24" rx="2" fill="#ffffff"', "straight run", "gate off edge"),
        ('data-gv-state="missing">', 'data-gv-state="control">', "drawn solid", "missing drawn dashed as control"),
        ('data-gv-gate="mfa-ticket" data-gv-on="assume" data-gv-state="control"', 'data-gv-gate="mfa-ticket" data-gv-on="assume" data-gv-state="gap"', "accent stroke", "gap without accent"),
        ('data-gv-gate="oidc-main" data-gv-on="oidc" data-gv-state="control"', 'data-gv-gate="oidc-main" data-gv-on="oidc" data-gv-state="gap"', "accent stroke", "third gap"),
        # Chips
        ('<g data-gv-chip="edit-trust">', '<g data-gv-chip="assume">', "belongs to an introduce arrow", "chip on obtain edge"),
        ('>carries Production<', '>carries Deploy<', "name the carried principal", "chip names wrong principal"),
        ('<rect x="612" y="211" width="112" height="18" rx="9" fill="#ffffff"', '<rect x="612" y="240" width="112" height="18" rx="9" fill="#ffffff"', "straight run", "chip off edge"),
        ('<g data-gv-chip="edit-trust">', '<g data-gv-dropped="edit-trust">', "needs a chip", "introduce without chip"),
        # Labels
        ('<g data-gv-for="merge">', '<g data-gv-for="merges">', "data-gv-for", "label for unknown edge"),
    ]
    count = 0
    for old, new, needle, label in cases:
        if needle is None:
            continue
        expect(module, static, old, new, needle, label)
        count += 1

    # The third gap must trip the focal budget, not just the colour rule.
    third_gap = re.sub(
        r'(<g data-gv-gate="oidc-main" data-gv-on="oidc" data-gv-state=")control(">\s*<rect[^>]*/>\s*<rect[^>]*?)fill="#ffffff" stroke="#4f5d75" stroke-width="1"',
        r'\1gap\2fill="rgba(191,69,32,0.08)" stroke="#bf4520" stroke-width="1.2" stroke-dasharray="4,3"',
        static, count=1,
    )
    assert third_gap != static
    assert any("focal gaps" in error for error in module.check_source(third_gap)), module.check_source(third_gap)
    count += 1

    trace_cases = [
        ('<script data-diagram-trace>', '<script data-diagram-controls>', "only the data-diagram-trace attribute", "wrong script attribute"),
        ("const revoked = new Set();", "const revoked = new Set(); fetch('/x');", "exactly match the controller", "tampered controller"),
        ('data-trace-controls hidden>', 'data-trace-controls>', "ship hidden", "controls visible in source"),
        ('role="status" aria-live="polite"', 'role="status" aria-live="off"', "aria-live=polite", "status not live"),
        ('<button type="button" data-trace-select="ci" aria-pressed="false">CI runner</button>', '', "data-trace-select", "missing select button"),
        ('data-trace-revoke="merge"', 'data-trace-revoke="merged"', "unknown edges", "revoke unknown edge"),
        ('<label><input type="checkbox" data-trace-intro> Include one-action-away arrows</label>', '', "data-trace-intro", "missing intro toggle"),
        ('<div data-trace-root>', '<div>', "data-trace-root", "no trace root"),
        ('</body>', '<script>alert(1)</script></body>', "exactly one script", "second script"),
    ]
    for old, new, needle, label in trace_cases:
        expect(module, traced, old, new, needle, label)
        count += 1

    # A static page that only adds a root still has to carry the whole contract.
    rooted = static.replace("    <div>\n      <div class=\"diagram-container\">", "    <div data-trace-root>\n      <div class=\"diagram-container\">", 1)
    assert rooted != static
    assert any("exactly one script" in error for error in module.check_source(rooted)), module.check_source(rooted)
    count += 1

    # All-of joins: build a fixture from the example scene with the CI runner as an all-of principal
    # (both contributor arrows into it), then break each join rule.
    joined = joined_fixture()
    assert module.check_source(joined) == [], module.check_source(joined)
    arc = re.search(r'<path data-gv-join-mark="ci" d="([^"]+)"', joined).group(1)
    pairs = [tuple(float(v) for v in p.split(",")) for p in re.findall(r"-?[\d.]+,-?[\d.]+", arc)]
    (x1, y1), (x2, y2) = pairs[0], pairs[-1]
    wide = f"M {x1:g},{y1:g} A 72,72 0 1 1 {x2:g},{y2:g}"
    # Same circle, but it stops at 175 degrees, short of the open-pr arrow's tip (~199.5 degrees).
    stop = (800 + 72 * math.cos(math.radians(175)), 560 + 72 * math.sin(math.radians(175)))
    short = f"M {x1:g},{y1:g} A 72,72 0 0 1 {stop[0]:.1f},{stop[1]:.1f}"
    join_cases = [
        ('data-gv-join="all"', 'data-gv-join="any"', 'only takes the value "all"', "bad join value"),
        ('<path data-gv-join-mark="ci"', '<path data-gv-dropped="ci"', "needs a data-gv-join-mark arc", "join without arc"),
        ('<path data-gv-join-mark="ci"', '<path data-gv-join-mark="deploy"', "only a data-gv-join", "arc on a plain node"),
        (f'd="{arc}"', f'd="M {x1:g},{y1:g} L {x2:g},{y2:g}"', "single absolute", "arc not an arc"),
        (f'd="{arc}"', f'd="{short}"', "cross the tip of", "arc misses an arrow"),
        (f'd="{arc}"', f'd="{wide}"', "large-arc flag", "wrong large-arc flag"),
        (f'd="{arc}"', f'd="M {x1 - 30:g},{y1 + 10:g} A 102,102 0 0 1 {x2 - 30:g},{y2 - 10:g}"', "outside the rim", "arc too far out"),
        (f'd="{arc}" fill="none"', f'd="{arc}" stroke-dasharray="4,3" fill="none"', "solid-stroked", "dashed arc"),
        (f'd="{arc}" fill="none" stroke="#2d3142"', f'd="{arc}" fill="none" stroke="#bf4520"', "accent belongs to gaps", "accent arc"),
        ('data-gv-edge="merge" data-gv-from="contributors" data-gv-to="ci"', 'data-gv-edge="merge" data-gv-from="contributors" data-gv-to="deploy"', "at least two arrows in", "join with one arrow in"),
    ]
    for old, new, needle, label in join_cases:
        expect(module, joined, old, new, needle, label)
        count += 1
    # Production is carried by the edit-trust introduction, so it cannot be all-of.
    carried = joined.replace('data-gv-node="prod" data-gv-label="Production"', 'data-gv-node="prod" data-gv-label="Production" data-gv-join="all"', 1)
    assert carried != joined
    assert any("introduction" in error for error in module.check_source(carried)), module.check_source(carried)
    count += 1

    print(f"OK granovetter checker: {count} adversarial cases rejected, shipped examples pass")


if __name__ == "__main__":
    main()
