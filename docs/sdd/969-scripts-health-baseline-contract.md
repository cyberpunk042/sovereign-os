# SDD-969 — scripts health-baseline contract

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-020** (scripts health baseline — protect it).
> Mandate module: **E11.M969** (operator-mandate cross-link).
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

The audit found the operator-script surface at an **exemplary baseline** (F-2026-020): every shell script parses, every Python script byte-compiles, and every verb `sovereign-osctl` dispatches resolves to a real handler. The ask was the same as for the crate workspace (SDD-974): a lint so the bar can't silently drop as 400 scripts churn. This is that guard — the scripts-surface parallel to the crate-hygiene contract.

## Investigation (each invariant re-checked against the tree)

- **Shell parse**: 102 `scripts/**/*.sh` — **0** `bash -n` failures.
- **Python compile**: 299 `scripts/**/*.py` — **0** `py_compile` failures.
- **osctl dispatch**: `scripts/sovereign-osctl` (9,101 lines) defines **29** `cmd_*` handlers and calls **29** — **0 dangling** (every dispatched verb resolves). (The audit noted "30 cmd_* verbs"; the tree is now 29 — the contract recomputes, so it tracks the real count.)
- The existing `test_live_reload_contract.py` byte-compiles only a handful of named daemons; the port-map / systemd-pairing baselines are already held by `test_dashboard_port_and_reference_integrity.py`. The parse / compile / dispatch axis over the *whole* scripts tree was unguarded — this closes it.

## What this SDD builds

### `tests/lint/test_scripts_health_baseline.py` — the contract

Three tests, each recomputed from the tree so a regression fails CI:

1. `test_all_shell_scripts_parse` — every `scripts/**/*.sh` passes `bash -n` (parse-only; the script is never executed).
2. `test_all_python_scripts_byte_compile` — every `scripts/**/*.py` passes `py_compile` (byte-compile; never imported — no side effects). `__pycache__` excluded.
3. `test_osctl_dispatch_targets_resolve` — every `cmd_*` that `sovereign-osctl` *calls* is *defined* (called-set ⊆ defined-set), so a dispatch verb routed to a missing handler is caught in CI instead of at the operator's terminal. Grep-based on the call/definition token sets — robust to the 9k-line bash case grammar, no execution.

## Verification

- `python3 -m pytest tests/lint/test_scripts_health_baseline.py` — **3 passed** (102 sh parse; 299 py compile; osctl 29 called ⊆ 29 defined).
- `ruff check` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Running the scripts** — `bash -n` / `py_compile` are parse/compile only; behavior/integration is out of scope (and covered elsewhere by the layer-2/3 harness).
- **Re-guarding the port map / systemd pairing** — already held by `test_dashboard_port_and_reference_integrity.py`; this covers the orthogonal parse/compile/dispatch axis.
- **Refactoring the 9,101-line osctl monolith** — that's F-2026-025 (separate, larger); this only guards its dispatch integrity.

## Safety invariants

New read-only pytest lint only — no scripts touched, no scripts executed (parse/compile never runs code), no crate code, no runtime, no gateway. Recomputes from what the repo already ships. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `tests/lint/test_scripts_health_baseline.py` — the contract
- `scripts/sovereign-osctl` — the dispatch surface guarded (part 3)
- `tests/lint/test_dashboard_port_and_reference_integrity.py` — the sibling port-map/pairing baseline
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-020 (source)
- SDD-974 — the crate-hygiene baseline contract (same self-maintaining discipline, crate surface)
- SDD-968 — the shell-safety-flags entry-point contract (sibling scripts-surface guard)
- SDD-100 — the per-session number-band convention
