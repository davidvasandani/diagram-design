#!/usr/bin/env python3
"""Verify Granovetter (capability) diagrams and their optional trace layer.

A Granovetter diagram is a graph of principals (circles) joined by references
they hold. Three arrow kinds carry the meaning, so each is bound in markup and
checked here rather than trusted to the drawing:

* ``held`` — a permission held today. Solid stroke.
* ``obtain`` — one the holder can acquire with a single action. Dashed.
* ``introduce`` — the holder can hand the target a reference to a third
  principal (``data-gv-carries``). Dashed, and it must carry a chip that
  names the carried principal, which is the Granovetter introduction.

A principal marked ``data-gv-join="all"`` is reached only when every arrow
into it is usable (an author *and* a second approver, say). It carries one
``data-gv-join-mark`` arc, drawn just outside its rim, that crosses the tip of
every incoming arrow, so the static frame shows the requirement too.

Controls sit *on* the arrow they gate (``data-gv-gate`` + ``data-gv-on``) in one
of three states: ``control`` (solid box), ``missing`` (dashed box) or ``gap``
(dashed accent box, at most two, the diagram's focal elements).

The checker reads the raw SVG: every arrow must start on its source circle's
rim and end on its target's, every gate and chip must sit on a straight run of
its own arrow, and nothing may be moved by a transform.

When the page carries the trace layer, its single ``<script data-diagram-trace>``
must byte-match the reviewed controller in ``assets/template-trace.html``
(ADR 0020), the controls must ship hidden so the no-JS frame stays static, and
every principal must have a trace button.

    python3 scripts/verify-granovetter.py --all
    python3 scripts/verify-granovetter.py path/to/diagram.html
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "skills/diagram-design/assets"
TEMPLATE = ASSETS / "template-trace.html"
SVG_RE = re.compile(r"<svg\b.*?</svg>", re.DOTALL)
KINDS = {"held", "obtain", "introduce"}
STATES = {"control", "missing", "gap"}
ACCENTS = {"#bf4520", "#f08a59", "var(--color-accent)"}
ACCENT_DECL_RE = re.compile(r"--color-accent\s*:\s*(#[0-9a-fA-F]{3,8})")
MAX_NODES, MAX_EDGES, MAX_GATES, MAX_GAPS, MAX_INTRODUCTIONS, MAX_JOINS = 8, 12, 6, 2, 2, 2
JOIN_GAP_RANGE = (8, 20)          # arc radius minus circle radius
JOIN_MARGIN = math.radians(4)     # the arc runs at least this far past each arrow tip
ARC_RE = re.compile(
    r"\s*M\s*(-?[\d.]+)[ ,]+(-?[\d.]+)\s+A\s*(-?[\d.]+)[ ,]+(-?[\d.]+)[ ,]+0[ ,]+([01])[ ,]+([01])[ ,]+(-?[\d.]+)[ ,]+(-?[\d.]+)\s*")
MIN_RADIUS, MAX_RADIUS = 24, 72
RIM_TOLERANCE = 2.5
PATH_TOKEN = re.compile(r"[MLHVQ]|[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
PATH_SEPARATORS = re.compile(r"[ \t\n\r\f,]*")
ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def number(value: str | None) -> float:
    try:
        result = float(value or "")
    except ValueError:
        return math.nan
    return result if math.isfinite(result) else math.nan


def path_segments(source: str) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Straight segments of an absolute M/L/H/V/Q path. A quadratic corner is
    one chord from its start to its end point. Empty when unparseable."""
    if not PATH_SEPARATORS.fullmatch(PATH_TOKEN.sub(" ", source)):
        return []
    tokens = PATH_TOKEN.findall(source)
    if not tokens or tokens[0] != "M":
        return []
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    point: tuple[float, float] | None = None
    index = 0
    while index < len(tokens):
        command = tokens[index]
        if command not in ARGS:
            return []
        count = ARGS[command]
        values = tokens[index + 1:index + 1 + count]
        if len(values) != count or any(value in ARGS for value in values):
            return []
        numbers = [float(value) for value in values]
        index += 1 + count
        if command == "M":
            if point is not None:
                return []
            point = (numbers[0], numbers[1])
            continue
        assert point is not None
        if command == "H":
            target = (numbers[0], point[1])
        elif command == "V":
            target = (point[0], numbers[0])
        elif command == "L":
            target = (numbers[0], numbers[1])
        else:
            target = (numbers[2], numbers[3])
        segments.append((point, target))
        point = target
    return segments


