# SDD-143 — Phase 4: raise 5 ux-audit modules to 6/6 (genuine next-step hints)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-11
> Closes findings: with the empty-state wording theme closed (SDD-140/141/142), the substantive next stream is the safe half of ux-audit "option B": the 5 backend operator modules scoring **5/6** each fail only the `next-step` dimension (`ux-design-audit.py::audit_next_step` — the module source must contain a `next:` / `next_action` / `Run:` hint). This gives each a genuinely-useful next-step hint in its human CLI output — real operator-ergonomics, not score-gaming — raising all 5 to **6/6**. Recover band (SDD-143 / E11.M143 per SDD-100).
> Derived from / extends: SDD-139 (ux-audit baseline + regression guard — regenerated here). §1g.

## Mission

Give the 5 shortfall modules a real "what to do next" hint pointing at a genuine drill-down verb, raising each to 6/6, and regenerate the SDD-139 baseline so the guard tracks the new state.

## Grounded design (5 backend scripts + regenerate 1 baseline JSON)

One `print("  next: run \`sovereign-osctl <module> <verb>\` …")` per module, added as the **last statement of the primary verb's human `else` branch** (indent-8) so `--json` stays byte-identical (the hint never runs on the JSON path):

| Module | verb | hint → drill-down |
|---|---|---|
| `network-topology.py` (`network-edge`) | `detect` | `next: run \`… network-edge opnsense status\`` — probe the OPNsense API tier (unlocks the full NAT-chain view) |
| `global-history.py` | `recent` | `next: run \`… global-history summary\`` — the per-source liveness rollup |
| `surface-map.py` | `gaps` | `next: run \`… surface-map coverage\`` — the full module-by-surface matrix |
| `doc-coverage.py` | `gaps` | `next: run \`… doc-coverage scan --module <m>\`` — which doc surfaces a module is missing |
| `anti-minimization-audit.py` | `report` | `next: run \`… anti-minimization-audit scan --pattern <id>\`` — file:line matches for any non-zero pattern |

`bashrc` (4/6) is **left out** — it also fails `recoverable`, whose fix (`--apply`/`--confirm` gating on `bashrc-install.sh`'s mutating `install` verb) is an install-safety behaviour change deserving its own operator-greenlit SDD.

Then `scripts/operator/ux-design-audit-baseline.json` is regenerated (`… score --json > …`); the 5 flip 5/6 → 6/6 and the SDD-139 guard's `live==baseline` + no-regression assertions track it.

## R10212 / SB-077 preserved

Additive human-output only. `--json` output is byte-identical (hint lives strictly in the `else` branch). No fabricated data; the hints point at real verbs. R10212 untouched.

## Verification

- `python3 scripts/operator/ux-design-audit.py score --json` → 5 modules now **6/6** (auth-tier, edge-firewall, master-dashboard, network-edge, global-history, surface-map, doc-coverage, anti-minimization-audit = 6/6; bashrc 4/6).
- JSON purity: for each of the 5, the `next: run` hint appears in human output but **0** times in `--json`.
- `tests/lint/test_ux_design_audit_baseline.py` (regenerated baseline, no regression) + `test_ux_design_audit_contract.py` + each module's `test_*_contract.py` green (recon-confirmed: no test pins exact human stdout — all validate source substrings + `--json` structure).
- Full `make test` green.

## On completion

8 of 9 ux-audit modules at 6/6. Remaining Phase 4 (operator-selectable): the **bashrc dry-run gate** (`--apply`/`--confirm` → 4/6→5/6, behaviour change, needs greenlight); an **SDD-040 token reconciliation** (`--good/--bad` vs `--ok/--danger`) to unblock a real spacing/typography scale.

## Cross-references

- SDD-139 (ux-audit baseline); producer `scripts/operator/ux-design-audit.py` (`audit_next_step`); the 5 modules `scripts/operator/{network-topology,global-history,surface-map,doc-coverage,anti-minimization-audit}.py`. SDD-100 — band scheme.
