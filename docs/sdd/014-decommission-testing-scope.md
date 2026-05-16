# SDD-014 — Decommission testing scope (Q-014 resolution)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: Q-014 (decommission / wipe testing scope)
> Derived from: `scripts/hooks/decommission/`, `sovereign-osctl
> decommission`, SDD-008 (5-layer test pyramid).

## Problem

Decommission scripts (`secure-wipe-context.sh`, `zfs-pool-destroy.sh`,
`secure-wipe.sh`) are inherently destructive: their happy path
destroys data the operator wants gone. They cannot be exercised
end-to-end in CI — there's no pool to destroy, no devices to wipe.

But the GATES that protect against accidental invocation
(`require_root`, `SOVEREIGN_OS_CONFIRM_DESTROY=YES`, interactive
`confirm`) MUST hold or the operator can wipe their disk by accident.
A regression in any gate is a sovereignty failure.

Q-014 asks: what's the testing scope for decommission? This SDD
formalizes the answer.

## Decision

**Test what's testable without destruction: gate behavior, dispatch,
and refusal modes.** End-to-end destruction is exercised on real
hardware by the operator, never by CI.

## What this SDD says ships at each test layer

| Layer | What it covers | What it does NOT cover |
|---|---|---|
| **Layer 1 (schema)** | profile.hooks.decommission entries reference real `scripts/hooks/decommission/*.sh` paths (via `test_hook_script_paths.py`) | content of scripts |
| **Layer 2 (unit)** | None today; common.sh confirm + require_root + require_command are covered in `test_common_lib.sh` (so the helpers decommission scripts rely on are themselves tested) | the decommission scripts as units |
| **Layer 3 (stage acceptance)** | `tests/nspawn/test_decommission_gates.sh` (added with this SDD): 12 assertions covering require_root gate, SOVEREIGN_OS_CONFIRM_DESTROY=YES env-gate, SOVEREIGN_OS_WIPE_DEVICES presence gate, `sovereign-osctl decommission <sub>` dispatch + unknown-subcommand exit, default-no confirm propagation under NONINTERACTIVE | actual destruction (no pool, no devices, no shred) |
| **Layer 4 (QEMU)** | Future: a destructive-loop test that creates a virtual ZFS pool inside QEMU, runs the full decommission sequence with all gates set, asserts the pool is gone post-run. Not in foundation phase (cost > benefit until hardware arrives) | — |
| **Layer 5 (hardware)** | Operator-driven only — the destructive happy path runs once per real decommission. Output is operator-observed (status/logs). Never CI-gated | — |

## Required-gate contract (locked by Layer 3)

Every script in `scripts/hooks/decommission/` MUST:

1. **`require_root`** — refuse to proceed if `id -u != 0`.
2. **`SOVEREIGN_OS_CONFIRM_DESTROY` env-gate** — when applicable
   (pool destroy, device wipe) require the value to be exactly `YES`
   before proceeding past initial checks. `secure-wipe-context.sh`
   currently relies on the interactive `confirm` (default-no);
   the higher-tier wipes also require the env-gate.
3. **Interactive `confirm`** — final operator double-take with
   `default-no`. Under `SOVEREIGN_OS_NONINTERACTIVE=1` this falls
   through to default-no (i.e., refuses) per the `confirm` helper's
   default-no semantics tested in `test_common_lib.sh`.
4. **Idempotency** — running a script when the target is already gone
   (e.g., pool already destroyed) exits 0 without action.
5. **Operator-observable diagnostics** — refusals print why
   (`log_error` with the missing gate name) so the operator can
   re-issue with the correct env-gate.

Any new decommission hook must satisfy 1-5 AND drop into the L3 test
(add an assertion). The `sovereign-osctl decommission <sub>` dispatch
auto-routes — no new dispatch code per hook.

## Operator-side runbook (informational; not CI)

For a real decommission, the operator runs (in order):

```sh
# Phase 1: wipe state-fabric (tank/context — sovereign-specific data)
sudo sovereign-osctl decommission start

# Phase 2: destroy the ZFS pool
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
  sudo sovereign-osctl decommission pool

# Phase 3: secure-erase the underlying block devices
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
SOVEREIGN_OS_WIPE_DEVICES='/dev/nvme0n1 /dev/nvme1n1' \
  sudo sovereign-osctl decommission wipe
```

Each phase prints the next phase's command on completion (operator
guidance baked into the CLI).

## Goals

1. **No accidental destruction** — gates are tested; regressions fail CI.
2. **Operator clarity** — each script logs WHY it refused so the
   operator knows which env-var to set.
3. **Composable** — a new decommission hook drops into
   `scripts/hooks/decommission/` and `sovereign-osctl decommission`
   auto-finds it (the dispatch logic does the lookup).
4. **Honest about Layer 5** — actual destruction lives in operator-
   driven runs only. We don't simulate destruction in CI; we test
   refusals.

## Non-goals (this SDD)

- Does NOT add a QEMU-level destructive-loop test (deferred until
  the hardware is in place to validate the script chain on real ZFS).
- Does NOT introduce a "dry-run" mode for decommission scripts —
  the gates ARE the dry-run (script refuses → no action).
- Does NOT replace the operator-driven `confirm` final check — that
  stays as a defense-in-depth layer.

## Cross-references

- `scripts/hooks/decommission/`
- `scripts/sovereign-osctl` § `cmd_decommission`
- `tests/nspawn/test_decommission_gates.sh` (the L3 gate)
- `tests/nspawn/test_common_lib.sh` (covers the `confirm` helper)
- SDD-008 § Layer 5 (where end-to-end destruction lives)
