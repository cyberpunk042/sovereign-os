# SDD-980 — auto-resolve parallel-session SDD conflicts (session identity + a resolver that renumbers, verifies, and warns)

> Status: draft
> Owner: operator-directed 2026-07-13 ("we could have actually useful ones to resolves conflict, automatically and then give a warning if we can't … we know the logic and how to resolve the conflict of numbers and lines"; aggressiveness chosen: **"Auto-apply, verify, warn on doubt"**; + "There should be a way for sessions to identify themselves … even talk to each other / talk to me"; + "a note about what was done … and potentiel further needs"); agent-authored.
> Advances: **F-2026-030-adjacent** — makes the SDD-100 band convention self-healing.
> Mandate module: **E11.M980**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

SDD-100 gives each parallel session a disjoint number band so their `SDD-NNN` /
`E11.M###` numbers never collide, and `.gitattributes merge=union` keeps both
sides' appended registry rows. But a session can still slip and take a number
**outside** its band — it happened twice (a dup `SDD-969`, then a dup `SDD-974`),
each resolved by hand across an `AskUserQuestion` round-trip. The resolution
logic was **deterministic** every time, so it should be automatic. This SDD adds:

1. a **session registry** (`docs/sdd/SESSIONS.md`) — sessions *identify themselves*
   (id → band → branch → purpose), the authoritative map the resolver trusts;
2. the **auto-resolver** (`scripts/git/sdd_conflict_resolver.py`) — on a duplicate
   number it renumbers the out-of-band intruder into its own band, verifies, and
   **warns on doubt**; and
3. a **cross-session ledger** (`docs/sdd/RESOLUTION-LOG.md`) — every auto-fix (or
   un-fixable case) is recorded with what was done and the residual follow-ups;
   also the seed of "sessions talk to each other / to the operator."

## The deterministic rule

Every banded SDD declares its band in its body — `> Number band: **950–999 …`.
That declared range is the file's **authorship signature**, independent of the
number it currently carries. On a duplicate number **N** shared by two files:

- the file whose declared band **contains N** is the rightful owner → keeps N;
- the file whose declared band **does not** is the **intruder** → renumbered into
  the next free slot of *its own* band.

