# SDD-961 — SDD INDEX status hygiene: drop stale branch refs + a hygiene contract

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-031** (the objective hygiene core; the subjective status-reconciliation is scoped as a follow-up).
> Mandate module: **E11.M961** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

`docs/sdd/INDEX.md` — the operator-discoverable SDD catalog — had collapsed hygiene:

- **71 rows** carried a stale ephemeral feature-branch reference in their provenance column: ``SDD-NNN on branch `claude/recover-projects-b0oT6` ``. That branch (the recover-projects session, SDDs 049–149) merged on 2026-07-11 and the session is dormant — a merged branch name is stale the moment it merges, and it does not belong in a durable catalog.
- The **Status column** had drifted into an undocumented, inconsistent vocabulary (7 distinct words: `draft`/`review`/`scoping`/`accepted`/`active`/`complete` + a `(decision pending)` qualifier) with no legend saying what any of them mean.

## What this SDD builds

### 1. Drop the stale branch refs (provenance made durable)

Each `` SDD-NNN on branch `claude/recover-projects-b0oT6` `` → `SDD-NNN (recover-projects session)` — the ephemeral branch name dropped, the honest **session** provenance kept (mirroring the `(this session)` provenance the audit-session rows use). 71 rows, mechanical, no substantive change to any SDD.

### 2. A Status vocabulary legend (INDEX header)

The header now defines the six status words: `draft` (proposed / in design), `review` (spec reviewed, pending gate), `scoping` (decision package, operator decision pending), `accepted` (design decided), `active` (implementation in progress), `complete` (shipped + verified) — so a reader can tell what a status means and staleness is visible.

### 3. `tests/lint/test_sdd_index_hygiene.py` — the contract

- No INDEX row references a `claude/<slug>` feature branch (nor the `on branch \`claude/…\`` phrase) — a merged branch is stale in a durable catalog.
- Every data row's Status base word is in the documented vocabulary — catches typos + freeform drift.
- The header legend documents each vocabulary word.

So the catalog can't silently re-accrue ephemeral branch cruft or undocumented status words.

## Scope — the objective floor, not the subjective flip

F-2026-031 also asks to reconcile *values* — "merged ⇒ implemented/accepted", i.e. flip the 91 `draft` rows whose work has shipped. That is a **per-SDD judgement** (a committed SDD file can legitimately still be `draft`-stage; "accepted" vs "complete" is the authoring session's / operator's call, and the INDEX rows are owned by several sessions). Mass-flipping them unilaterally would misrepresent other sessions' work and collide with their ownership. So this SDD enforces the **objective floor** — no stale branch refs, a defined vocabulary — and leaves the value-reconciliation to each authoring session against the legend. The lint makes future statuses consistent; it does not presume to relabel merged work.

## Verification

- 71 branch refs replaced; `grep -c recover-projects-b0oT6 docs/sdd/INDEX.md` → 0; no other `claude/<slug>` refs remain.
- `python3 -m pytest tests/lint/test_sdd_index_hygiene.py` — 4 passed (no feature-branch refs; no `on branch` phrase; every Status word in the vocabulary; the legend documents each word).
- `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Mass status-value reconciliation** (draft → accepted/complete for merged SDDs) — per-SDD/operator judgement, deferred (see scope).
- **Adding a status-block date to every row** — the legend + the hygiene lint deliver the "staleness visible" intent; per-row dates can follow.

## Safety invariants

Docs + read-only lint only — no crate code, no runtime behavior, no gateway touch. The branch-ref edit only drops an ephemeral branch name from a dormant session's merged rows (verified merged 2026-07-11), preserving session provenance; it invents nothing and changes no SDD's substance. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/sdd/INDEX.md` — the catalog + the new Status legend
- `tests/lint/test_sdd_index_hygiene.py` — the enforcing lint
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-031 (source)
- SDD-955 / SDD-958 / SDD-959 — the same self-maintaining-contract pattern
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
