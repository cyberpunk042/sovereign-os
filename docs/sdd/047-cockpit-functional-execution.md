# SDD-047 — Cockpit functional execution (realize R10274: panels EXECUTE, command becomes the fallback)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-08
> Closes findings: none (execution layer atop SDD-045's control surface)
> Derived from: operator directive 2026-07-08 (verbatim, sacrosanct): *"we now have a sudoer strategy, we will fix everything that is a manual command so that the manual command is only the alternative but we will otherwise do the features functional from the panels / dashboard, this mean all existing one including the new ones ... This is massive evolution take your time to do it well."*; SDD-045 (Universal Dashboard Contract / control-surface); SDD-040 (D-040.6 R10274 signed-mutation proxy); SDD-024 (server-hardening posture); SDD-015 (MS003 / MOK signing)

## Mission

Every cockpit panel today is strictly **READ-ONLY**: action buttons copy an
MS003-signed CLI verb to the clipboard (`navigator.clipboard.writeText`) and the
43 `scripts/operator/*-api.py` daemons `_reject()` POST/PUT/DELETE → 405. The
operator directive is to make the panels **functionally execute** the feature,
demoting the copyable command to the documented fallback.

This is **not** a new doctrine — it is the functional realization of **R10274**
(the sanctioned "mutation proxies via an MS003-signed request" escape hatch,
until now implemented only as clipboard-copy; SDD-040 D-040.6). **R10212 is
preserved**: the web still never *arbitrarily* mutates — it executes only a verb
that is allowlisted, placeholder-validated, confirmed, and audited.

## Problem

Three gaps sit between "copy the command" and "execute the feature":

1. **No execution primitive over HTTP.** The daemons are read-only by design. The
   single existing HTTP→privileged path is `build-configurator-api.py` `/api/run`
   (`RUN_ACTIONS` allowlist + regex-validated args + single-flight `RUN_LOCK` +
   interactive `pkexec` + `operator_key_env()` + streamed stdout) — the pattern to
   generalize, not a general control executor.
2. **No non-interactive "sudoer strategy" exists yet.** The operator states one
   now exists; the merged tree contains only interactive `pkexec`. The mechanism
   is a security-envelope decision (Q-047-A) and shapes everything downstream.
3. **A load-bearing boundary must not break.** `config/control-systems.yaml`
   registers 11 controls; **2 are selfdef-owned** (`selfdef`, `perimeter` — their
   `state_path` is selfdef units / tetragon). sovereign-os is the READ-ONLY
   *consumer* of the selfdef IPS (R10212); those must stay a signed proxy request
   to the selfdef producer, never executed locally. Only the **9 sovereign-os-owned**
   controls execute locally.

## Required coverage

| Surface | Count | Change |
|---|---|---|
| Shared control-surface controls | 11 (9 local + 2 proxy) | `webapp/_shared/control-surface.js` renders an **Execute** button (+ confirm gate for privileged) with **Copy** demoted to fallback; ONE change lights all 47 panels' control rail. |
| Cockpit panels | 47 | Each `webapp/*/index.html` control rail becomes executable for its `applies_to` controls; selfdef-domain panels (D-13..D-18, selfdef-management, perimeter) stay copy-only proxy. |
| Per-panel hand-written buttons | ~175 | `emit(cmd)`/`copyApply()` → a shared `executeOrCopy(control,args)` helper (primary = execute, secondary = copy); sovereign-os-owned only. |
| Read-only daemons | 43 (41 explicit 405 + 2 by omission) | sovereign-os-owned daemons gain a validated execute handler; selfdef-boundary daemons keep `_reject()`. |
| Contracts asserting 405/clipboard-only | ~48 (30 `*_api_contract` + 15 `*_webapp_contract` + 3 in `test_control_surface_component.py`) | Invert for sovereign-os-owned surfaces to assert the new contract (valid allowlisted action → 200 + audit; invalid / boundary → 4xx; unconfirmed privileged → 403); keep selfdef-boundary 405 tests. |
| Execution primitive | 1 | `scripts/operator/_action_exec.py` (**Phase 0 — SHIPPED**). |
| Sudoer allowlist | 1 | `config/sudoers.d/sovereign-os-cockpit` (**Phase 0 — DRAFT, review-pending**). |

## Goals

- Panels execute the **9 sovereign-os-owned** controls end-to-end (state changes +
  OCSF-5001 audit span), with the manual `sovereign-osctl …` command as fallback.
- Preserve R10212: selfdef-owned mutations remain a signed proxy to selfdef.
- Two-gate defence: app-layer placeholder validation (`options` allowlist / strict
  no-shell-metacharacter regex) **and** the sudoer binary+verb allowlist.
- Every privileged execution gated on operator-key presence + explicit type-to-confirm
  (`crates/sovereign-cockpit-destructive-confirm`) and audited (OCSF-5001 +
  `crates/sovereign-cockpit-audit-trail`).
- Reuse, don't reinvent: `build-configurator-api.py` execution pattern,
  `control-systems.yaml` registry, existing confirm/audit/operator-key primitives.

## Non-goals

- Executing selfdef-owned controls locally (stays a signed proxy — unless Q-047-B
  is answered otherwise).
- A general web→root bridge; execution is strictly the fixed control allowlist.
- Live inference/chat invocation (separate surface; unchanged here).
- Redesigning the control-surface UX (SDD-045 owns the 5-region skeleton).

## Open questions

| Q | Question | Options | Status |
|---|---|---|---|
| Q-047-A | The sudoer strategy mechanism | **(A)** NOPASSWD sudoers allowlist run as the operator user; (B) root helper daemon; (C) interactive `pkexec`; (D) operator already added a sudoer artifact | **answered (evidence, 2026-07-08)** — option **D**: the strategy is `scripts/operator/operator-sudoers.sh` (already on `main`), which generates `/etc/sudoers.d/sovereign-os-operator` granting the **operator user** (that the panel APIs + agent run as) a scoped `Cmnd_Alias SOVEREIGN_OS_OPS` NOPASSWD allowlist (today: diagnostics + image-inspection only, absolute paths, never `ALL`; contract locked by `tests/lint/test_operator_sudoers.py` + `test_root_password_gate.py`). The functional-execution work **extends that generator** with a controls bucket (the 9 sovereign-os-owned `sovereign-osctl <verb>` commands as a second scoped alias) — NOT a parallel hand-authored file. |
| Q-047-B | selfdef-owned controls (selfdef/perimeter/D-12..D-18) | Stay a signed proxy to selfdef (recommended, preserves R10212 producer/consumer) vs execute locally | **open** — default: stay proxy |
| Q-047-C | systemd privilege model | Whether a dedicated user / `NoNewPrivileges` change is needed | **answered (evidence, 2026-07-08)** — **no** dedicated user and **no** `NoNewPrivileges` drop: the panels run **as the operator user** (per `operator-sudoers.sh`), so `_action_exec` runs `sudo -n sovereign-osctl <verb>` as that user against the extended allowlist. Supersedes the Phase-0 draft's `sovereign-cockpit` dedicated-user assumption. |
| Q-047-D | Landing strategy | The dev branch is an unrelated history vs a fast-moving `main`; CI merges surface main's newer code the behind-branch lacks (proven: my `mkosi-emit.sh` is the old `Format=none`; main is the fixed `Format=ext4`). Only 67 files differ (40 added = my clean deliverable; the rest are main-ahead modifications + main-only files INCLUDING `operator-sudoers.sh`). Recreate the branch from `origin/main` + re-apply the 40-file deliverable (reconciled to extend `operator-sudoers.sh`), vs patch drift against a moving target | **open (strongly recommend recreate)** — it also brings in `operator-sudoers.sh` (the real sudoer strategy this SDD builds on) |

## Way forward

- **Phase 0 — execution primitive (SHIPPED, commit `059f076c`).**
  `scripts/operator/_action_exec.py`: loads the registry; hard-rejects the 2
  selfdef-owned controls; validates placeholders; gates privileged on key +
  confirm; executes via `_privileged_argv()` (mechanism-isolated `sudo -n`);
  single-flight lock; OCSF-5001 audit span + a Prometheus counter
  (`sovereign_os_operator_cockpit_action_total{control_id,outcome}`) for
  operability. DRY_RUN by default (import changes nothing).
  Tests: `tests/unit/test_action_exec.py` (30) +
  `tests/lint/test_cockpit_action_exec_sudoers.py` (4 drift-guards). **Touches no
  live daemon/systemd unit.**
  **Reconciliation (post-recreate, per Q-047-A/C answers):** the Phase-0
  `config/sudoers.d/sovereign-os-cockpit` DRAFT (dedicated `sovereign-cockpit`
  user, parallel file) is SUPERSEDED — replace it by extending
  `scripts/operator/operator-sudoers.sh`'s generator with a `SOVEREIGN_OS_COCKPIT`
  controls alias (the 9 owned `sovereign-osctl` verbs) for the **operator user**,
  and point `_action_exec` at that. The `_action_exec.py` core (validation,
  boundary, gating, metric, audit) is unchanged; only the sudoers artifact + user
  model reconcile to main's pattern.
- **Phase 1 — shared control-surface execute (gated on Q-047-A/C).** Extend
  `webapp/_shared/control-surface.js` with an Execute button (+ confirm gate) and
  a sovereign-os-owned `/api/control/execute` endpoint on the owning daemons; Copy
  becomes the labelled fallback. Highest leverage (one renderer → 47 panels).
- **Phase 2 — per-panel buttons (~175), sovereign-os-owned only,** panel-by-panel
  via `executeOrCopy`; selfdef-domain panels stay copy-only.
- **Phase 3 — invert the contracts.** Update the ~48 read-only-asserting tests to
  the new contract; add write handlers to the 2 read-only-by-omission daemons
  (`four-watchdog-api.py`, `runtime-modes-api.py`); keep selfdef-boundary 405 tests.

Each phase is its own commit(s), green `tests/lint tests/unit tests/schema` before
the next. Q-047-A/B/C resolve before Phase 1; when answered, append `D-NNN` to
`docs/decisions.md` and annotate the Q rows here in place.

## Cross-references

- **SDD-045** — Universal Dashboard Contract / `webapp/_shared/control-surface.{js,css}` + `config/control-systems.yaml` (the control surface this SDD makes executable).
- **SDD-040** — D-040.6 R10212 (web READ-ONLY) + R10274 (MS003-signed mutation proxy) — the doctrine realized here.
- **SDD-024** — server-hardening posture (auditd/pwquality: sudo stays audited; the sudoer strategy is the deliberate, scoped exception).
- **SDD-015** — MS003 / MOK operator signing (`operator_key_env()`, `operator_key_status()`).
- `scripts/operator/_action_exec.py` · `config/sudoers.d/sovereign-os-cockpit` · `scripts/operator/build-configurator-api.py` (`_run_action`) · `crates/sovereign-cockpit-destructive-confirm` · `crates/sovereign-cockpit-audit-trail` · `scripts/manifest/dashboard-toggles.py` (`_emit_ocsf_5001`) · `scripts/lifecycle/approval-queue.py` (`operator_key_status`).
