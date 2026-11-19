# ADR 0019: Granovetter is a capability-reach grammar

**Status:** Proposed
**Date:** 2026-11-19

## Context

People use Diagram Design to explain access: who can deploy, which service principal can write to the directory, what a leaked CI token reaches. Those figures currently land in Dependency graph or Architecture. Both draw boxes and arrows, but neither says what an access review needs to say:

- **Reach is transitive.** If A holds B and B holds C, A reaches C. A dependency graph's edges do not compose that way, and an architecture diagram has no walk at all.
- **Not every arrow is held.** Some permissions are one action away: assuming a role, activating an eligible assignment, adding a credential to an app you administer.
- **Introductions.** The defining move in capability systems is handing someone a reference to a third party (consenting an app to an API, editing a role's trust policy). Granovetter and Miller drew it as a message carrying a reference; no type here can.
- **Controls sit on paths, not on nodes.** Reviews, MFA, branch protection and conditional access gate a specific arrow, and a missing control is as important as a present one.

## Decision

Add **Granovetter** as visual type #52.

Principals are circles. Arrows are references in three kinds: `held` (solid), `obtain` (dashed) and `introduce` (dashed, with a pill chip naming the carried principal). Controls are gate boxes straddling a straight run of the arrow they guard, in three states: `control` (solid), `missing` (dashed) and `gap` (dashed accent, at most two per diagram, the focal elements). Every element is bound with `data-gv-*` attributes, and `scripts/verify-granovetter.py` checks that arrows start and end on their circles' rims, that solid versus dashed matches the declared kind, that chips name a real principal, that gates sit on their own arrow, the focal budget, and that no bound element is moved by a transform.

The shipping set is `references/type-granovetter.md`, three static examples (light, dark, full editorial) generated from one scene by `scripts/build-granovetter-examples.py`, a traced variant (ADR 0020), the gallery tab and README entries, a complexity-budget row, a canonical screenshot, and the checker with adversarial tests.

## Consequences

- Access reviews, blast-radius questions and privilege-escalation paths get a grammar whose arrows mean what the reader thinks they mean.
- Dependency graph stays the type for "depends on" and keeps its cycle grammar; requests about calls and data movement still route to Architecture, Data flow or Sequence.
- Accent goes on gaps, never on principals, matching the dependency graph's rule that the accent is the problem rather than the actors.
