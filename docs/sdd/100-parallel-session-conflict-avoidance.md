# SDD-100 — parallel-session conflict avoidance (merge=union registries + per-session number bands)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: the recurring parallel-session merge conflicts (the SDD-070 number collision + the INDEX/mandate append conflicts observed 2026-07-09 across 3 concurrent sessions)
> Derived from: operator directive 2026-07-09 ("resolve the conflicts and think of a new way so that we stop having conflict, we are working 3 sessions at the same time"); picked per-session number bands + `.gitattributes merge=union`.

## Mission

Stop the merge conflicts that arise when **3 sessions work sovereign-os in parallel** (the
Memory-OS / recover-projects session, the cockpit app-shell / header-sidemenu session, the
science-tools session), each on its own branch merging to `main`. This SDD is **SDD-100** —
the first entry in this session's new number band, so it bootstraps the very scheme it
defines.

## Problem

Every increment appends to the same handful of **monotonic shared "registry" files**, which
produces two independent conflict classes — both hit repeatedly on 2026-07-09:

1. **Text-append conflicts.** Each increment appends a row at the end of `docs/sdd/INDEX.md`,
   `docs/standing-directives/2026-05-17-operator-mandate.md`, `docs/src/lifecycle/ongoing.md`,
   `docs/observability/dashboards/README.md`, `docs/decisions.md`. Two branches both appending
   "the next row" → a 3-way git conflict even though the rows are logically independent.
2. **Number collisions.** Each session independently picks "the next free SDD-NNN / E11.M##"
   → two sessions pick the same number (SDD-070 collided between this session's memory-janitor
   and the science-tools warp panel; the app-shell earlier took 067/068 this session had to
   renumber around).
3. **Hardcoded-count churn.** Magic integers like "18→19 recurrent hooks" / "N timers" that
   two sessions both bump → one ends up wrong.

## Grounded design

- **`.gitattributes merge=union`** on the append-only registries — git's built-in `union`
  merge driver keeps BOTH sides' added lines on a merge (no config, no manual conflict). This
  directly fixes class 1 (a `git merge origin/main` would auto-resolve INDEX + mandate). Union
  keeps both `| 070 |` rows if two sessions pick 070, so it is paired with the bands (below)
  that guarantee distinct numbers.

- **Per-session number bands** (`docs/sdd/README.md`) — each session picks the next free number
  WITHIN its own disjoint band, so a collision is structurally impossible. Bands start ABOVE
  the current max (SDD-071 / E11.M38) so nothing already-merged is renumbered; gaps are fine
  (the INDEX lint maps file↔row by number, not by sequence).

  | Session / workstream | SDD band | mandate E11 band |
  |---|---|---|
  | recover-projects (Memory-OS + infra, this session) | 100–199 | E11.M100–M199 |
  | header-sidemenu (cockpit app-shell) | 200–299 | E11.M200–M299 |
  | science-tools | 300–399 | E11.M300–M399 |
  | compute-plane (multi-model / GPU) | 900–949 | E11.M900–M949 |
  | phase-1 audit / improvement | 950–999 | E11.M950–M999 |
  | cockpit-wasm bridge (F-2026-001) | 800–899 | E11.M800–M899 |

  > **Amendment (2026-07-12):** the single "any new / general / unassigned → 900–999" catch-all was itself a
  > collision source — TWO unassigned sessions (compute-plane + the phase-1 audit) each grabbed the next free
  > 900-number and collided on SDD-900. **Fix: every unassigned session claims its OWN disjoint sub-band and
  > records it as a row above** (compute-plane 900–949, phase-1 audit 950–999). A new unassigned session takes
  > the next free 100-wide block (e.g. `800–899`, then `600–699`, …) — never the shared catch-all. The
  > `test_sdd_numbers_unique` lint is the backstop; the disjoint bands make a collision structurally impossible.

  > **Amendment (2026-07-13):** it happened again — the **cockpit-wasm bridge** session (F-2026-001) took
  > **SDD-969**, inside the phase-1-audit band (950–999), colliding with the audit session's own SDD-969
  > (standing-mandate navigation). Root cause was twofold: (1) the new session drew from the audit band instead
  > of claiming its own disjoint block per the rule above; (2) the `test_sdd_numbers_unique` backstop passed on
  > the cockpit PR because that branch was cut before the audit's 969 merged — a **stale-green** merge (GitHub
  > merged without re-running the lint against the post-merge tree). **Resolution:** the cockpit-wasm session is
  > assigned its own **800–899** block (row above); the audit session yielded its 969 → **975** (its own band);
  > the cockpit-wasm 969 is grandfathered (its future SDDs use 800–899). **Prevention for the stale-green class:**
  > enable GitHub branch protection *"require branches to be up to date before merging"* on `main` so a PR must
  > re-run `test_sdd_numbers_unique` against the current tree before it can merge — the operator setting that
  > makes the existing lint actually block cross-session number reuse. (Operator decision 2026-07-13; the
  > 950–969-for-cockpit split first proposed was corrected to 800–899 because 950–968 are already audit-consumed
  > and the audit session already owns all of 950–999 per the 2026-07-12 amendment.)

