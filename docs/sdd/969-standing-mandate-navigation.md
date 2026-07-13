# SDD-969 — navigation companion for the 640 KB standing-directive

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-039** (giant single-file standing directive), at the finding's explicit "at minimum" bar.
> Mandate module: **E11.M969** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

`docs/standing-directives/2026-05-17-operator-mandate.md` is ~640 KB. Its bulk is single mandate-table rows that are each multi-KB (the per-SDD `E11.M###` cross-link rows), so the file is slow to open and effectively undiffable as one blob. F-2026-039 asked to "split by section with an index, preserving verbatim content byte-for-byte (sacrosanct), **or at minimum add a TOC + anchor map companion**."

This SDD takes the **"at minimum" path deliberately**, for two reasons specific to this file:

1. **Sacrosanct byte-risk.** Section 1 is the operator mandate reproduced *verbatim* across every `/goal` — the highest-value content in the repo to preserve byte-for-byte. Splitting it across files is a mechanical operation with a real chance of altering a byte of sacrosanct content; the payoff (LOW-severity readability) doesn't justify that risk.
2. **It is the most-contended file in the repo.** Every audit-session SDD (and parallel sessions) appends an `E11.M###` row here. A split — or a per-row-synced index — would turn the hottest file into a CI-coupling point across sessions, cutting against the operator's paramount collision-avoidance directive.

## What this SDD builds

### 1. `…-operator-mandate-NAVIGATION.md` — a section-level map

A companion that reproduces **no content** — only a structural map so a reader/agent can jump to the right place without loading 640 KB:

- the 6 top-level sections (`## 1`…`## 6`) with anchor links + a one-line "what's inside";
- the §1 sub-directives (§1.0–§1h — the verbatim operator pastes);
- the §3 epics E1–E11 (noting **Epic E11 holds the `E11.M###` mandate-module rows**);
- a "how to find a specific `E11.M###` module" note (search the file for the id; cross-linked to the SDD INDEX + generated catalog).

### 2. `tests/lint/test_mandate_navigation.py` — the completeness contract

Fails CI if any `##`/`###` section heading in the mandate is added, renamed, or removed without being reflected in the NAVIGATION companion — so the map can't silently diverge from the file's structure. It checks **headings only**, not the `E11.M###` table rows: adding a mandate row does not change a heading, so routine per-SDD mandate-row appends need no update here — keeping the contract **off the hot path** of the most-appended file.

## Verification

- `git status` on the mandate `.md`: **unmodified** by this change except the normal single `E11.M969` row append (the established agent-append location under Epic E11 in §3); the sacrosanct §1 verbatim content is byte-untouched.
- `python3 -m pytest tests/lint/test_mandate_navigation.py` — **3 passed** (companion exists + links the mandate; every one of the mandate's section headings is navigable).
- `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Splitting the mandate into multiple files** — deliberately not done (sacrosanct byte-risk + hot-file collision); the finding's primary option is declined in favor of its "at minimum" option, with the rationale above.
- **A per-`E11.M###`-row synced index** — would CI-couple the most-appended file across sessions; the map is section-level on purpose.
- **Editing any §1 verbatim content** — untouched; the companion is navigation only.

## Safety invariants

Adds a navigation companion + a read-only lint; the sacrosanct mandate content is not modified (only the routine `E11.M969` cross-link row is appended, as every audit SDD does). No crate code, no runtime behavior, no gateway touch. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/standing-directives/2026-05-17-operator-mandate.md` — the mandate (single sacrosanct source)
- `docs/standing-directives/2026-05-17-operator-mandate-NAVIGATION.md` — the map
- `tests/lint/test_mandate_navigation.py` — the completeness contract
- `docs/sdd/INDEX.md` + `docs/src/sdd-catalog.md` — the per-SDD catalogs the mandate rows cross-reference
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-039 (source)
- SDD-958 (mdbook catalog) / SDD-952 (context counts) — sibling doc-navigability + drift-guard contracts
- SDD-100 — the per-session number-band convention (phase-1-audit 950–999 sub-band)