def edge_segments(element: ET.Element) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    if local(element.tag) == "line":
        points = [number(element.get(key)) for key in ("x1", "y1", "x2", "y2")]
        if any(math.isnan(value) for value in points):
            return []
        return [((points[0], points[1]), (points[2], points[3]))]
    if local(element.tag) == "path":
        return path_segments(element.get("d", ""))
    return []


def pierces(segments, box: tuple[float, float, float, float]) -> bool:
    """True when a straight horizontal or vertical run crosses the whole box."""
    x, y, width, height = box
    for (x1, y1), (x2, y2) in segments:
        if y1 == y2 and y < y1 < y + height and min(x1, x2) <= x and max(x1, x2) >= x + width:
            return True
        if x1 == x2 and x < x1 < x + width and min(y1, y2) <= y and max(y1, y2) >= y + height:
            return True
    return False


def styled(group: ET.Element, tag: str) -> ET.Element | None:
    """The stroked shape of a group (the paper mask comes first and is unstroked)."""
    shapes = [child for child in group if local(child.tag) == tag and child.get("stroke")]
    return shapes[-1] if shapes else None


def box(rect: ET.Element) -> tuple[float, float, float, float]:
    return tuple(number(rect.get(key)) for key in ("x", "y", "width", "height"))  # type: ignore[return-value]


def text_of(element: ET.Element) -> str:
    return " ".join(" ".join(part.strip() for part in element.itertext()).split())


