# SDD-132 — Phase 3: wire the 2 genuine gaps to the exec-rail (peace-check + profiles-generate-runtime)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the SDD-131 R10212-honest audit found exactly 2 wireable gaps. Operator chose "wire both" (2026-07-10). This adds the 2 exec-rail controls + swaps those panels' copy→`jumpToControl`, so **0 wireable-gap** remain. Both controls are sovereign-os-owned + read-only + **non-privileged** (no sudoers grant); R10212 is intact — the exec daemon stays the only write path. Recover band (SDD-132 / E11.M132 per SDD-100).
> Derived from / extends: SDD-130/131 (audit); SDD-048/049/051/052 (exec-rail wiring). §1g.

## Mission

Wire `d-20-peace-machine-health` and `profile-generation` so their actions execute from the cockpit via
the sanctioned exec-rail (dry-run + operator-key + type-to-confirm), instead of copy-pasting a command.

## Grounded design

- **`config/control-systems.yaml`** — 2 new controls (both `privileged: false`, `scope: scoped`,
  `kind: lifecycle`):
  - **`profiles-generate-runtime`** (`applies_to: [profile-generation]`) —
    `change_cli: sovereign-osctl profiles generate-runtime <hw> {efficiency|high-concurrency|deep-context}`.
    Read-only (prints to stdout).
  - **`peace-check`** (`applies_to: [d-20-peace-machine-health]`) — `change_cli: sovereign-osctl peace-check --json`.
    Read-only (the validator computes + publishes; nothing mutates host state).
- **`scripts/sovereign-osctl`** — a thin `peace-check)` verb `exec /usr/bin/sovereign-os-peace-check "$@"`
  (required because `change_cli` must start with `sovereign-osctl`, and the validator is a standalone
  binary, not otherwise an osctl subcommand). `profiles generate-runtime` already exists.
- **`tests/lint/test_control_systems_registry.py`** — the 2 ids added to `EXPECTED_IDS` (exact-set lint).
- **Panels** — each gains the standard `jumpToControl(cid)` fn + a "▶ run via controls" / "▶ re-run
  (controls)" button that scrolls to + highlights the control card (which executes via the exec-rail).
  The existing CLI-verb copy stays as the labelled fallback (never removed). Both panels already embed
  their control-surface with the correct `filterSlug`, so the new cards render.
- **`scripts/webapp/controls-audit-baseline.json`** — regenerated: both panels flip copy→**wired**.

## R10212 preserved

Both controls are sovereign-os-owned (NOT in `SELFDEF_OWNED`/`PROXY_ONLY`), options-validated
(`_SAFE_VALUE` + `options`), OCSF-5001 audited, **dry-run by default**, and — being read-only /
non-privileged — carry **no new sudo grant**. The web never mutates directly; the exec daemon is the
only write path. Verified: `_action_exec.execute()` dry-run returns `code 200` with the correct
`argv` for both (`['sovereign-osctl','profiles','generate-runtime','sain-01','high-concurrency']` and
`['sovereign-osctl','peace-check','--json']`).

## Verification

- Registry lint (`EXPECTED_IDS` + fields + `applies_to` slugs), audit baseline lint, execute-boundary lint.
- `make controls-audit`: **11 wired · 7 proxy-copy-only · 0 wireable-gap · 34 no-actions.**
- `bash -n scripts/sovereign-osctl`; exec-rail dry-run (code 200) for both; `demo-capture` regression on
  the 2 panels; full `make test`.

## On completion

Phase 3 wiring is complete — every genuinely wireable panel action now executes from the cockpit; the
selfdef family stays copy-only by R10212 design. Remaining Phase-3 items (non-security): master-dashboard
front-door fix + cross-panel deep links + Cmd-K palette coverage.

## Cross-references

- SDD-130/131 (audit); `scripts/operator/_action_exec.py` (exec-rail); `config/control-systems.yaml`. SDD-100 — band scheme.
