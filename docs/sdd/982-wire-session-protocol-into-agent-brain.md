# SDD-982 — wire the session identity / resolver / comms protocol into the agent brain surfaces

> Status: draft
> Owner: operator-directed 2026-07-13 ("you did not even update claude and agents.md files and such"); agent-authored.
> Builds on: SDD-980 (identity + auto-resolver) + SDD-981 (message board). This makes them **discoverable** to every session.
> Mandate module: **E11.M982**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

SDD-980 and SDD-981 shipped the machinery — a session registry, the collision
auto-resolver, and the message board — but a fresh session or a post-compaction
agent had **no way to learn it exists**: the agent-facing brain surfaces still
described only the SDD-100 number bands. This wires the new protocol into the two
surfaces a session actually reads, so identity, self-healing, and inter-session
communication become part of the standing onboarding rather than tribal knowledge.

## The brain surfaces (this repo)

`sovereign-os` has no root `CLAUDE.md`/`AGENTS.md`; the agent-facing surfaces are:

| Surface | Role | What was added |
|---|---|---|
| **`context.md`** | The operator-mandated "read me first after every compaction" re-orientation surface (SessionStart hook `cat`s it). | The "Parallel-session conventions" section grew from 3 steps to 6: **(1) identify yourself** (SESSIONS.md + `session_comms.py whoami`, set your band declaration), **(4) collisions self-heal** (the SDD-980 resolver + RESOLUTION-LOG), **(5) talk to sessions + operator** (the SDD-981 board + `inbox`/`post`/`reply`/`thread`). The higher-up one-line summary now names all three. |
| **`scripts/claude-code-env/templates/CLAUDE.md`** | The CLAUDE.md the env-bootstrap installs into `~/.claude/` for every session (loaded every message). | One row added to the SDD+TDD methodology table: at session start, `whoami` + check `inbox`; collisions self-heal; message the board — pointing at `context.md` for the full protocol. Kept tight (it's hot-path context). |

## What a session now learns at start

1. **Who am I** — `session_comms.py whoami` resolves the session from the branch;
   confirm/add your row in `docs/sdd/SESSIONS.md`; set your `Number band:` line.
2. **Any mail?** — `session_comms.py inbox` (the `post-merge` hook also nudges on pull).
3. **Collisions self-heal** — an out-of-band number is auto-renumbered + verified
   (`sdd_conflict_resolver.py`), logged to `RESOLUTION-LOG.md`.
4. **How to talk** — `post --to <session|operator|all>` / `reply` / `thread`.

## Verification (real, observed)

- `context.md` counts-contract lint (`test_context_md_counts.py`) still green — only
  prose changed + the `sdd files` count bumped to match the new SDD-982 file.
- `test_mdbook_catalog_sync.py`, `test_sdd_reachability.py`, `test_sdd_numbers_unique.py`,
  `test_session_registry.py`, `test_sdd_band_declaration_matches_number.py` green.
- No script/behaviour change — the tools referenced (`session_comms.py`,
  `sdd_conflict_resolver.py`) already exist and are tested (SDD-980/981).

## Non-goals

- Creating a root `AGENTS.md` — `context.md` is this repo's equivalent read-me-first
  surface; a dedicated `AGENTS.md` can follow if the operator wants one.
- Any change to the protocol itself — this is documentation/onboarding only.

## Safety invariants

Docs only (`context.md` + the deployed CLAUDE.md template + this SDD + registries).
No gatewayd, no cockpit, no `unsafe`, no crate edits. R10212/SB-077 untouched. MS003
`unsigned-pending-MS003`.

## Cross-references

- `context.md` — "Parallel-session conventions" (the full protocol for sessions)
- `scripts/claude-code-env/templates/CLAUDE.md` — the deployed per-session CLAUDE.md
- `docs/sdd/980-sdd-conflict-auto-resolution.md` — identity + auto-resolver
- `docs/sdd/981-session-communication-protocol.md` — the message board
- `docs/sdd/SESSIONS.md` — the session registry
