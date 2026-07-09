# SDD-057 — Session save-state (M047 5-layer save-state + CRIU wrapper for D-01)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: none (SDD-053 Stage 3 — the real hibernate/resume save-state effect)
> Derived from: operator directive 2026-07-08 (chose the M047 continuity Stage-3 backend behind D-01 after the cockpit control-wiring sweep completed in PR #34); SDD-053 (session lifecycle — the registry transition this extends); SDD-050 (snapshot/rollback — reused for the ZFS layer); SDD-052 (memory state — the memory-record layer); `crates/sovereign-save-state` (E0451 — the 5-layer save-state contract); M047 continuity (Phase 9); M057 12-step task lifecycle.

## Mission

Give D-01's hibernate/resume a real *save-state* effect: capture a session's
continuity as the E0451 **five-layer save-state** — ZFS snapshot + CRIU checkpoint
+ replay log + memory record + profile state — with a completeness gate, instead
of only transitioning the registry `state` field (SDD-053). This is the first
Stage-3 real-runtime engine.

## Problem (grounded reality)

- The `crates/sovereign-save-state` crate is the 5-layer **completeness-gate type
  model** (serde kebab-case: `zfs-snapshot`, `criu-checkpoint`, `replay-log`,
  `memory-record`, `profile-state`); a TRUE save-state = all five. It fixes the
  contract; it is NOT an executor, and it asserts "ZFS + CRIU alone is not a true
  save-state."
- **No `criu` executor exists**; **no M057 session-process runtime exists** —
  `sessions.json` entries carry no `pid`/cgroup/dataset. A real CRIU checkpoint has
  **no target process** today.
- **Four of the five layers are already producible** via existing engines;
  `criu-checkpoint` is the only one blocked on the missing runtime.

## Required coverage

### The 5-layer orchestrator + completeness gate (`scripts/lifecycle/save-state.py`)

`capture(session_id)` composes:
- **profile-state** — the active profile (`/etc/sovereign-os/active-profile.env` /
  `SOVEREIGN_OS_ACTIVE_PROFILE`); always capturable.
- **memory-record** — snapshot + sha256 of `/run/sovereign-os/memory.json`
  (SDD-052); capturable when present.
- **replay-log** — an append to the durable `/var/log/sovereign-os/save-state.jsonl`;
  always capturable.
- **zfs-snapshot** — `rollback-points.create` (SDD-050) on the session's dataset
  (default `agents`); dry-run plan / host live.
- **criu-checkpoint** — the WRAPPER (operator decision Q-057-A): when the session
  carries a `pid`, plan/execute `criu dump --tree <pid> --images-dir <dir>`
  (host live); when absent (always today) record it **missing** ("no target —
  pending the M057 runtime").

The save-state record carries `captured` / `missing` / `is_true_save_state`
(= all 5) / per-layer `layers` plan, written atomically to
`/var/lib/sovereign-os/save-state/<sid>/<ts>/manifest.json` + a ledger + OCSF-5001
span. **The gate honestly reports partial (4/5) save-states** until a `pid`-bearing
session exists.

`restore(session_id)` emits the inverse plan from the latest manifest: `criu
restore` (if a checkpoint exists) + `rollback-points.apply` (zfs rollback) +
memory/profile restore note (Stage 4).

### Wiring + registry passthrough

- `session-registry.py` `_normalise` passes through optional `pid` + `dataset`
  (read-only; populated by the future M057 runtime / a test fixture) — the reader
  stays pure.
- `session-decide.py` `hibernate` invokes `save-state.capture` (the real effect,
  after the SDD-053 registry transition; partial captures logged); `resume`
  invokes `save-state.restore`. The SDD-053 transition + guards stay intact.
- `sovereign-osctl sessions {save-state|restore} <id>` write sub-verbs →
  save-state.py; sudoers gains the two verb prefixes (host mutations: zfs + criu).

### Drift-guard

`tests/lint/test_save_state_layers_match_crate.py` asserts the Python `_LAYERS` ≡
the crate's `SaveLayer` serde names — the crate is the single source of truth.

## Goals

- A real, testable 5-layer save-state orchestrator + completeness gate; DRY-RUN
  plans testable in CI; real zfs/criu host-gated.
- Reuse existing engines (SDD-050 ZFS, SDD-052 memory, SDD-053 ledger); keep
  `session-registry.py` a pure reader.
- R10212 preserved: selfdef/perimeter untouched; save-state paths free of
  selfdef/tetragon; the session read API stays read-only.

## Non-goals (Stage 4 / follow-up)

- The real **M057 session-process runtime** (spawns + PID/cgroup/dataset-tracks
  sessions — the true CRIU target producer).
- A dedicated `session-save-state` cockpit control; per-session ZFS dataset
  provisioning; the memory/profile **restore** execution (vs plan).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-057-A | Save-state scope. | **answered (operator, 2026-07-08): the 5-layer orchestrator + completeness gate PLUS the CRIU wrapper path (pid-gated).** |
| Q-057-B | `pid`/`dataset` source. | **proposed: optional session fields; the M057 runtime populates them (Stage 4). Today they're absent → criu missing.** |
| Q-057-C | Restore semantics. | **proposed: criu restore + zfs rollback (rollback-points.apply); memory/profile restore is Stage 4.** |
| Q-057-D | memory-record capture depth. | **proposed: reference + sha256 the memory.json now; deep-copy/restore is Stage 4.** |
| Q-057-E | Real M057 session-process runtime. | **proposed: Stage 4 — the true CRIU target producer; until then the gate reports partial.** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `scripts/lifecycle/save-state.py` + `tests/unit/test_save_state.py`
  + `tests/lint/test_save_state_layers_match_crate.py`.
- **Stage 2:** registry `pid`/`dataset` passthrough + session-decide
  hibernate→capture / resume→restore + osctl save-state/restore sub-verbs + sudoers.
- **Stage 3 (follow-up):** the M057 session-process runtime; the cockpit control;
  per-session datasets; memory/profile restore execution.

## Safety invariants

Grounded-not-speculative (CRIU plan only with a real `pid`; else honest missing);
DRY-RUN-default + operator-key + type-to-confirm for the real mutations (zfs +
criu); selfdef/perimeter untouched + save-state paths free of selfdef/tetragon;
session read API stays read-only; the completeness gate honestly reports partial
save-states; Python layers ≡ Rust crate (drift-guard); atomic manifest + ledger +
OCSF-5001 span; MS003 `unsigned-pending-MS003`. zfs snapshot + criu dump are the
only host mutations, each gated by the exec rail + sudoers.

## Cross-references

- `crates/sovereign-save-state/src/lib.rs` — the E0451 5-layer contract (drift-guard
  source of truth).
- `scripts/lifecycle/rollback-points.py` `create`/`apply` — reused for the ZFS layer.
- `scripts/lifecycle/session-registry.py` (pure reader; pid/dataset passthrough) ·
  `scripts/lifecycle/session-decide.py` (SDD-053 — hibernate/resume drive capture/restore).
- `scripts/operator/_action_exec.py` / `control-exec-api.py` — the exec rail.
- SDD-053 (session lifecycle), SDD-050 (snapshot/rollback), SDD-052 (memory), M047
  continuity (Phase 9), M057 task lifecycle.
