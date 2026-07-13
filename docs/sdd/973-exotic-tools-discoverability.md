# SDD-973 — exotic tool-domain discoverability index

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-027** (exotic one-script domains are hidden capabilities), via the docs surface.
> Mandate module: **E11.M973** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

Six `scripts/<domain>/` trees — **science / research / insights / history / weaver / pulse** — each hold a lone specialist entry point that is a real operator capability (each traces to a mandate row or the master spec) but had **no doc, no discoverability page, no index**. On a directory listing they read as orphans; you had to already know they existed. F-2026-027 (OPP) asked to *"surface them (osctl verbs + docs + panel cards) or fold them into their parent domains."*

Investigation (confirmed against the tree): **docs references = 0 for all six domains**. `science` + `weaver` already have operator-API backends (`scripts/operator/science-api.py`, a weaver API) but no documentation; `research` / `insights` / `history` / `pulse` have neither. So the gap is discoverability, and the lightweight surface the finding offers — **docs** — closes it without building new osctl verbs / panels (the heavier options, out of scope for an OPP and riskier).

## What this SDD builds

### 1. `docs/src/exotic-tools.md` — the discoverability index

One page mapping each of the 8 top-level scripts across the 6 domains to its **role** (with operator-named / master-spec traceability), **invocation** (from each script's `argparse`), and **what already wraps it** (science + weaver note their operator-API surface). Wired into `SUMMARY.md` under "Using the box" so it's in the published mdbook. It reproduces no logic — a pointer surface so the capabilities are findable.

### 2. `tests/lint/test_exotic_tools_doc.py` — the completeness contract

Every top-level `*.py` / `*.sh` in the six exotic domains must appear in the index; the doc must name no script that doesn't exist; and `SUMMARY.md` must link the page. So a new exotic-domain capability can't ship undiscoverable, and the index can't drift into ghost references — the same self-maintaining discipline as the binaries-doc (SDD-962) contract. (A domain's `lib/` / `sample/` helpers are excluded — they're not entry points.)

## Verification

- The 6 domains' current docs-reference count is 0 (the gap); after this SDD, all 8 scripts are documented + reachable from the book.
- `python3 -m pytest tests/lint/test_exotic_tools_doc.py` — **3 passed** (doc + SUMMARY link exist; every exotic script documented; no ghost references).
- `ruff` clean; `exotic-tools.md` is in `docs/src/` + linked in SUMMARY, so `build mdbook` includes it; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Building osctl verbs / operator APIs / panel cards for the un-surfaced domains** (research / insights / history / pulse) — the heavier "surface them" options; each is its own feature arc. This closes the OPP via the docs surface the finding also offers.
- **Authoring in the reserved SDD band 300–399 ("science-tools")** — that band is another session's structured home for these; this audit stays in its 950–999 band (SDD-100) and points at 300–399 as the eventual owner.
- **Folding the domains into parents** — the finding's other option; not chosen (the domains are coherent as-is; discoverability was the actual gap).

## Safety invariants

Docs + read-only lint only — no crate code, no script behavior, no runtime, no gateway touch. The index documents scripts the repo already ships (invocation + purpose taken from their own headers + `argparse`); it invents nothing. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/src/exotic-tools.md` — the discoverability index
- `docs/src/SUMMARY.md` — wires it into the book
- `tests/lint/test_exotic_tools_doc.py` — the completeness contract
- `scripts/{science,research,insights,history,weaver,pulse}/` — the documented domains
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-027 (source)
- SDD-962 — the sibling runtime-binaries discoverability + completeness-lint pattern
- SDD-100 — the per-session number-band convention (the 300–399 science-tools band is the eventual structured home)