- **De-magic the counts** — the count-churn surfaces drop their hardcoded integers (the real
  assertion is already glob/set-based): `test_recurrent_hooks_contract.py` (the
  `sorted(glob) == sorted(EXPECTED)` check is unchanged; the "Exactly N" integers leave the
  docstring/error) + `ongoing.md` prose ("N timers" → derived phrasing).

- **Cross-session documentation** — a "Parallel-session conventions" section in `AGENTS.md`
  (the cross-tool contract every session reads) points at the band table + the union mechanism,
  so the OTHER two sessions inherit the scheme by pulling `main`.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-100-A | Conflict-avoidance scheme. | **answered (operator, 2026-07-09): per-session number bands + `.gitattributes merge=union` on the append-only registries.** |
| Q-100-B | Band assignment. | **answered: recover-projects 100–199, header-sidemenu 200–299, science-tools 300–399, general 900–999 (SDD + E11.M##); the historical 064–071 / M32–M38 stay as-is.** |
| Q-100-C | The single-line lint LISTs (`EXPECTED_RECURRENT_HOOKS`, `EXEMPT_PATTERNS`). | **de-magic the counts now; unioning or fragmenting the `.py` lists (multi-line-tuple-safe) is Stage-N — those conflict only when two sessions add a hook/metric in the same window (rare).** |

## Non-goals (Stage N)

- Unioning or fragmenting the Python lint list files (`EXPECTED_RECURRENT_HOOKS`,
  `EXEMPT_PATTERNS`) — multi-line entries make `.py` union risky; deferred.
- A generator that renders INDEX/mandate from per-SDD fragment files (the "fragment the
  registries" alternative — larger refactor, not chosen).
- Automated band-boundary enforcement in lint (a test asserting each session's files fall in
  its band) — the band doc is convention-first for now.

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 100 + mandate E11.M100.
- **Stage 1:** `.gitattributes` (union) + `docs/sdd/README.md` (band table + protocol) +
  `AGENTS.md` (conventions section) + de-magic the counts.

## Safety invariants

`merge=union` only affects MERGE behavior on the named append-only markdown registries — it
never changes runtime behavior, never touches code, and keeps both sides' content (no data
loss). The bands are additive convention (historical numbers untouched). De-magicing the
counts removes ONLY the non-asserted magic integers — the glob/set-equality assertions that
actually lock the recurrent-hook set are unchanged. No contract yaml change; no
lifecycle/security change. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/sdd/README.md` — the band-allocation table + "add an SDD in your band" protocol.
- `.gitattributes` — the union entries.
- `AGENTS.md` — the "Parallel-session conventions" section.
- `tests/lint/test_sdd_index_consistency.py` — the file↔row-by-number lint the bands satisfy.
- The 2026-07-09 incident: the SDD-070 collision (science-tools warp vs this session's
  memory-janitor, renumbered to SDD-071) + the INDEX/mandate merge conflicts.
