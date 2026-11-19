# ADR 0020: Trace is the second pinned controller

**Status:** Proposed
**Date:** 2026-11-19
**Amends:** ADR 0001

## Context

ADR 0001 keeps output script-free by default and admits exactly one reviewed controller, for motion. A Granovetter diagram (ADR 0019) answers a question the static frame can show but not answer per reader: *what can this principal reach, and what changes if this permission goes away?* Reach is a graph walk. With six principals and seven arrows the reader can walk it by eye, but checking each principal against each "what if" is tedious and easy to get wrong. That is exactly the review an access diagram exists to support.

## Decision

Admit a second pinned controller, `assets/template-trace.html`, under ADR 0001's rules:

- One script per file. A file is traced or animated, never both.
- The script tag carries only `data-diagram-trace`, and its body byte-matches the template. `lint-skin.py` (SHA-256), `self_check.py` and `verify-granovetter.py` (string equality) all enforce it.
- The controller reads only `data-gv-*` bindings and `data-trace-*` controls inside a `[data-trace-root]`. It toggles classes and `aria-pressed`, unhides the controls and writes one polite live region. It makes no network requests, does not add markup, and stores nothing.
- The static frame is complete without it. Controls ship `hidden`; print hides them; transitions run only under `prefers-reduced-motion: no-preference`.

## Consequences

- A traced Granovetter diagram lets a reader hover a principal to see its reach, include one-action-away arrows, and revoke an arrow to see what drops out, with every state announced to assistive technology.
- Behavior changes to tracing are changes to `template-trace.html`, reviewed once and re-propagated verbatim, exactly as with motion.
- Trace is scoped to Granovetter diagrams. Any other interaction is still out of scope.
