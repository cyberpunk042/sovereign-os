# SDD-050 — Snapshot/rollback actuation (functional snapshot create / prune + recent-N rollback for D-08)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-08
> Closes findings: none (write half atop the D-08 read model + SDD-047 control surface)
> Derived from: operator directive 2026-07-08 (chose the D-08 rollback-points engine after SDD-049's model-runtime merged in PR #27); SDD-047 (cockpit functional execution / R10274 control-exec-api); SDD-045 (control surface); SDD-049 (the prior greenfield engine — id-resolution + refuse-by-default patterns reused here); M060 R10097-R10101 (D-08 read model); M068 ZFS storage architecture; MS041 commit authority.

## Mission

Make the D-08 rollback-points panel's snapshot/rollback actions functional as
sanctioned cockpit controls on the SDD-047 R10274 rail. Today the write buttons
are neutralized ("planned") and emit a fake `sovereignctl snapshot …` string;
the D-08 read path (`rollback-points.py` core + `rollback-api.py` daemon) is
complete, but the actuation half — snapshot **create** and **prune** — is
greenfield, and the per-snapshot **rollback** button is dead (the functional
`rollback-apply` control is latest-only).

## Problem

The D-08 dashboard's `actions` row + per-row buttons emit `sovereignctl snapshot
list/create/preview/prune/diff` and `commit log` — none of which exist
(`sovereignctl` is not a binary; these subverbs are absent). Two categories:

1. **Already live but mislabeled (read).** `sovereign-osctl rollback
   {snapshot,preview --to,commits}` → `rollback-points.py` already backs the
   list, preview, and commit-history views, and `rollback-api.py` serves
   `/api/d-08/snapshot` + `/api/d-08/preview?to=`. The table + timeline + per-row
   `preview` already render from the live API; the standalone "planned: list /
   preview / commit log" buttons are dead clipboard fakes that duplicate live data.
2. **Genuinely greenfield (write).** `snapshot create` (`zfs snapshot <ds>@<tag>`)
   and `snapshot prune` (`zfs destroy` aged snapshots) do not exist. And arbitrary-
   snapshot rollback is not web-functional: `apply(to)` in the core resolves ANY
   snapshot, but the `rollback-apply` control is latest-only because arbitrary
   snapshot ids carry `/`+`@` that the exec allowlist's `_SAFE_VALUE` forbids.

## Required coverage

### Snapshot create + prune (write verbs, sovereign-os-owned)

- **create** — `sovereign-osctl rollback create --dataset <key> --tag <tag>
  [--confirm]` → `zfs snapshot <resolved-dataset>@<tag>`. The dataset is an **enum
  of short keys** resolved to the real dataset path INSIDE the engine (`os →
  rpool/sovereign-os`, `context → tank/context`, `models → tank/models`, `agents →
  tank/agents`) — never a `/`-bearing arg through the exec allowlist (the model-load
  id-resolution pattern from SDD-049). `<tag>` is validated `_SAFE_VALUE`-clean
  (reject `/`, `@`, whitespace, shell metacharacters).
- **prune** — `sovereign-osctl rollback prune --retain-days <n> [--confirm]
  [--force]` → per dataset, destroy snapshots older than `n` days, EXCEPT a hard
  **floor** (never the newest N per dataset, never the very latest). If the plan
  would drop a dataset below the floor → **refuse** unless `--force` (logged).
  DRY-RUN default lists the exact `@`-names it WOULD destroy.
- **R10212 ownership**: create/prune are ZFS storage ops on sovereign-os-owned
  datasets — **sovereign-os-owned**, consistent with `rollback-apply` (already
  local, PR #25). NOT selfdef-proxy. `rollback-api.py` stays read-only (405 on
  writes); its imported `_core` calls only `snapshot()`/`preview()` — the new write
  methods are CLI-dispatch-only.

### Recent-N rollback (arbitrary-snapshot rollback, made web-functional)

- A NEW control `rollback-recent` — `sovereign-osctl rollback apply --to
  {recent-1|…|recent-5} --confirm` — a bounded enum of **stable positional
  tokens** (`_SAFE_VALUE`-clean, no `/`). The engine resolves `recent-N` →
  `collect_snapshots()[N-1]["id"]` (newest-first, bounds-checked) INTERNALLY. The
  DRY-RUN plan returns `resolved` (the real `@`-name), so the operator sees the
  exact target before the type-to-confirm gate (TOCTOU mitigation). The existing
  `rollback-apply` (latest-only, one-click) is left UNTOUCHED — its change_cli is a
  pinned security contract (`test_sovereign_osctl_rollback_apply.py`).

### Honest read re-wiring (per "we do not minimize")

The dead read buttons are re-pointed to real live actions (drop the fake
`sovereignctl` clipboard): list → `load()` (refresh the live inventory), the
generic preview → `preview()` of the latest snapshot, per-row diff → `preview()`
(the plan already shows the reverted-commit diff), commit-log → `load()` (the
timeline interleaves the live MS041 commits); create/prune/per-snapshot-rollback
→ the control rail (`jumpToControl`).

## Goals

- Functional snapshot create + prune + recent-N rollback via the sanctioned
  control-exec-api rail; each a new control auto-rendered on d-08
  (`applies_to: [d-08-rollback-points]`).
- Reuse `rollback-points.py` (`collect_snapshots` / `_run`) — the new write methods
  live alongside the existing destructive `apply` (already in this module); the
  read methods `snapshot()`/`preview()` the API imports stay untouched.
- R10212 preserved: selfdef/perimeter untouched; `state_path` free of
  selfdef/tetragon; `rollback-api.py` stays read-only (405); dataset enum resolved
  internally (never a `/`-arg).

## Non-goals (Stage 3 / follow-up)

- Structured file-level `rollback diff` (a real `zfs diff` read verb + endpoint) —
  the per-row diff button reuses the live preview for now.
- Auto-snapshot-before-MS041-commit hook; cross-dataset atomic snapshot groups; a
  retention-policy config file.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-050-A | The snapshot-target dataset enum set. | **proposed: `{os→rpool/sovereign-os, context→tank/context, models→tank/models, agents→tank/agents}`. Operator may extend (tank/runtime, tank/agents siblings exist).** |
| Q-050-B | Prune floor size. | **proposed: keep the newest 3 per dataset AND never the very latest, regardless of `--retain-days`. Operator may tune.** |
| Q-050-C | `--force` (below-floor prune) placement — a control option or CLI-only? | **answered (operator, 2026-07-08): floor + refuse-by-default; `--force` is the logged override, kept CLI-only (a dangerous escalation, like arbitrary-snapshot rollback stayed CLI in PR #25).** |
| Q-050-D | Recent-N depth. | **proposed: 5 (recent-1..recent-5). Operator may widen.** |
| Q-050-E | A real `rollback diff --from <id>` read verb + endpoint. | **proposed: defer to Stage 3; the per-row diff button reuses the live preview for now (no new API surface).** |
| Q-050-F | Arbitrary-rollback posture. | **answered (operator, 2026-07-08): make it web-functional via a bounded recent-N enum resolved internally (a separate `rollback-recent` control; `rollback-apply` stays latest-only).** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** extend `scripts/lifecycle/rollback-points.py` — `_DATASETS` enum,
  `create()`, `prune()` (floor + refuse + `--force`), recent-N in `apply()`, new
  subparsers; `tests/unit/test_snapshot_ops.py`.
- **Stage 2:** 3 controls (`snapshot-create`, `snapshot-prune`, `rollback-recent`)
  + sudoers (`rollback create --dataset *`, `rollback prune --retain-days *`,
  `rollback apply --to *`) + lint bumps (registry 21→24, local 19→22) + honest
  d-08 button re-wiring. No `sovereign-osctl` edit — the `rollback)` arm already
  passes `"$@"` to the core.
- **Stage 3 (follow-up):** real `rollback diff`, auto-snapshot-before-commit hook,
  cross-dataset atomic snapshots, retention config.

## Safety invariants (every stage)

Privileged + operator-key + type-to-confirm + DRY-RUN-default (create/prune/
recent-rollback); selfdef/perimeter untouched + `state_path` free of selfdef/
tetragon; `rollback-api.py` stays read-only (405); dataset enum resolved internally
(never a `/`-arg); `<tag>` `_SAFE_VALUE`-validated; prune floor + refuse-below-floor
(`--force` logged, CLI-only); recent-N resolved internally with `resolved` shown
pre-confirm; `zfs snapshot/destroy/rollback` are the only host mutations, each gated
by the exec rail + sudoers. `rollback-apply`'s pinned `--to latest --confirm`
contract is left intact.

## Cross-references

- `scripts/lifecycle/rollback-points.py` — the D-08 core (extend with write methods;
  keep `snapshot()`/`preview()` read methods pristine for the API).
- `scripts/operator/rollback-api.py` — read-only daemon (imported `_core`; stays 405).
- `scripts/sovereign-osctl:8190` — the `rollback)` arm passes `"$@"` (no edit).
- `scripts/operator/_action_exec.py` — the exec rail (`state_path` must avoid
  selfdef/tetragon; `_SAFE_VALUE` forbids `/`); `control-exec-api.py` — R10274 daemon.
- `config/control-systems.yaml` — the 21 controls (model the 3 new after the model
  block; do NOT modify `rollback-apply`).
- `config/sudoers.d/sovereign-os-cockpit` — NOPASSWD allowlist (add the 3 verb prefixes).
- `tests/lint/test_sovereign_osctl_rollback_apply.py` — pins `rollback-apply.change_cli`
  (why `rollback-recent` is a separate control).
- SDD-047 (cockpit functional execution), SDD-045 (control surface), SDD-049 (model
  runtime — the prior greenfield engine; id-resolution + refuse-by-default reused).
