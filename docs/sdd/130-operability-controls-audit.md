# SDD-130 — Phase 3 (operability) kickoff: read-only controls audit

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: Phase 3 of the roadmap — god-tier operability ("no manual commands"). Operator picked Phase 3 as the next direction after the DEMO rollout (Phase 1) completed at 52/52. This first increment is the **read-only controls audit**: enumerate which panel action affordances already execute via the sanctioned R10274 exec-rail vs which are still copy-only, producing the ranked worklist that sequences the wiring PRs. Recover band (SDD-130 / E11.M130 per SDD-100).
> Derived from / extends: SDD-048/049/051/052 (exec-rail wiring precedent), SDD-123 (tooling discipline). §1g.

## Mission

Ship a read-only audit tool + baseline so the operability work is measured, sequenced, and regression-
guarded — before touching a single action. No behaviour change; no web mutation.

## Grounded design (read-only)

- **`scripts/webapp/controls-audit.py`** — classifies each panel's panel-specific action affordances:
  - **exec-rail** — wired to the exec-rail via `jumpToControl(<cid>)` (the control card executes via
    `/api/control/execute`, dry-run + operator-key + type-to-confirm). Actions run from the cockpit.
  - **copy-only** — still emits a `sovereign-osctl …` command to the clipboard (`copyCmd`/`copyApply`/
    active `emit`) for the operator to paste + run.
  - **neutral / no-actions** — navigation / view-only. The shared `SovereignControlSurface` cards are
    excluded (they already execute via the rail by design — the audit measures the gap, not the baseline).
- **`make controls-audit`** (+ `JSON=1`) prints a per-panel table + the ranked worklist.
- **`scripts/webapp/controls-audit-baseline.json`** — the committed snapshot; the lint
  (`tests/lint/test_controls_audit_baseline.py`) fails if a wired panel regresses to copy-only or the
  baseline goes stale, so each wiring PR regenerates it as the live progress tracker.

## Current state (baseline)

52 panels — **6 exec-rail wired, 12 with copy-only actions, 34 with no panel-specific actions.**

**Ranked wiring worklist (Phase-3 PRs, most copy-only first):** d-08-rollback-points (partial),
d-21-lm-orchestration (partial), d-22-lm-status-operability (partial), then the selfdef family
(d-12-networking, d-13-filesystem-grants, d-14-capability-tokens, d-15-sandboxes, d-16-audit,
d-17-quarantine), d-18-trust-scores, d-20-peace-machine-health, profile-generation. (Regenerate anytime
with `make controls-audit`.)

## Way forward

- **This SDD** — the audit tool + baseline + Make target + regression lint.
- **Next** — wire the worklist panel-by-panel: for each copy-only action, map it to its
  control-systems registry entry, replace the clipboard-copy with `jumpToControl(<cid>)` (ensuring the
  control card exists in that panel's control-surface), keep the signed-CLI-verb copy as the fallback, and
  regenerate the baseline. **R10212 stays intact** — the exec daemon remains the only write path
  (dry-run + operator-key + type-to-confirm); the web never mutates directly. Then master-dashboard
  front-door fix + cross-panel deep links.

## Cross-references

- SDD-048/049/051/052 (exec-rail wiring); the R10274 exec-rail (`/api/control/execute`). SDD-100 — band scheme.
