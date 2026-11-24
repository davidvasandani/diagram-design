# Trace — interactive reach for Granovetter diagrams

Routed from [type-granovetter.md](type-granovetter.md). Optional. A diagram is static by default (ADR 0001); the trace layer is the second pinned controller, admitted by ADR 0020 for one job: letting a reader explore **reach** in a Granovetter diagram without changing what the static frame says.

## What it does

- **Hover or click a principal** (or press its button) to highlight every principal it reaches along held arrows, the arrows used, and their gates, labels and chips. Everything else dims to 16% opacity. Escape clears.
- **Include one-action-away arrows** adds `obtain` targets and `introduce` hand-offs to the walk.
- **All-of principals** (`data-gv-join="all"`) are reached only when every arrow into them is usable. When some but not all are, the status says so: `Deploy needs both arrows in; 1 reachable.`
- **Revoke** removes an arrow from the walk and fades it, so the reader sees what falls out of reach.
- A polite live region announces the result: `Contributors reaches 3: CI runner, Deploy role, Production.`
- URL parameters make screenshots deterministic: `?trace=<node-id>&intro=1&revoke=<edge-id>,<edge-id>`.

## Contract

The controller lives in `assets/template-trace.html` and is copied **verbatim**. `lint-skin.py`, `self_check.py` and `verify-granovetter.py` all compare it to the template; a hand-edited controller fails every gate. `scripts/test-granovetter-browser.py` runs the controller itself: for every principal, with intro off and on and each arrow revoked in turn, the reach it marks must match an independent model of the rules, and the buttons, Reset and Escape must drive the same state. Per diagram you write only markup and CSS:

1. Wrap the diagram container and controls in one `<div data-trace-root>`.
2. Bind the SVG as the type reference describes (`data-gv-node`, `data-gv-edge`, `data-gv-gate`, `data-gv-for`, `data-gv-chip`, and `data-gv-join` / `data-gv-join-mark` for all-of principals).
3. Ship the controls **hidden** — `<div class="trace-controls" data-trace-controls hidden>` — with one `data-trace-select` button per principal, a `data-trace-intro` checkbox when any arrow is dashed, `data-trace-revoke` buttons for the arrows worth testing, and a `data-trace-reset` button. The controller unhides them.
4. Add `<p data-trace-status role="status" aria-live="polite" aria-atomic="true">` after the controls.
5. Copy the trace CSS block from the template: `.is-dim`, `.is-revoked`, the last-child bottom clearance, transitions only under `prefers-reduced-motion: no-preference`, and `@media print` hiding the controls.
6. One script per file. A diagram is either traced or animated, never both.

## Fallbacks

- **No JavaScript:** the controls stay hidden and the diagram is the complete static frame.
- **Reduced motion:** state changes apply without transitions.
- **Pinned host widgets:** when the trace root is the last block on the page it carries 96px of bottom padding, so the controls can scroll clear of chat or presence widgets a host pins to the bottom corners.
- **Print:** controls and status are hidden and that padding is dropped; whatever trace state is active prints as shown.
- **Keyboard:** every action is a native button or checkbox; principals in the SVG are pointer affordances only, because the SVG is `role="img"`.

## Anti-patterns

- Using trace to reveal arrows the static frame omits.
- A second script, inline event handlers, or editing the controller for one diagram.
- Trace on anything other than a Granovetter diagram. Ordered change is motion's job ([animation.md](animation.md)).
