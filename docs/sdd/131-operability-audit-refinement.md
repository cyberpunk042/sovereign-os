# SDD-131 — Phase 3: controls-audit refinement (R10212-honest classification)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the SDD-130 audit's flat "12 copy-only" worklist was misleading — a recon of every worklist panel showed most are NOT wiring gaps. This refines `controls-audit.py` to classify by the action's TRUE nature so the worklist tells the truth (and doesn't propose changes that would violate R10212). Recover band (SDD-131 / E11.M131 per SDD-100).
> Derived from / extends: SDD-130 (the audit). §1g.

## Mission

Correct the audit's classification so Phase-3 wiring targets the real, safe gaps only.

## What the recon found (per-panel, verified against source + control-surface.js + control-systems.yaml)

- **d-08 / d-21 / d-22** — already **fully exec-rail-wired**; every action button calls `jumpToControl(<cid>)`.
  The "copy-only" the flat audit flagged is dead/neutralized leftover (`copyCmd`/`actionCmd` with no
  callers; an `emit()` that copies nothing). Not a gap.
- **d-12 / d-13 / d-14 / d-15 / d-16 / d-17 / d-18** — copy `selfdefctl …` verbs. `selfdef`/`perimeter`
  are **PROXY_ONLY / SELFDEF_OWNED** (`control-surface.js` `PROXY_ONLY`; `_action_exec.SELFDEF_OWNED`):
  the web may **never** execute them locally (R10212). Their cards render copy-only *by design* — wiring
  them would violate the security boundary. **Copy-only is correct here, not a gap.**
- **d-20-peace-machine-health** + **profile-generation** — the only genuine gaps: each copies a
  non-selfdef sovereign command (`sovereign-os-peace-check`, `sovereign-osctl profiles generate-runtime`)
  with no `jumpToControl`. **But neither has a matching control in `config/control-systems.yaml`** (no
  `applies_to` entry, no matching `change_cli` verb), so each needs a **new registry control** before the
  copy→`jumpToControl` swap — a security-sensitive decision (exposing those verbs to the exec-rail).

## Grounded design (read-only tooling)

`controls-audit.py` now classifies each panel as:
- **wired** — calls `jumpToControl` (actions execute via `/api/control/execute`).
- **proxy-copy-only** — emits a `selfdefctl` command → copy-only by R10212 design (NOT a gap; excluded
  from the worklist).
- **wireable-gap** — copies a non-selfdef sovereign command with no `jumpToControl` → a real gap (needs a
  matching registry control first).
- **no-actions** — nav / view-only.

Result: **9 wired · 7 proxy-copy-only · 2 wireable-gap (d-20, profile-generation) · 34 no-actions.** The
baseline + regression lint are regenerated to the corrected schema.

## Way forward — operator decision

The realistic Phase-3 wiring surface is **2 panels**, each requiring a **new exec-rail control** (a
security choice — the exec daemon's allowlist + dry-run/key/confirm gating). Options for the operator:
(a) add a read-mostly `peace-check` control (`applies_to: d-20`) + a `profiles-generate-runtime` control
(`applies_to: profile-generation`), then wire both; or (b) leave them copy-only (they're already honest —
the command is shown to copy). The selfdef family stays copy-only regardless (R10212).

## Verification

- `make controls-audit` shows the corrected classification; `pytest tests/lint/test_controls_audit_baseline.py`;
  full `make test`. Read-only — no behaviour change, no web mutation.

## Cross-references

- SDD-130 (audit); `webapp/_shared/control-surface.js` `PROXY_ONLY`; `config/control-systems.yaml`. SDD-100 — band scheme.
