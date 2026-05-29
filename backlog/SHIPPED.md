# sovereign-os · backlog/SHIPPED.md

> **Production-shipped state tracker against `backlog/INDEX.md`.** Auto-maintained as commits land. Surfaces, per milestone, which catalogued R-rows have reached production code (with test coverage + cockpit-visible surface) versus which remain catalogued-only.
>
> The catalogue is `backlog/INDEX.md` (80 milestones / 13,740 R-rows). This file is the orthogonal "delivery state" view per the operator's standing constraint:
>
> > *"You cannot mark something done if it hasn't reached Prod."*
>
> *Shipped* here means: production code merged on the development branch, with passing lint+schema sweep, with operator-visible surface (cockpit dashboard / api endpoint / Prometheus rule / Grafana panel), AND (for cross-repo R-rows) with the selfdef producer side wired. *Catalogued-only* means: R-row exists in `backlog/milestones/M*.md` but no production surface has landed.

## Roll-up

| State | R-rows | % of 13,740 |
|---|---:|---:|
| Catalogued (total) | 13,740 | 100% |
| Shipped (production surface + tests + cockpit-visible) | partial — tracked per-milestone below | — |
| Catalogued-only | balance | — |

Per-milestone shipped deltas are enumerated below in commit-order so the trajectory across the multi-year project is auditable.

## M060 — Cockpit + 20+ dashboards + UX surface

**Catalogued:** 170 R-rows (R10001..R10170 family). See `backlog/milestones/M060-cockpit-and-dashboards-ux-surface.md`.

**Shipped this milestone (cross-repo M060 mirror chain, consumer side):**

