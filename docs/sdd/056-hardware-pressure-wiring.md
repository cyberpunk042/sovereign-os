# SDD-056 — Hardware-pressure wiring (functional zpool-scrub for D-09)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: none (a wiring pass — reuses the existing maintenance control, no new engine)
> Derived from: operator directive 2026-07-08 (chose to finish D-09 hardware-pressure after SDD-055's LM-orchestration wiring merged in PR #33, closing out the cockpit control-wiring sweep); SDD-047 (cockpit functional execution / R10274 — the `maintenance` control); SDD-054/055 (the d-10/d-21/d-22 wiring precedents).

## Mission

Complete the last cockpit control-wiring: make the D-09 hardware-pressure
`zpool scrub` button execute via the existing `maintenance` control instead of
clipboard-copying the CLI. This closes the "make dashboard controls functional"
sweep (nine panels wired across PRs #24–33).

## Problem

D-09 already carries the full inline control-surface, and the `maintenance`
control (`sovereign-osctl maintenance {scrub|arc-status|log-rotate|snapshot|
security-check|models-sync|perimeter-check|alerts-check}`) already has
`applies_to: [d-09-hardware-pressure]` — so it already renders in D-09's rail. But
the panel's `scrub-btn` still clipboard-copies `sovereign-osctl maintenance scrub`
and merely *points* the operator to the Maintenance control card.

The `dcgm-export-btn` copies a real read-only telemetry command
(`dcgmi dmon …`) — an observability diagnostic, not a sovereign-os mutation and
not a control. It stays an honest copy.

## Required coverage

- **D-09 webapp re-wire**: a shared `jumpToControl(cid)` helper; `scrub-btn` →
  `jumpToControl('maintenance')` (the control already renders on D-09 — no config
  change needed). `dcgm-export-btn` kept as an honest read-only telemetry copy.
- **No control change** — `maintenance.applies_to` already includes
  d-09-hardware-pressure; registry stays 28; no lint count bumps.

## Goals

- The D-09 `zpool scrub` button executes via the sanctioned `maintenance` control
  (operator-key + type-to-confirm + DRY-RUN default at the exec rail).
- R10212 unchanged: selfdef/perimeter untouched; the hardware-pressure read API
  stays read-only; the `maintenance` control's exec allowlist + sudoers entry are
  unchanged (it was already wired for D-09).

## Non-goals (follow-up)

- A dedicated DCGM-export control (the copy is a read-only diagnostic; no host
  mutation to gate).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-056-A | Finish D-09 vs a deferred Stage-3 backend. | **answered (operator, 2026-07-08): finish D-09 — the last control-wiring, closing the sweep.** |
| Q-056-B | `dcgm-export-btn` treatment. | **proposed: keep as an honest read-only telemetry copy (real `dcgmi` cmd; no mutation to gate).** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `webapp/d-09-hardware-pressure/index.html` re-wire (jumpToControl
  helper; scrub-btn → maintenance). No config/script/test change — verified by the
  existing D-09 contract + control lints.

## Safety invariants

No new mutation path — reuses the already-gated `maintenance` control (which was
already wired for D-09); selfdef/perimeter untouched; the hardware-pressure read
API stays read-only; no config or exec-allowlist change.

## Cross-references

- `config/control-systems.yaml` — the `maintenance` control (reused; already
  `applies_to: [d-09-hardware-pressure]`).
- `webapp/d-09-hardware-pressure/index.html` — the re-wired panel.
- SDD-054 (eval-history wiring), SDD-055 (LM-orchestration wiring) — the
  wiring precedents; SDD-047 (cockpit functional execution).
