# SDD-054 — Eval-history wiring (functional run-suite / promote / export for D-10)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-08
> Closes findings: none (a wiring pass — reuses existing controls, no new engine)
> Derived from: operator directive 2026-07-08 (chose the D-10 eval-history panel after SDD-053's session lifecycle merged in PR #31); SDD-047 (cockpit functional execution / R10274 — the `eval-run` control); SDD-051 (adapter promotion — the `adapter-decide` control); M060 R10106-R10108 (D-10 read model).

## Mission

Complete the D-10 eval-history panel's functional execution. Unlike SDD-048..053
(six greenfield engines), D-10 is a **pure re-wire**: its actionable buttons map
onto controls that ALREADY exist — no new writer, no new control, no lint count
change.

## Problem

Three D-10 buttons, mixed state:
- **`run-suite-btn`** — already FUNCTIONAL (jumps to the `eval-run` control,
  SDD-047 PR #25; `applies_to: [d-10-eval-history]`).
- **per-adapter `promote`** — NEUTRALIZED (`alert('planned')`). It maps to the real
  `adapter-decide` control (SDD-051 PR #29), but that control's `applies_to` was
  `[d-11-adapter-status]` only, so it did NOT render in D-10's control-surface.
- **`export-btn`** — NEUTRALIZED (fake `sovereign eval` export).

## Required coverage

- **Extend `adapter-decide.applies_to`** to `[d-11-adapter-status,
  d-10-eval-history]` — so the promote control renders in D-10's rail too. The
  eval-history panel shows adapters pending promotion with their eval gains, so
  signing off a promotion from there is the natural surface. No new control, no
  count change (still 28); the control's exec-allowlist + sudoers entry are
  unchanged — only its render-target list widens.
- **d-10 webapp re-wire** (honest surface, per "we do not minimize"): a shared
  `jumpToControl(cid)` helper; per-adapter `promote` → `jumpToControl('adapter-decide')`;
  `run-suite-btn` → `jumpToControl('eval-run')` (same behavior, shared helper);
  `export-btn` → a real client-side CSV from the live `/api/evals/summary` (a read,
  no host mutation).

## Goals

- Every D-10 actionable button resolves to a real functional control or a live
  read; no fake `sovereign*` clipboard strings remain.
- Reuse the existing gated controls (`eval-run`, `adapter-decide`) — no new
  mutation path.
- R10212 unchanged: selfdef/perimeter untouched; `evals-api.py` stays read-only
  (405); the widened control keeps its exec allowlist + sudoers unchanged.

## Non-goals (Stage 2 / follow-up)

- A dedicated multi-benchmark `eval-suite` runner (batched, WB/BB-disaggregated) —
  the single `eval-run` control covers per-benchmark runs now.
- Inline per-row adapter promote/demote/rollback (vs the shared control card).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-054-A | `adapter-decide` cross-panel render (D-10 too?). | **answered (operator, 2026-07-08): extend `applies_to` to include d-10-eval-history — eval-history is a natural adapter-promotion surface.** |
| Q-054-B | `export-btn` scope. | **answered (operator, 2026-07-08): real client-side CSV from the live eval summary (a read).** |
| Q-054-C | Dedicated multi-benchmark suite runner vs reuse single `eval-run`. | **proposed: reuse `eval-run` now; a batched suite runner is a Stage-2 follow-up.** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `config/control-systems.yaml` adapter-decide `applies_to` += d-10;
  `webapp/d-10-eval-history/index.html` re-wire (jumpToControl helper; promote →
  adapter-decide; run-suite → eval-run; export → client-side CSV). No new scripts
  or unit tests — a wiring change verified by the existing D-10 contract + control
  lints.
- **Stage 2 (follow-up):** batched eval-suite runner; inline per-row adapter ops.

## Safety invariants

No new mutation path — reuses the already-gated `eval-run` + `adapter-decide`
controls (operator-key + type-to-confirm + DRY-RUN default at the exec rail);
selfdef/perimeter untouched; `evals-api.py` stays read-only (405); export is a
client-side read. The `adapter-decide` control's exec allowlist + sudoers entry
are unchanged — only its render-target (`applies_to`) widens.

## Cross-references

- `config/control-systems.yaml` — `eval-run` (SDD-047) + `adapter-decide`
  (SDD-051), reused here (not re-authored); adapter-decide `applies_to` widened.
- `scripts/operator/evals-api.py` — read-only daemon (stays 405).
- `webapp/d-10-eval-history/index.html` — the re-wired panel.
- SDD-047 (cockpit functional execution / eval-run), SDD-051 (adapter promotion /
  adapter-decide), SDD-053 (session lifecycle — the prior engine).