def moved(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> bool:
    node: ET.Element | None = element
    while node is not None:
        if "transform" in node.attrib or "transform" in node.get("style", "").replace(" ", "").lower():
            return True
        node = parents.get(node)
    return False


class TraceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[dict[str, object]] = []
        self.roots = 0
        self.controls: list[dict[str, str | None]] = []
        self.statuses: list[dict[str, str | None]] = []
        self.selects: list[str] = []
        self.revokes: list[str] = []
        self.intro = 0
        self.root_before_svg = False
        self.seen_svg = False
        self._script: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "svg":
            self.seen_svg = True
        if "data-trace-root" in values:
            self.roots += 1
            if not self.seen_svg:
                self.root_before_svg = True
        if "data-trace-controls" in values:
            self.controls.append(values)
        if "data-trace-status" in values:
            self.statuses.append(values)
        if "data-trace-select" in values:
            self.selects.append(values["data-trace-select"] or "")
        if "data-trace-revoke" in values:
            self.revokes.append(values["data-trace-revoke"] or "")
        if "data-trace-intro" in values:
            self.intro += 1
        if tag == "script":
            self._script = {"names": [name for name, _ in attrs], "values": values, "body": [], "closed": False}
            self.scripts.append(self._script)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script is not None:
            self._script["closed"] = True
            self._script = None

    def handle_data(self, data: str) -> None:
        if self._script is not None:
            body = self._script["body"]
            assert isinstance(body, list)
            body.append(data)


def normalized(body: str) -> str:
    return body.replace("\r\n", "\n").replace("\r", "\n").strip()


def canonical_trace_controller() -> str:
    parser = TraceParser()
    parser.feed(TEMPLATE.read_text(encoding="utf-8"))
    scripts = [script for script in parser.scripts if "data-diagram-trace" in script["names"]]  # type: ignore[operator]
    if len(scripts) != 1:
        raise RuntimeError("template-trace.html must contain exactly one data-diagram-trace controller")
    return normalized("".join(scripts[0]["body"]))  # type: ignore[arg-type]


def check_trace(source: str, node_ids: set[str], edge_ids: set[str], has_dashed: bool) -> list[str]:
    parser = TraceParser()
    parser.feed(source)
    if not parser.scripts and not parser.roots:
        return []
    errors: list[str] = []
    if len(parser.scripts) != 1:
        errors.append(f"trace layer needs exactly one script; found {len(parser.scripts)}")
    for script in parser.scripts:
        if script["names"] != ["data-diagram-trace"] or script["values"].get("data-diagram-trace") not in ("", None):  # type: ignore[union-attr]
            errors.append("trace script must carry only the data-diagram-trace attribute")
            continue
        if not script["closed"]:
            errors.append("trace script must be closed")
            continue
        if normalized("".join(script["body"])) != canonical_trace_controller():  # type: ignore[arg-type]
            errors.append("trace script must exactly match the controller in template-trace.html")
    if parser.roots != 1:
        errors.append(f"expected exactly one data-trace-root; found {parser.roots}")
    elif not parser.root_before_svg:
        errors.append("the diagram SVG must sit inside the data-trace-root")
    if len(parser.controls) != 1:
        errors.append("trace layer needs one data-trace-controls group")
    elif "hidden" not in parser.controls[0]:
        errors.append("data-trace-controls must ship hidden so the no-JS frame stays static")
    if len(parser.statuses) != 1:
        errors.append("trace layer needs one data-trace-status")
    else:
        status = parser.statuses[0]
        if status.get("role") != "status" or status.get("aria-live") != "polite" or status.get("aria-atomic") != "true":
            errors.append("data-trace-status needs role=status, aria-live=polite and aria-atomic=true")
    if set(parser.selects) != node_ids or len(parser.selects) != len(node_ids):
        errors.append("every principal needs exactly one data-trace-select button, and nothing else")
    if not parser.revokes:
        errors.append("trace layer needs at least one data-trace-revoke button")
    unknown = sorted(set(parser.revokes) - edge_ids)
    if unknown:
        errors.append(f"data-trace-revoke names unknown edges: {unknown}")
    if has_dashed and parser.intro != 1:
        errors.append("a diagram with dashed arrows needs one data-trace-intro toggle")
    if not has_dashed and parser.intro:
        errors.append("data-trace-intro is only for diagrams with dashed arrows")
    return errors


def check_joins(svg, parents, nodes, edges, joins, accents) -> list[str]:
    errors: list[str] = []
    if len(joins) > MAX_JOINS:
        errors.append(f"at most {MAX_JOINS} all-of joins; found {len(joins)}")
    marks: dict[str, ET.Element] = {}
    for mark in (element for element in svg.iter() if "data-gv-join-mark" in element.attrib):
        node_id = mark.get("data-gv-join-mark", "")
        if node_id not in joins:
            errors.append(f"join mark {node_id!r}: only a data-gv-join=\"all\" principal carries a join mark")
            continue
        if node_id in marks:
            errors.append(f"join mark {node_id!r}: one join mark per principal")
        marks[node_id] = mark
    for node_id in sorted(joins):
        cx, cy, r, _ = nodes[node_id]
        incoming = {edge_id: edge for edge_id, edge in edges.items() if edge["to"] == node_id}
        if any(edge["kind"] == "introduce" for edge in incoming.values()) or any(edge["carries"] == node_id for edge in edges.values()):
            errors.append(f"{node_id}: an all-of principal cannot be reached by an introduction")
        if len(incoming) < 2:
            errors.append(f"{node_id}: an all-of principal needs at least two arrows in")
        mark = marks.get(node_id)
        if mark is None:
            errors.append(f"{node_id}: an all-of principal needs a data-gv-join-mark arc")
            continue
        if moved(mark, parents):
            errors.append(f"join mark {node_id!r}: join marks may not be positioned by transform")
        if local(mark.tag) != "path" or mark.get("fill", "") != "none" or not mark.get("stroke") or mark.get("stroke-dasharray"):
            errors.append(f"join mark {node_id!r}: a join mark is an unfilled, solid-stroked <path>")
        if mark.get("stroke", "").lower() in accents:
            errors.append(f"join mark {node_id!r}: the accent belongs to gaps, not join marks")
        match = ARC_RE.fullmatch(mark.get("d", ""))
        if not match:
            errors.append(f"join mark {node_id!r}: the arc must be a single absolute 'M x,y A r,r 0 large sweep x,y'")
            continue
        x1, y1, rx, ry, large, sweep, x2, y2 = (float(value) for value in match.groups())
        if rx != ry or not JOIN_GAP_RANGE[0] <= rx - r <= JOIN_GAP_RANGE[1]:
            errors.append(f"join mark {node_id!r}: the arc is circular and sits {JOIN_GAP_RANGE[0]}-{JOIN_GAP_RANGE[1]}px outside the rim")
            continue
        if any(abs(math.dist(point, (cx, cy)) - rx) > RIM_TOLERANCE for point in ((x1, y1), (x2, y2))):
            errors.append(f"join mark {node_id!r}: the arc must be centred on {node_id}")
            continue
        start = math.atan2(y1 - cy, x1 - cx)
        end = math.atan2(y2 - cy, x2 - cx)
        if not sweep:
            start, end = end, start
        span = (end - start) % math.tau
        if bool(large) != (span > math.pi):
            errors.append(f"join mark {node_id!r}: the large-arc flag does not match the arc's span")
        for edge_id, edge in sorted(incoming.items()):
            tip = edge["segments"][-1][1]
            offset = (math.atan2(tip[1] - cy, tip[0] - cx) - start) % math.tau
            if not JOIN_MARGIN <= offset <= span - JOIN_MARGIN:
                errors.append(f"join mark {node_id!r}: the arc must cross the tip of {edge_id}")
    return errors


def check_source(source: str) -> list[str]:
    match = SVG_RE.search(source)
    if not match:
        return ["missing SVG"]
    try:
        svg = ET.fromstring(match.group())
    except ET.ParseError as exc:
        return [f"invalid SVG: {exc}"]
    if svg.get("data-diagram-type") != "granovetter":
        return ["SVG must declare data-diagram-type=granovetter"]
    parents = {child: parent for parent in svg.iter() for child in parent}
    errors: list[str] = []
    # A branded skin declares its accent once; the gap rule follows it.
    accents = ACCENTS | {value.lower() for value in ACCENT_DECL_RE.findall(source)}

    nodes: dict[str, tuple[float, float, float, str]] = {}
    joins: set[str] = set()
    for group in (element for element in svg.iter() if "data-gv-node" in element.attrib):
        node_id = group.get("data-gv-node", "")
        label = group.get("data-gv-label", "").strip()
        if not node_id or node_id in nodes:
            errors.append(f"blank or duplicate principal id {node_id!r}")
            continue
        circle = styled(group, "circle")
        if local(group.tag) != "g" or circle is None:
            errors.append(f"{node_id}: a principal is a <g> holding a stroked <circle>")
            continue
        cx, cy, r = (number(circle.get(key)) for key in ("cx", "cy", "r"))
        if any(math.isnan(value) for value in (cx, cy, r)) or not MIN_RADIUS <= r <= MAX_RADIUS:
            errors.append(f"{node_id}: circle radius must be {MIN_RADIUS}-{MAX_RADIUS}")
            continue
        words = text_of(group)
        if not label or any(word not in words for word in label.split()):
            errors.append(f"{node_id}: data-gv-label must match the name drawn in the circle")
        if moved(group, parents):
            errors.append(f"{node_id}: principals may not be positioned by transform")
        nodes[node_id] = (cx, cy, r, label)
        if "data-gv-join" in group.attrib:
            if group.get("data-gv-join") != "all":
                errors.append(f'{node_id}: data-gv-join only takes the value "all"')
            else:
                joins.add(node_id)
    if not 2 <= len(nodes) <= MAX_NODES:
        errors.append(f"expected 2 to {MAX_NODES} principals; found {len(nodes)}")

    edges: dict[str, dict[str, object]] = {}
    for element in (element for element in svg.iter() if "data-gv-edge" in element.attrib):
        edge_id = element.get("data-gv-edge", "")
        src, dst, kind = element.get("data-gv-from", ""), element.get("data-gv-to", ""), element.get("data-gv-kind", "")
        if not edge_id or edge_id in edges:
            errors.append(f"blank or duplicate edge id {edge_id!r}")
            continue
        if kind not in KINDS:
            errors.append(f"{edge_id}: data-gv-kind must be one of {sorted(KINDS)}")
        if src not in nodes or dst not in nodes or src == dst:
            errors.append(f"{edge_id}: data-gv-from and data-gv-to must name two different principals")
            continue
        carries = element.get("data-gv-carries", "")
        if kind == "introduce" and (carries not in nodes or carries == dst):
            errors.append(f"{edge_id}: an introduce edge must carry a principal other than its target")
        if kind != "introduce" and carries:
            errors.append(f"{edge_id}: only introduce edges carry a reference")
        dashed = bool(element.get("stroke-dasharray"))
        if kind == "held" and dashed:
            errors.append(f"{edge_id}: a held permission is drawn solid")
        if kind in {"obtain", "introduce"} and not dashed:
            errors.append(f"{edge_id}: a one-action-away arrow is drawn dashed")
        if not element.get("marker-end", "").startswith("url(#arrow"):
            errors.append(f"{edge_id}: arrows need an arrow marker at the end")
        if moved(element, parents):
            errors.append(f"{edge_id}: arrows may not be positioned by transform")
        segments = edge_segments(element)
        if not segments:
            errors.append(f"{edge_id}: arrow path must use absolute M/L/H/V/Q commands")
            continue
        start, end = segments[0][0], segments[-1][1]
        sx, sy, sr, _ = nodes[src]
        tx, ty, tr, _ = nodes[dst]
        if abs(math.dist(start, (sx, sy)) - sr) > RIM_TOLERANCE:
            errors.append(f"{edge_id}: arrow must start on the rim of {src}")
        if not tr - 1 <= math.dist(end, (tx, ty)) <= tr + RIM_TOLERANCE:
            errors.append(f"{edge_id}: arrow must end on the rim of {dst}")
        edges[edge_id] = {"kind": kind, "segments": segments, "carries": carries, "from": src, "to": dst}
    introductions = sum(1 for edge in edges.values() if edge["kind"] == "introduce")
    if introductions > MAX_INTRODUCTIONS:
        errors.append(f"at most {MAX_INTRODUCTIONS} introductions; found {introductions}")
    if not 1 <= len(edges) <= MAX_EDGES:
        errors.append(f"expected 1 to {MAX_EDGES} arrows; found {len(edges)}")

    gates = [element for element in svg.iter() if "data-gv-gate" in element.attrib]
    gate_ids: set[str] = set()
    gated: set[str] = set()
    gaps = 0
    for gate in gates:
        gate_id, edge_id, state = gate.get("data-gv-gate", ""), gate.get("data-gv-on", ""), gate.get("data-gv-state", "")
        if not gate_id or gate_id in gate_ids:
            errors.append(f"blank or duplicate gate id {gate_id!r}")
        gate_ids.add(gate_id)
        if state not in STATES:
            errors.append(f"{gate_id}: data-gv-state must be one of {sorted(STATES)}")
        if edge_id not in edges:
            errors.append(f"{gate_id}: data-gv-on must name an arrow")
            continue
        if edge_id in gated:
            errors.append(f"{gate_id}: one gate per arrow; {edge_id} already has one")
        gated.add(edge_id)
        rect = styled(gate, "rect")
        if rect is None or any(math.isnan(value) for value in box(rect)):
            errors.append(f"{gate_id}: a gate is a <g> holding a stroked <rect>")
            continue
        if not text_of(gate):
            errors.append(f"{gate_id}: a gate names its control")
        if not pierces(edges[edge_id]["segments"], box(rect)):
            errors.append(f"{gate_id}: the gate must sit on a straight run of {edge_id}")
        if moved(gate, parents):
            errors.append(f"{gate_id}: gates may not be positioned by transform")
        dashed = bool(rect.get("stroke-dasharray"))
        if state == "control" and dashed:
            errors.append(f"{gate_id}: a control in place is drawn solid")
        if state in {"missing", "gap"} and not dashed:
            errors.append(f"{gate_id}: a missing control or gap is drawn dashed")
        if state == "gap":
            gaps += 1
            if rect.get("stroke", "").lower() not in accents:
                errors.append(f"{gate_id}: a focal gap uses the accent stroke")
        elif rect.get("stroke", "").lower() in accents:
            errors.append(f"{gate_id}: only a focal gap may use the accent")
    if len(gates) > MAX_GATES:
        errors.append(f"at most {MAX_GATES} gates; found {len(gates)}")
    if gaps > MAX_GAPS:
        errors.append(f"at most {MAX_GAPS} focal gaps; found {gaps}")

    chips: dict[str, ET.Element] = {}
    for chip in (element for element in svg.iter() if "data-gv-chip" in element.attrib):
        edge_id = chip.get("data-gv-chip", "")
        if edge_id not in edges or edges[edge_id]["kind"] != "introduce":
            errors.append(f"chip {edge_id!r}: a carried-reference chip belongs to an introduce arrow")
            continue
        if edge_id in chips:
            errors.append(f"chip {edge_id!r}: one chip per introduce arrow")
        chips[edge_id] = chip
        rect = styled(chip, "rect")
        carried = nodes.get(str(edges[edge_id]["carries"]))
        if rect is None or not pierces(edges[edge_id]["segments"], box(rect)):
            errors.append(f"chip {edge_id!r}: the chip must sit on a straight run of its arrow")
        if carried and carried[3] not in text_of(chip):
            errors.append(f"chip {edge_id!r}: the chip must name the carried principal ({carried[3]})")
        if moved(chip, parents):
            errors.append(f"chip {edge_id!r}: chips may not be positioned by transform")
    for edge_id, edge in edges.items():
        if edge["kind"] == "introduce" and edge_id not in chips:
            errors.append(f"{edge_id}: an introduce arrow needs a chip naming what it carries")

    errors += check_joins(svg, parents, nodes, edges, joins, accents)

    for label in (element for element in svg.iter() if "data-gv-for" in element.attrib):
        if label.get("data-gv-for") not in edges:
            errors.append(f"label {label.get('data-gv-for')!r}: data-gv-for must name an arrow")

    has_dashed = any(edge["kind"] != "held" for edge in edges.values())
    errors += check_trace(source, set(nodes), set(edges), has_dashed)
    return errors


def check(path: Path) -> list[str]:
    return check_source(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true", help="check shipped Granovetter examples")
    args = parser.parse_args()
    paths = sorted(ASSETS.glob("example-granovetter*.html")) if args.all else args.paths
    if not paths:
        parser.error("provide files or --all")
    failed = False
    for path in paths:
        errors = check(path)
        if errors:
            failed = True
            for error in errors:
                print(f"{path}: {error}", file=sys.stderr)
        else:
            print(f"OK {path}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
