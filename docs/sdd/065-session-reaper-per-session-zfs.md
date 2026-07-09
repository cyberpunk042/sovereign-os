# SDD-065 — M057 session reaper + per-session ZFS datasets (session-runtime Stage-N)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: SDD-058 Q-058-C (partial) + Q-058-D — the deferred reaper + per-session ZFS
> Derived from: operator directive 2026-07-09 (chose M057 reaper + per-session ZFS after SDD-064 merged in PR #42; the per-panel wiring sweep is complete, so the remaining work is Stage-N backends); SDD-057 (5-layer save-state) + SDD-058 (the M057 runtime); R10212.

## Mission

Deepen the M057 session-runtime continuity slice (D-01): a **session reaper** that
auto-archives sessions whose process has exited, and **per-session ZFS datasets** so
each session's save-state snapshot is isolated to its own `tank/agents/<id>` child.

## Problem

SDD-058 shipped the M057 runtime (`session-runtime.py` spawns a real `systemd-run
--scope` process, captures the MainPID, registers a session; save-state's CRIU layer
targets that pid). Two SDD-058 Stage-N non-goals remain:
- **No reaper** — nothing polls session pids; a session whose process crashed/exited
  without a clean `sessions stop` stays `state:"active"` forever. There is **zero
  pid-liveness checking** in the tree.
- **No per-session ZFS** — every session shares `tank/agents` (the `dataset` field is a
  fixed enum key `"agents"`, `rollback-points._DATASETS`). There is no Python `zfs
  create` actuator (only install-time bash + a plan emitter).

## Grounded design

### The reaper — a state-reconciliation janitor

`reap()` (in `session-runtime.py`) scans `active` pid-bearing sessions; for any whose
tracked process is dead (`_pid_alive(pid)` via `os.kill(pid, 0)` — `ProcessLookupError`
= dead; `PermissionError`/undeterminable = alive, conservative) it sets `state:"archived"`
+ `reaped_at` + appends the session-decisions ledger + an OCSF-5001 span (atomic write,
best-effort). Only `active` sessions with a dead pid are touched — `hibernated`/`paused`/
terminal sessions are skipped (their pid is intentionally gone). **No `--confirm`** — the
process is gone regardless, so reconciling state to reality is safe bookkeeping, not a
destructive act (like the SDD-064 memory `reconcile`). Runs from a systemd oneshot+timer
(`sovereign-session-reaper.{service,timer}`, ~every 2 min, R171-hardened, mirroring
`sovereign-backup-snapshot`) + an osctl `sessions reap` verb. **CLI/timer-only — adds no
web mutation path** (`sessions start` stays CLI-only arbitrary-exec-gated, R10212).

### Per-session ZFS — additive (non-breaking)

At `start`, host-gated `zfs create tank/agents/<sess-id>` (`_zfs_create`, DRY-RUN
default; `shutil.which("zfs") is None` → skip honestly — SB-077, never claims a dataset
it did not create) + store a NEW `dataset_path: "tank/agents/<sid>"` on the entry **only
when the child dataset was really created**. The enum `dataset:"agents"` key STAYS — so
save-state's `_dataset_key`, `test_save_state`'s `dataset_key=="agents"` assertion, and
the `rollback-points._DATASETS` no-`/` exec-rail design are all UNTOUCHED. save-state's
zfs-snapshot layer PREFERS `dataset_path` (snapshots the per-session dataset directly via
`_zfs_snapshot_path` → real isolation) when present, else the enum key via
`rollback-points.create` (fallback — keeps the existing behavior + tests green); restore
mirrors (composes `<dataset_path>@<tag>` for `rollback-points.apply`).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-065-A | Reaper trigger. | **answered (operator, 2026-07-09): a systemd oneshot+timer janitor (~2 min) + an osctl `sessions reap` verb — CLI/timer-only, never a web control.** |
| Q-065-B | Archive semantics. | **answered: dead `active` pid-sessions → `archived` (+ ledger + span); hibernated/paused/terminal/no-pid skipped; no `--confirm` (reconciles state to reality).** |
| Q-065-C | Per-session dataset representation. | **answered: ADDITIVE `dataset_path` (tank/agents/<id>), set only on real `zfs create`; the enum `dataset` key + `_DATASETS` design preserved — no test breakage.** |
| Q-065-D | Dataset lifecycle on archive. | **proposed: leave the dataset (a retention purge is Stage-N; destroying it would lose the session's save-state).** |
| Q-065-E | Full m009 12-step orchestration + resume-into-checkpoint. | **proposed: Stage-N (the m009 deterministic-cortex deep work).** |

## Non-goals (Stage N)

- The full m009 12-step lifecycle orchestration + resume-into-restored-checkpoint.
- A per-session dataset **retention purge** (destroy archived sessions' datasets).
- Making `sessions start` anything other than CLI-only (the arbitrary-exec boundary).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX + mandate E11.M32; flip SDD-058 Q-058-C/D.
- **Stage 1:** `session-runtime.py` (`reap` + `_pid_alive` + `_zfs_create` + `dataset_path`)
  + `save-state.py` (prefer `dataset_path`) + `test_session_runtime.py` +
  `test_save_state.py` extensions.
- **Stage 2:** `sovereign-session-reaper.{service,timer}` + the `session-reap.sh` hook +
  the osctl `sessions reap` routing.
- **Stage N:** the m009 orchestration; a dataset retention purge; resume-into-checkpoint.

## Safety invariants

The reaper only reconciles state to reality (archives `active` sessions whose process is
already dead — safe bookkeeping, no destructive action); CLI/timer-only, never a web
control (R10212 — `sessions start` stays CLI-only; the reaper adds no web mutation path);
per-session `zfs create` is host-gated + DRY-RUN default + skips honestly when zfs is
absent (SB-077 — never fabricates a dataset); `dataset_path` is ADDITIVE (the enum
`dataset` key + `_DATASETS` no-`/` design + save-state's enum path all preserved — no
test breakage); the dataset is NOT destroyed on archive (no data loss; retention purge is
Stage-N); atomic sessions.json writes + ledger + OCSF-5001 span; the session reader
(`session-registry.py`) stays pure read-only; MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/lifecycle/session-runtime.py` (SDD-058) — the producer; += reap + per-session zfs.
- `scripts/lifecycle/save-state.py` (SDD-057) — the 5-layer save-state; prefers `dataset_path`.
- `scripts/lifecycle/rollback-points.py` (SDD-050) — the host-gated `zfs` idiom (`_run` +
  `shutil.which` + DRY-RUN) + `_DATASETS` enum + `apply()` (restore).
- `scripts/lifecycle/session-registry.py` — the pure reader (pid/dataset passthrough); unchanged.
- `scripts/lifecycle/session-decide.py` (SDD-053) — the ledger+span pattern reused.
- `systemd/system/sovereign-backup-snapshot.{service,timer}` — the oneshot+timer + R171 shape.
- SDD-057/058, M057 session runtime, R10212.
