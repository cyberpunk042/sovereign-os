# SDD-055 — LM orchestration wiring (functional apply / load / toggle / override / eval for D-21 + D-22)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-08
> Closes findings: none (a wiring pass — reuses existing controls, no new engine)
> Derived from: operator directive 2026-07-08 (chose the D-21/D-22 LM-orchestration panels after SDD-054's eval-history wiring merged in PR #32); SDD-047 (cockpit functional execution / R10274 — `runtime-mode` + `inference-tier` controls); SDD-054 (the d-10 wiring precedent); SDD-049 (model runtime) + SDD-051 (adapters); M075 SRP topology; M076 runtime-mode profiles.

## Mission

Complete the D-21 (LM orchestration) + D-22 (LM status & operability) panels'
functional execution. Like SDD-054 (D-10), these are **pure re-wires**: every
panel button maps onto a control that ALREADY exists — no new writer, no new
control, no lint count change.

## Problem

Both panels already carry the full inline control-surface (`/api/control/execute`
+ cs-exec buttons) and reuse D-03's `model-health.py` grid + M076 runtime-mode
profiles + M075 topology. But their panel-specific action buttons still
clipboard-copy the real CLI verb instead of executing:

- **D-21 `apply-btn`** — copies `sovereign-osctl trinity profile switch <profile>`
  → the existing **`runtime-mode`** control (change_cli `trinity profile switch
  <id>`), but that control's `applies_to` doesn't include d-21, so it doesn't
  render in D-21's rail.
- **D-22 `.act` buttons** — copy real verbs mapping to existing controls:
  `load`/`toggle` → `inference start|restart <tier>` = **`inference-tier`**;
  `override` → `trinity profile switch` = **`runtime-mode`**; `eval`/`bench` →
  `models eval` = **`eval-run`**. None of those controls' `applies_to` includes
  d-22.
- **D-22 `chat-send`** — genuinely deferred: no single-prompt inference CLI exists
  (inference is start/stop/status/health per tier); live chat awaits the M058
  inference producer. It already copies a REAL `inference status` verb with an
  honest note — kept as honest-deferred (not a phantom).

## Required coverage

- **Extend three controls' `applies_to`** in `config/control-systems.yaml`:
  - `runtime-mode` += `d-21-lm-orchestration`, `d-22-lm-status-operability`
  - `inference-tier` += `d-21-lm-orchestration`, `d-22-lm-status-operability`
  - `eval-run` += `d-22-lm-status-operability`
  so the controls render in these panels' control-surfaces. No new control, no
  count change (still 28); exec allowlists + sudoers entries unchanged — only the
  render-target lists widen.
- **D-21 webapp re-wire**: a shared `jumpToControl(cid)` helper; `apply-btn` →
  `jumpToControl('runtime-mode')`.
- **D-22 webapp re-wire**: `jumpToControl` helper; `.act` `load`/`toggle` →
  `jumpToControl('inference-tier')`; `override` → `jumpToControl('runtime-mode')`;
  `eval`/`bench` → `jumpToControl('eval-run')`; `chat-send` kept honest-deferred
  (M058-pending note; copies a real status verb — no phantom).
- Both panels keep their `/api/lm-orchestration/*` + `/api/lm-status/*` fetches
  (contract tests); the read APIs stay read-only.

## Goals

- Every D-21/D-22 actionable button resolves to a real functional control or a
  live read / honest-deferred note; no fake `sovereign*` clipboard strings.
- Reuse the existing gated controls (`runtime-mode`, `inference-tier`, `eval-run`)
  — no new mutation path.
- R10212 unchanged: selfdef/perimeter untouched; the LM read APIs stay read-only;
  the widened controls keep their exec allowlists + sudoers unchanged.

## Non-goals (Stage 2 / follow-up)

- Live single-prompt **chat** inference (needs the M058 inference producer).
- A dedicated per-device **bench** control (bench reuses `eval-run` now).
- Surfacing the full model-load/unload/warm set inline on D-21/D-22 (available via
  D-03; can be added to `applies_to` later if the operator wants them in-panel).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-055-A | Which controls to surface on D-21/D-22. | **answered (operator, 2026-07-08 — via the button map): runtime-mode + inference-tier on both; eval-run on d-22.** |
| Q-055-B | `chat-send` (no inference-chat CLI). | **answered: keep honest-deferred — copies a real `inference status` verb + M058-pending note; live chat is Stage 2 (M058 producer).** |
| Q-055-C | Dedicated per-device `bench` control. | **proposed: reuse `eval-run` now; a device-scoped bench runner is a Stage-2 follow-up.** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `config/control-systems.yaml` applies_to extensions (runtime-mode,
  inference-tier, eval-run) + D-21 + D-22 webapp re-wires (jumpToControl helpers).
  No new scripts/tests — a wiring change verified by the existing contract +
  control lints.
- **Stage 2 (follow-up):** M058 chat inference producer; device-scoped bench.

## Safety invariants

No new mutation path — reuses the already-gated `runtime-mode` + `inference-tier`
+ `eval-run` controls (operator-key + type-to-confirm + DRY-RUN default at the
exec rail); selfdef/perimeter untouched; the LM read APIs stay read-only; the
widened controls' exec allowlists + sudoers entries are unchanged — only their
render-target (`applies_to`) lists widen.

## Cross-references

- `config/control-systems.yaml` — `runtime-mode` / `inference-tier` / `eval-run`,
  reused here (not re-authored); `applies_to` widened.
- `scripts/operator/lm-orchestration-api.py` + `lm-status-operability-api.py` —
  read-only daemons.
- `webapp/d-21-lm-orchestration/index.html` + `webapp/d-22-lm-status-operability/index.html`
  — the re-wired panels.
- SDD-054 (eval-history wiring — the precedent), SDD-047 (cockpit functional
  execution), SDD-049 (model runtime), SDD-051 (adapters).
