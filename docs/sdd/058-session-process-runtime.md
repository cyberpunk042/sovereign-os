# SDD-058 — M057 session-process runtime (the session producer that makes CRIU real)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: none (SDD-057 Stage 4 — the producer that makes the CRIU save-state layer capturable)
> Derived from: operator directive 2026-07-08 (chose the M057 session-process runtime after SDD-057's save-state merged in PR #35 — the highest-leverage continuation); SDD-057 (5-layer save-state — the consumer); SDD-053 (session lifecycle — the registry this produces); M057 (12-step task lifecycle / "text is payload inside typed state"); m009 deterministic-cortex-runtime; m058 goldilocks-scheduler.

## Mission

Build the missing **producer** for the M057 session registry: spawn a real
operator task command as a tracked process and register it in
`/run/sovereign-os/sessions.json` with a real `pid` (+ cgroup + dataset). That
real pid is what makes SDD-057's `criu-checkpoint` layer capturable — turning the
4/5 partial save-state into a **true 5/5**.

## Problem

- **No producer writes `sessions.json`** and **no process-spawning runtime
  exists** — SDD-057's save-state always reports `criu-checkpoint` missing ("no
  target pid"). M057 is the "12-step task lifecycle" with the deep deterministic
  cortex (m009) + scheduler (m058) as substrate — a large spec with no impl.
- Building the full cortex runtime is out of scope for one PR. The honest MVP that
  makes CRIU real is a **session-process producer**: spawn a real, operator-given
  task command as a tracked process + register it.

## Required coverage

### The task-command producer (`scripts/lifecycle/session-runtime.py`)

- **`start(task_argv, dataset_key)`** — allocate `id = sess-<8hex>`; validate
  `dataset_key ∈ rollback-points._DATASETS`; spawn the task under a transient
  `systemd-run --scope --unit=sovereign-session-<id> -- <task_argv>` (a real cgroup
  — the CRIU target + resource control); capture the MainPID
  (`systemctl show <scope> -p MainPID`); **register** the session `{id, kind:task,
  state:active, step:1 (Intake), pid, cgroup, dataset, started_at, task}` in
  `sessions.json` atomically. DRY-RUN default emits the scope plan (spawns nothing).
- **`stop(session_id)`** — `systemctl stop <scope>` + transition state→`archived`.
- **`list()`** — reuse `session-registry.list_sessions`.
- The session starts `active` at M057 step 1; the full 12-step lifecycle
  orchestration is the m009 deep work (Stage N).

### Security boundary (R10212 + arbitrary-exec)

`sessions start` runs an OPERATOR-SUPPLIED command — arbitrary code execution. It
is **CLI-ONLY** and **DELIBERATELY NOT a cockpit control**: NO
`control-systems.yaml` entry, NO `control-exec-api` wiring, NO cockpit sudoers
grant. `_action_exec` runs only registered controls (404 on unknown), so the web
can never reach it. The task argv is passed as a **list** to `systemd-run` (no
shell, no injection). Only the already-registered-session controls
(hibernate / save-state) stay web-triggerable.

### The payoff

A runtime-registered pid-session → `save-state.capture` now captures the
`criu-checkpoint` layer → **true 5/5 `is_true_save_state`** (proven end-to-end in
`test_session_runtime.py`).

## Goals

- A real, testable session-process producer; DRY-RUN plans testable in CI; the real
  `systemd-run` spawn host-gated.
- Reuse `session-registry` (reader) + `rollback-points._DATASETS`; complete
  SDD-057 (save-state) by producing its CRIU target.
- R10212 + arbitrary-exec safety: `sessions start` never web-triggerable.

## Non-goals (Stage N / follow-up)

- The full m009 deterministic-cortex **12-step lifecycle orchestration** (step
  transitions driven by the scheduler m058).
- Per-session ZFS dataset provisioning (`zfs create tank/agents/<id>`); a session
  **reaper** daemon (auto-archive on process exit); resume-into-restored-checkpoint.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-058-A | What is a session process (MVP). | **answered (operator, 2026-07-08): a task-command runtime — `sessions start -- <cmd>` spawns the operator's real command.** |
| Q-058-B | Process tracking mechanism. | **answered (operator, 2026-07-08): `systemd-run --scope` (a real cgroup — CRIU target + resource control).** |
| Q-058-C | Full 12-step lifecycle orchestration. | **the reaper half answered (SDD-065, 2026-07-09): `session-runtime.reap()` auto-archives `active` sessions whose process has exited (a systemd-timer janitor). The full m009 12-step orchestration remains Stage N.** |
| Q-058-D | Per-session ZFS dataset. | **answered (SDD-065, 2026-07-09): `start` host-gated `zfs create tank/agents/<sid>` + an ADDITIVE `dataset_path` (the enum `dataset` key preserved); save-state prefers the per-session dataset when present, else the shared enum fallback.** |
| Q-058-E | pid-capture precision. | **proposed: `systemctl show <scope> -p MainPID` (else the child pid).** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `scripts/lifecycle/session-runtime.py` + `tests/unit/test_session_runtime.py`
  (incl. the end-to-end pid → 5/5 save-state proof).
- **Stage 2:** osctl `sessions start`/`stop`/`list` CLI dispatch arms (no control,
  no cockpit sudoers change).
- **Stage N (follow-up):** the m009 12-step orchestration; per-session datasets; a
  reaper; resume-into-checkpoint.

## Safety invariants

`sessions start` is CLI-only + never a cockpit control (arbitrary-exec never
web-triggerable — R10212); task argv is an argv-list (no shell injection); session
ids `_SAFE_ID`-clean; DRY-RUN-default + host-gated `systemd-run`/`systemctl`;
selfdef/perimeter untouched; `sessions.json` writes are atomic + single-flight; the
producer never mutates selfdef/tetragon; the existing web-triggerable session
controls (hibernate/save-state) are unchanged.

## Cross-references

- `scripts/lifecycle/save-state.py` (SDD-057) — the consumer; its CRIU layer now
  captures against runtime-produced pids.
- `scripts/lifecycle/session-registry.py` — the reader (reused); this runtime is
  the writer/producer.
- `scripts/lifecycle/rollback-points.py` `_DATASETS` — dataset-key validation.
- `scripts/sovereign-osctl` — the `sessions)` arm (start/stop/list CLI dispatch).
- `config/control-systems.yaml` + `config/sudoers.d/sovereign-os-cockpit` —
  DELIBERATELY unchanged (no web control for arbitrary-exec `start`).
- SDD-057 (save-state), SDD-053 (session lifecycle), M057 (task lifecycle), m009
  (deterministic cortex), m058 (goldilocks scheduler).
