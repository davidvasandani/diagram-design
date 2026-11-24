# Granovetter Diagram

**Best for:** who can act on what, and through whom. A Granovetter diagram (the capability diagram Mark Miller adapted from Mark Granovetter's social-network figures) draws principals as circles and the references they hold as arrows. Use it to map real permissions and the controls that gate them: an access review, a blast-radius question ("if this CI token leaks, what can it reach?"), a privilege-escalation path, or a before/after of a control change.

The grammar a dependency graph lacks: **reach is transitive along held arrows**, an arrow can be **one action away** instead of held, an **introduction** hands a third principal's reference to someone else, and **controls sit on the arrow they gate**. If the edges mean "imports" or "calls", use [Dependency graph](type-dependency.md). If you need who-does-what over time, use [Sequence](type-sequence.md).

## Vocabulary

| Element | Markup | Drawn as |
|---|---|---|
| Principal | `<g data-gv-node="id" data-gv-label="Name">` holding a paper-mask circle and a stroked circle | Circle, `r` 48–64 (24–72 allowed). White fill and `ink` stroke; the target resource uses `ink @ 0.05` fill |
| Held permission | `<path data-gv-edge data-gv-from data-gv-to data-gv-kind="held">` | Solid `muted` arrow |
| One action away | `data-gv-kind="obtain"` | Dashed `5,4` arrow: the source can acquire this reference itself (assume a role, add a credential, activate PIM) |
| Introduction | `data-gv-kind="introduce" data-gv-carries="id"` | Dashed arrow from the introducer to the recipient, with a **carried-reference chip** (`<g data-gv-chip="edge-id">`, pill `rx=9`) naming the principal being handed over. The classic Granovetter message: Alice sends Bob a reference to Carol |
| Control | `<g data-gv-gate="id" data-gv-on="edge-id" data-gv-state="control">` | `rx=2` box straddling a straight run of its arrow, solid `muted` stroke, mono text naming the control |
| Missing control | `data-gv-state="missing"` | Same box, dashed `4,3`, `ink @ 0.02` fill. A control that belongs on this path and does not exist |
| Focal gap | `data-gv-state="gap"` | Dashed `accent` box on `accent-tint`; its held arrow and label go `accent` too. **Max 2** |
| All-of principal | `data-gv-join="all"` on the principal, plus one `<path data-gv-join-mark="id" d="M … A …">` | An unfilled `ink` arc 8–20px outside the rim (12 by default) crossing the tip of every arrow into it: the principal needs **all** of them, not any one. Use it for two-party controls such as author plus approver |
| Edge label | `<g data-gv-for="edge-id">` | Masked 8px mono caps, 6–10px clear of the stroke (§6 rule 2) |

Reach is the set of circles you can walk to from a principal along held arrows. Dashed arrows extend it only when the reader asks "one action away": an `obtain` arrow adds its target; an `introduce` arrow adds the carried principal to its recipient's reach, and only matters to someone who already reaches both the introducer and the recipient. An all-of principal is reached only when every arrow into it is usable from what is already reached; it may not receive or be carried by an introduction.

## Layout conventions

- **Actors left, resources right.** Principals that start chains (people, groups, roles that act) sit in a left column; the resource the diagram is about sits at the right edge, larger (`r=64`) and filled. Intermediaries (CI runners, service principals, roles) sit in the middle. Use `doc-wide` (`0 0 1280 720`) — the gate boxes need horizontal runway.
- **Arrows start and end on the rim.** An arrow leaves its source circle at the rim and its tip lands on the target's rim (stop 1px short so the marker touches it). For an attach point off the circle's centre line, the rim x is `cx ± √(r² − dy²)`.
- **Gates need a straight run.** Route each gated arrow so a horizontal or vertical segment is at least the gate's width plus 16px, and centre the gate on it. The connector visibly enters and leaves the box; the box is the arrow's checkpoint, not a node.
- **Two arrows between one pair** (open a PR vs merge it) run parallel, 40px apart, each with its own gate — that is usually the story.
- **The chip** sits on the last straight run before the recipient, so it reads as what arrives.
- All six §6 connector rules apply. Gates and chips are not nodes for rule 5: an arrow passes through its own gate by design, never through another arrow's.
- Paint order: arrows → labels → gates → chips → principals. Principals last, so arrow ends tuck under the paper mask.

## Honest-data rule

Every count and state is read from the source system, not inferred: role holders and eligibility from the directory, branch protection and CODEOWNERS from the repository, policy from the policy engine. When a gap is inferred from configuration rather than tested, the caption says so. `scripts/verify-granovetter.py` gates the markup: rim endpoints, solid vs dashed by kind, carried chips that name a real principal, gates that straddle their own arrow, the 2-gap focal budget, names and sublabels that fit inside their circle, and no transforms on bound elements. The label fit there is a conservative estimate; `scripts/test-granovetter-browser.py` measures the rendered boxes in Chromium and holds them 2px inside the rim.

## Interactive trace (optional)

The static diagram must carry the whole meaning. When a reader benefits from exploring reach — "what can Contributors get to?", "what if we revoke this?" — add the pinned trace controller from `assets/template-trace.html` ([trace.md](trace.md)). It highlights everything reachable from a hovered or selected principal, can include one-action-away arrows, and revokes arrows to show what falls out of reach. ADR 0020 admits it as the second pinned controller; copy it verbatim.

## Complexity budget

| Limit | Rule |
|---|---|
| Max principals | 8 |
| Max arrows | 12 |
| Max gates | 6, one per arrow |
| Max focal gaps (accent) | 2 |
| Max introductions | 2 |
| Max all-of joins | 2, each with at least two arrows in |

Over budget: merge principals that hold the same arrows into one circle with a count in the sublabel (`5 active · 8 eligible`), or split into an overview and a per-resource detail.

## Anti-patterns

- Arrows that mean "depends on" or "calls" — that is a dependency graph or an architecture diagram.
- A gate box floating beside an arrow instead of on it; the reader cannot tell which path it guards.
- Accent on the principals. Accent belongs to the gaps, not to the people.
- Dashed arrows with no legend entry, or a held permission drawn dashed to look less alarming.
- An introduction without its chip — it reads as an ordinary grant and loses the "who hands what to whom" meaning.
- Two arrows into a principal that needs both, drawn without the join arc — the trace will claim either one reaches it.
- Counts from a ticket or memory instead of the source system.
- Reach shown only in the interactive layer. The static frame has to show every arrow.

## Examples

- `assets/example-granovetter.html` — minimal light
- `assets/example-granovetter-dark.html` — minimal dark
- `assets/example-granovetter-full.html` — full editorial
- `assets/example-granovetter-traced.html` — minimal light with the trace controller
