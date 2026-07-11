# SDD-139 — Phase 4: ux-design-audit score baseline + regression guard

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: the Phase-4 roadmap listed "the ux-design-audit six-dimension sweep", imagined as fixing low-scoring cockpit panels. Recon corrected the premise: the `ux-design-audit` scorer (`scripts/operator/ux-design-audit.py`, a §1g instrument like surface-map / doc-coverage) does NOT score cockpit HTML — it scores **9 backend operator modules** by reading their source + osctl help, and **all 9 already pass** its default gate (`DEFAULT_THRESHOLD=4`, 0 below). The scorer is real + computed but had **no score baseline + regression guard** — unlike its sibling `controls-audit` (producer + `controls-audit-baseline.json` + `test_controls_audit_baseline.py`). So a module could silently drop a dimension and every existing ux lint (which assert the machinery exists, not that scores hold) stayed green. Recover band (SDD-139 / E11.M139 per SDD-100).
> Derived from / extends: SDD-130 (controls-audit baseline trio — the pattern mirrored here). §1g.

## Mission

Lock the ux-design-audit's current all-passing state with a committed baseline + a regression guard, so no operator module can silently lose a UX dimension.

## Grounded design (test + docs + one committed JSON — no backend-script edits)

The producer already emits the snapshot: `python3 scripts/operator/ux-design-audit.py score --json` → `{"scores":[{module,score,total}],"count":9}`.

- **`scripts/operator/ux-design-audit-baseline.json`** — committed `score --json` snapshot. Current scores: `auth-tier`, `edge-firewall`, `master-dashboard` = **6/6**; `network-edge`, `global-history`, `surface-map`, `doc-coverage`, `anti-minimization-audit` = **5/6** (each fails only `next-step`); `bashrc` = **4/6** (fails `next-step` + `recoverable`).
- **`tests/lint/test_ux_design_audit_baseline.py`** (mirrors `tests/lint/test_controls_audit_baseline.py`): reruns `score --json`; asserts it covers all 9 `MODULES`; asserts **no module's score regressed below baseline** (`live[m] >= baseline[m]` — the durable guard); asserts the baseline is current (a *raised* score means the PR forgot to regenerate it). Raising a score is fine (regenerate the baseline in the same PR); dropping one fails here.

## R10212 / SB-077 preserved

Test + one snapshot JSON. No backend-script edit, no behavior change, nothing fabricated. R10212 untouched.

## Verification

- `python3 -m pytest tests/lint/test_ux_design_audit_baseline.py -q` — passes on the current tree (baseline == live: 9 modules, scores as above).
- Full `make test` green.

## On completion

The ux-design-audit now has the same producer → baseline → regression-lint trio as controls-audit. Remaining Phase 4 (operator-selectable): raise the 6 shortfall modules to 6/6 (genuine next-step hints in their CLI output + a `--apply`/`--confirm` dry-run gate for `bashrc-install.sh` — a real install-safety change deserving its own operator-greenlit SDD); a spacing/typography/empty-state visual-consistency pass across cockpit panels.

## Cross-references

- Producer `scripts/operator/ux-design-audit.py` (`cmd_score`, `MODULES`, `DIMENSIONS`); sibling trio `scripts/webapp/controls-audit.py` + `scripts/webapp/controls-audit-baseline.json` + `tests/lint/test_controls_audit_baseline.py`. SDD-100 — band scheme.
