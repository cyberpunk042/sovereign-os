# SDD-053 — Session lifecycle authority (functional hibernate / resume / kill for D-01)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-08
> Closes findings: none (write half atop the D-01 read model + SDD-047 control surface)
> Derived from: operator directive 2026-07-08 (chose the D-01 active-sessions engine after SDD-052's memory-change authority merged in PR #30); SDD-051 (adapter promotion) + SDD-052 (memory-change) — the registry-transition twins (state-file overlay read model + decision-writer + MS003-deferred signature); SDD-047 (cockpit functional execution / R10274); M057 12-step task lifecycle (E0548/E0556); M047 CRIU + ZFS continuity; M060 R10059-R10062 (D-01 read model).

## Mission

Make the D-01 active-sessions panel's lifecycle actions — **hibernate**,
**resume**, **kill**, and bulk **hibernate-all** — functional as sanctioned
cockpit controls on the SDD-047 R10274 rail. Today the buttons are neutralized
(`alert('planned')`); the D-01 read path (`session-registry.py` +
`sessions-api.py`) is complete, but the write half — the M057 session-lifecycle
authority — is greenfield.

## Problem

The D-01 per-row hibernate/resume/kill + the `hibernate all` button emit nothing
(`sovereign-osctl` has no session-lifecycle verb; "the M057 CRIU+ZFS
session-lifecycle engine is not built; session-registry.py is a pure reader").
Structurally the SDD-051/052 registry-transition gap:

- **Read side complete.** `sovereign-osctl sessions {active,summary,steps}` →
  `scripts/lifecycle/session-registry.py` projects the M057 session registry
  (`/run/sovereign-os/sessions.json`: `sessions:[{id, kind, profile, state, step,
  srp_agent, started_at, eta_seconds, branch_count}]`). `sessions-api.py` serves
  `/api/sessions/active`; writes → 405.
- **Sessions are typed registry entries, NOT raw PIDs.** The M057 state machine
  has 9 states (active / paused / waiting_user / waiting_tool / hibernated /
  completed / failed / rolled_back / archived). So hibernate/resume/kill transition
  a session entry's `state` field.
- **The real CRIU+ZFS effect is the M057 engine's job.** The actual M047 CRIU
  checkpoint + ZFS warm-sandbox continuity is Stage 4; this engine transitions the
  registry state + records the decision (like memory-decide deferred the M028
  effect).

## Required coverage

### hibernate / resume / kill + hibernate-all (write, sovereign-os-owned)

- **hibernate** — `active → hibernated` (state guard).
- **resume** — `hibernated → active` (state guard).
- **kill** — non-terminal → **`archived`** (Q-053-A; M057 has no distinct `killed`
  state — `archived` is the clean operator-terminated terminal). Refused if the
  session is already terminal (`completed`/`failed`/`rolled_back`/`archived`).
- **hibernate-all** — bulk: every `active` session → `hibernated` in one atomic
  write (Q-053-B).
- Each transition updates the entry's `state` in `sessions.json`, appends a ledger
  record + OCSF-5001 span, and records `signature: "unsigned-pending-MS003"`.
  **R10212 ownership**: the M057 session lifecycle is sovereign-os-owned;
  `sessions-api.py` stays read-only (405); write methods are CLI-dispatch-only.
- **No speculative CRIU/ZFS effect.** The registry-state transition + record is
  the sovereign-os-owned decision; the real M047 CRIU checkpoint/restore + ZFS
  warm-sandbox is the M057 engine (Stage 4).

### Decision-writer

The writer lives in a NEW `scripts/lifecycle/session-decide.py` (keeps
`session-registry.py` a pure reader — the API imports it and calls `active()`),
importing the reader's `SESSION_REGISTRY` / `_read_registry` / `TASK_STATES` /
`list_sessions`. Atomic `os.replace` write; durable
`/var/log/sovereign-os/session-decisions.jsonl` ledger; OCSF-5001 M049 span
(D-05/D-16).

### MS003 signing (deferred, per the SDD-051/052 precedent)

Signing delegated to selfdef; records `unsigned-pending-MS003` (no signing crypto
in sovereign-os — R10212). Presence-gated + type-to-confirm at the exec daemon.

### The controls

Two controls: `session-decide` — `sovereign-osctl sessions
{hibernate|resume|kill} <id> --confirm` (per-session, mirroring adapter-decide's
verb enum); and `session-hibernate-all` — `sovereign-osctl sessions
hibernate-all --confirm` (the bulk action, no id). Both privileged,
`applies_to: [d-01-active-sessions]`. Registry 26→28, local 24→26.

## Goals

- Functional hibernate/resume/kill + hibernate-all via the sanctioned
  control-exec-api rail; two controls auto-rendered on d-01.
- Reuse `session-registry.py` (pure reader) + mirror `adapter-decide.py`.
- R10212 preserved: selfdef/perimeter untouched; `state_path` free of
  selfdef/tetragon; `sessions-api.py` stays read-only (405).

## Non-goals (Stage 3 / follow-up)

- Real M047 **CRIU** checkpoint/restore + **ZFS** warm-sandbox continuity (the
  actual hibernate/resume effect).
- A `sovereign run` **session producer** wiring; resume-into-branch.
- Real MS003 **signing** (selfdef).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-053-A | `kill` target state (M057 has no `killed`). | **answered (operator, 2026-07-08): `archived` (the clean operator-terminated terminal; no schema change).** |
| Q-053-B | `hibernate-all` bulk scope. | **answered (operator, 2026-07-08): include the bulk control (every active → hibernated in one gated action).** |
| Q-053-C | `kill` guard on terminal states. | **proposed: refuse if the session is already terminal (completed/failed/rolled_back/archived).** |
| Q-053-D | Real M047 CRIU + ZFS checkpoint/restore. | **proposed: Stage 4 — this engine transitions the registry state + records; the M057 engine performs the real effect.** |
| Q-053-E | Real MS003 signing. | **proposed: Stage 4 — signature `unsigned-pending-MS003` until selfdef signs.** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `scripts/lifecycle/session-decide.py` (hibernate/resume/kill +
  hibernate-all) + `tests/unit/test_session_decide.py`.
- **Stage 2:** the two controls + the `sessions)` osctl read/write sub-case
  routing + sudoers + lint bumps (26→28) + honest d-01 button re-wire.
- **Stage 3 (follow-up):** real CRIU+ZFS effect, session producer, real signing.

## Safety invariants (every stage)

Privileged + operator-key + type-to-confirm + DRY-RUN-default; state-machine
guards (hibernate←active, resume←hibernated, kill refused on terminals);
selfdef/perimeter untouched + `state_path` free of selfdef/tetragon;
`sessions-api.py` stays read-only (405); ids `_SAFE_ID`-validated; atomic
`sessions.json` write + durable ledger + OCSF-5001 span; MS003
`unsigned-pending-MS003`. The registry write is the only host mutation (no
speculative CRIU/ZFS), gated by the exec rail + sudoers.

## Cross-references

- `scripts/lifecycle/session-registry.py` — the D-01 reader (import its helpers;
  keep it a pure reader).
- `scripts/inference/adapter-decide.py` + `scripts/intelligence/memory-decide.py`
  — the writer templates (this engine's twins).
- `scripts/operator/sessions-api.py` — read-only daemon (imported `_core`; 405).
- `scripts/sovereign-osctl` — the `sessions)` arm → read/write sub-case routing,
  mirroring `approvals)`.
- `scripts/operator/_action_exec.py` — the exec rail (`state_path` must avoid
  selfdef/tetragon; `_SAFE_VALUE` forbids `/`); `control-exec-api.py` — R10274 daemon.
- `config/control-systems.yaml` — the 26 controls (model the new ones on
  adapter-decide / memory-decide).
- SDD-051 (adapter promotion), SDD-052 (memory-change — the twins), SDD-047
  (cockpit functional execution).