`SESSIONS.md` maps each band to a session, and `tests/lint/test_session_registry.py`
+ `tests/lint/test_sdd_band_declaration_matches_number.py` keep the signal honest
(bands disjoint; every number lands in one band; no file declares a band that
doesn't contain its number — the exact drift that left `SDD-800` stale, fixed here).

## What the resolver does ("auto-apply, verify, warn on doubt")

`scripts/git/sdd_conflict_resolver.py` — stdlib-only; `--check` (report, exit 1 on
unresolved) / `--dry-run` (preview) / `--apply` (default). On `--apply`, for each
duplicated number it:

1. **identifies the intruder** by the declared-band rule (raises *doubt* if no
   single in-band owner, no band declared, or the band is full);
2. **renumbers it in place** — renames the file (+ its own internal `SDD-`/`E11.M`
   refs), and *surgically* renumbers the intruder's **INDEX row** and **mandate
   row**, each identified by its self-declaring last cell (`… (cockpit-wasm
   session)` / `… branch claude/…cockpit-wasm…`) matching the intruder's band —
   never a blind global replace, which would corrupt the owner's identically
   numbered rows;
3. **regenerates** the mdbook SDD catalog + recomputes the `context.md` counts;
4. **verifies** by re-running the uniqueness / band-contiguity / counts lints;
5. on success, **logs** the fix to `RESOLUTION-LOG.md` and leaves everything
   **UNSTAGED** for operator review (a hook never auto-commits);
6. on **any doubt** — ambiguous ownership, band full, or verify still red — it
   **reverts its own changes** (`git checkout`/`clean`) and **warns** with the
   exact manual remediation, and records the attempt in the ledger.

Silent + fast when there is no collision, so the `post-merge` / `post-rewrite`
hooks (`lib/sdd-resolve.sh`) run it on every pull safely.

### Scope line (what it does NOT touch)

- **Lines, not numbers**: registry *line* conflicts are already handled by the
  built-in `merge=union` (zero-config, works in CI + fresh clones — a custom
  merge driver would silently no-op there, a regression); the resolver adds the
  **number** half union can't do, plus surgical row renumber. Prose mentions of
  the old number outside the registries (e.g. a CHANGELOG line) are left
  untouched and flagged in the ledger for a human to repoint — safer than
  guessing which of two same-numbered references a global replace should move.
- No gatewayd / cockpit-crate / code edits — docs + scripts + `.gitattributes`
  only (collision-safe with the parallel sessions).

## Sessions identify themselves — and can talk (the deeper frame)

The root cause of every collision is that sessions were **anonymous and
non-communicating**. `SESSIONS.md` is the first fix: a session declares its band,
branch, and purpose, so tooling (and the operator) can attribute any number to a
session. `RESOLUTION-LOG.md` is the second: because it is `merge=union`,
**any** session — or the operator — can append a note addressed to another
session or to the operator, and every branch keeps every note across merges. The
resolver already uses it that way (each fix names the sessions involved and the
follow-ups). That is the **seed of a session-to-session / session-to-operator
message board**; a fuller bidirectional protocol (threaded, ack/reply, an "inbox"
a session reads on orient) is a natural follow-up, deliberately left out of this
PR to keep it collision-safe and reviewable.

## Verification (real, observed)

- **Live end-to-end** on the real tree: planted a self-declaring cockpit-wasm
  intruder at `SDD-979` (+ INDEX + mandate rows) → `--check` planned `SDD-979 →
  801`; `--apply` renamed the file, renumbered its INDEX + mandate rows,
  regenerated catalog + counts, the owner kept `979`, and the three lints went
  **green**; a `RESOLUTION-LOG` entry was written. Tree then restored.
- **Warn-on-doubt** live: an intruder declaring no band → resolver touched
  nothing and warned with the manual fix (exit 1).
- **`tests/lint/test_sdd_conflict_resolver.py`** — 4 hermetic git-fixture cases:
  happy-path no-op (silent), unambiguous resolve+log, verify-failure reverts,
  ambiguous warns-and-touches-nothing.
- **`tests/lint/test_session_registry.py`** (3) + **`test_sdd_band_declaration_matches_number.py`**
  (1) green on the real tree (after the `SDD-800` band-declaration drift-fix).
- Happy path on the current clean tree: `--check` / `--apply` / `--dry-run` exit
  0, silent, no writes.

## Non-goals

- A full inter-session messaging protocol (threads/ack/inbox) — the union log is
  the seed; the protocol is a follow-up.
- Auto-committing (a hook must not); auto-resolving *line* conflicts beyond union
  + surgical row renumber; renumbering `E11.M` beyond the intruder's own row.
- Branch protection ("require branches up to date before merging") — recommended
  separately; would prevent most out-of-band merges from ever landing.

## Safety invariants

Docs + scripts + `.gitattributes` only. No gatewayd, no cockpit, no `unsafe`, no
crate edits. The resolver leaves changes UNSTAGED and reverts on unverified state
— it can never commit a half-applied renumber. R10212/SB-077 untouched. MS003
`unsigned-pending-MS003`.

## Cross-references

- `scripts/git/sdd_conflict_resolver.py` — the resolver (detect / plan / apply / verify / log / warn)
- `docs/sdd/SESSIONS.md` — the session registry (sessions identify themselves)
- `docs/sdd/RESOLUTION-LOG.md` — the cross-session ledger / message-board seed
- `scripts/git-hooks/lib/sdd-resolve.sh` + `post-merge` + `post-rewrite` — the wiring
- `tests/lint/test_sdd_conflict_resolver.py` / `test_session_registry.py` / `test_sdd_band_declaration_matches_number.py` — the lints
- `docs/sdd/100-parallel-session-conflict-avoidance.md` — SDD-100 (the band convention this heals)
- `docs/sdd/README.md` — the band table + how-to-add-an-SDD
- `tests/lint/test_sdd_numbers_unique.py` / `test_mandate_section_1_subsections.py` (`test_e11_modules_sequential`) / `test_context_md_counts.py` — the verify gate