| R-row family | Surface | Commits (sovereign-os) | Tests | Selfdef pair |
|---|---|---|---|---|
| D-CLI cross-link (operator runbook discoverability) | "Companion guide — selfdef-side producer wiring" section at top of `docs/operator/m060-deployment-guide.md` with direct GitHub URL to selfdef's `m060-cockpit-mirror-producers.md` + contract test paths on both sides | `52d925f` | n/a (markdown) | selfdef `fdbef1b` |
| D-CLI Prometheus alerts | `M060CliMirrorChainDegraded` (worst_severity==1, for 5m, warning), `M060CliMirrorChainBroken` (worst_severity==2, for 2m, critical), `M060CliMirrorObserverSilent` (last_run_unix > 300, for 5m, critical) added to `config/prometheus/alerts/m060-chain-health.rules.yml` | `bf98e2a` | 7 new contract tests in `test_m060_chain_health_alerts_contract.py` (sub-chain alerts present, exprs reference doctor textfile metrics, severity classification correct, chain_link label set, runbook_url points to selfdef producer guide, for-clause present, observer threshold pinned at 300s) | selfdef `e9ab056` |
| D-CLI runbook sections | 3 sections (#### M060CliMirror{ChainDegraded,ChainBroken,ObserverSilent}) added to `docs/operator/m060-deployment-guide.md` with ready-to-paste diagnosis commands + per-cause SSH-into-selfdef fixes; each cross-links to the selfdef-side producer guide | `bf98e2a` | 3 runbook coverage tests (each alert has section heading, contains diagnosis + fix, links systemctl or journalctl) | n/a |
| D-CLI Grafana panel | `docs/observability/dashboards/sovereign-os-m060-cli-mirror.json` — 9 panels covering worst-severity stat, per-check severity time-series, live triage table surfacing the `fix` column from `selfdef_cli_mirror_doctor_check_info`, observer-age tracking with 300s red threshold matching the alert | `2a44536` | 10 dashboard contract tests (title/uid/tags lock, all 4 producer metrics on ≥1 panel, observer-age red threshold == 300s, worst-severity value mappings + thresholds match alert classifier, check-info is table with fix column, link to producer guide, companion chain-wide signal, 30s refresh, panel count exactly 9) | n/a |

## Cross-cutting infrastructure (catalogue health visibility)

| Surface | Status |
|---|---|
| `backlog/INDEX.md` (80 milestones, 13,740 R-rows enumerated) | shipped prior to this session; surfaces the catalogue at a glance |
| `backlog/SHIPPED.md` (this file) | shipped — orthogonal production-delivery state tracker |

## Pre-session production state (audit of shipped surfaces)

The codebase carries substantial production state from prior development. This section audits the existing shipped surface — populated from the actual repo inventory (475 crates, 20 cockpit dashboards, 45 operator api scripts, 10 mirror reader scripts, 20 Grafana dashboards, 1 Prometheus alert-rules file), not invented. Each row references real artifacts a `git ls-files | grep …` confirms.

### M060 — Cockpit + 20+ dashboards + UX surface (pre-existing)

| Surface | Shipped artifact |
|---|---|
| Master dashboard (D-00) | `webapp/master-dashboard/index.html` (872 lines) |
| 20 per-domain cockpit dashboards (D-01..D-20) | `webapp/d-01-active-sessions`, `d-02-profile-choices`, `d-03-model-health`, `d-04-costs`, `d-05-traces`, `d-06-pending-approvals`, `d-07-memory-changes`, `d-08-rollback-points`, `d-09-hardware-pressure`, `d-10-eval-history`, `d-11-adapter-status`, `d-12-networking`, `d-13-filesystem-grants`, `d-14-capability-tokens`, `d-15-sandboxes`, `d-16-audit`, `d-17-quarantine`, `d-18-trust-scores`, `d-19-super-model-manifest`, `d-20-peace-machine-health` |
| Operator-§1g instrument webapps | `webapp/auditor`, `webapp/anti-minimization-audit`, `webapp/auth-tier`, `webapp/compliance`, `webapp/doc-coverage`, `webapp/edge-firewall`, `webapp/global-history`, `webapp/network-edge`, `webapp/_shared` |
| API daemon scripts (operator-side) | `scripts/operator/` — 45 `*-api.py` daemons including `m060-health-api.py`, `audit-mirror-api.py`, `approvals-api.py`, `costs-api.py`, etc. |
| Mirror reader scripts | `scripts/mirror/` — 10 `selfdef-*-mirror.py` READ-ONLY consumers (audit, capability, grants, profile, quarantine, rules, sandbox, trust-score, tui, cli) |
| Prometheus alerts | `config/prometheus/alerts/m060-chain-health.rules.yml` (5 chain-wide alerts pre-session; 3 cli-mirror sub-chain alerts added this session) |
| Grafana dashboards | 20 dashboards under `docs/observability/dashboards/*.json` — `sovereign-os-router`, `sovereign-os-inference`, `sovereign-os-auditor`, `sovereign-os-doc-coverage`, `sovereign-os-trinity`, `sovereign-os-surface-map`, `sovereign-os-network-edge`, `sovereign-os-predicate-coverage`, `sovereign-os-auth-tier`, `sovereign-os-ux-design-audit`, + 10 more |

### Cross-repo binding crates (consumed by sovereign-os from selfdef)

| Selfdef surface | Sovereign-os consumer |
|---|---|
| Typed-mirror crates (14, see selfdef SHIPPED MS007) | sovereign-os reads via `scripts/mirror/selfdef-*-mirror.py` + renders in `webapp/d-*/` |
| Daemon `/v1/m060/health` endpoint | sovereign-os consumes via `scripts/operator/m060-health-api.py` |
| `selfdefctl m060-doctor` (selfdef SHIPPED MS043 cross-rollup) | sovereign-os textfile metrics surface in the existing M060 chain-health alert rules |

## Other catalogued milestones — production-shipped state TBD

M002-M059, M061-M082 — most have substantial production state in the 475-crate workspace + 20-dashboard webapp tree. The per-milestone audit hasn't been mapped to this file yet for those. Future audits append per-milestone rows above.

The above per-milestone shipped audit is a SAMPLED snapshot, not a complete production-state survey. The trajectory: each commit or audit cycle appends rows here so the SHIPPED column converges toward the catalogue total as the multi-year project progresses.

## How this file is maintained

1. **Every production commit** that lands a catalogued R-row appends a row to the relevant milestone section above with: R-row family, surface description, commit hash(es), tests added, selfdef pair (if cross-repo).
2. **No invention** — every row references real commits + tests + sovereign-os user-visible surface (alert/runbook/dashboard/api). Audits cross-check against `git log` + `tests/lint/` + `docs/operator/` + `config/prometheus/alerts/`.
3. **Never marks done** what isn't in production — the operator's "You cannot mark something done if it hasn't reached Prod" constraint is sacrosanct. Half-shipped (e.g. alert without runbook section, dashboard without contract test) gets a parenthetical "partial — pending X" note, not a "shipped" row.

This file pairs with selfdef's parallel `backlog/SHIPPED.md` for producer-side surfaces. Both repos' INDEX + SHIPPED files together give the operator the catalogue-vs-shipped delta at any commit.
