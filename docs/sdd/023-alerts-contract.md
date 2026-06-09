# SDD-023 — Operator-derived alerts contract (Round 89-90)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-06-09
> Derived from: SDD-016 (observability bindings), Rounds 89-90 code,
> operator verbatim "Reach our ultimate sovereignty" + "observable
> and operable, at all stages of lifecycle".
> Amended 2026-06-09: added § "Complementary Prometheus rule path" +
> § "Every-metric-has-a-home coverage gate" — the with-Prometheus
> alerting surface and its enforcement, sister to the in-tree engine.

## Problem

SDD-016 specified three observability layers (A: JSONL logs, B:
Prometheus textfile metrics, C: operator CLI + Grafana JSON dashboards),
all local-default. What SDD-016 left implicit:

- **Operators without Grafana** still need to know "is anything wrong
  right now?" The .prom files contain the answer; the question is how
  to surface it.
- **Alertmanager assumes a Prometheus server + rules.yml file + a
  separate notification chain** — none of which sovereign-os ships
  by default.
- The choice between (a) requiring operators to stand up
  Prometheus+Alertmanager and (b) shipping a built-in rules engine
  that derives alerts directly from the .prom files determines
  whether the "no third-party SaaS required" sovereignty posture
  actually holds for the alerting axis.

Rounds 89-90 implemented option (b). This SDD documents the contract
so future modifications (new rules, new metric labels, new alert
levels) are bound by a written spec instead of code archaeology.

## Decision: in-tree rules engine; .prom files as the only input; sovereign-osctl + recurrent hook as the surfaces

### Rule set (canonical, versioned by this SDD)

Six rules. Each rule emits exactly one alert per matched metric line.

| ID | Level | Predicate | Remediation hint shape |
|---|---|---|---|
| R1 | ALERT | metric name matches `*_total` AND label `result="fail"` AND value > 0 | "investigate the most recent <step> run; check journalctl and JSONL logs" |
| R2 | ALERT | metric name == `sovereign_os_friction_audit_failures` AND value > 0 | "run 'sovereign-osctl audit friction' to see the failing hardware checks" |
| R3 | ALERT | metric name == `sovereign_os_perimeter_status` AND value != 1 | "Tetragon not active; run 'sovereign-osctl perimeter status' and 'systemctl status tetragon'" |
| R4 | ALERT | metric name == `sovereign_os_zfs_pool_health` AND value < 1 | "zpool '<pool>' not ONLINE; run 'zpool status <pool>'" |
| R5 | WARN | metric name == `sovereign_os_security_updates_available` AND value > 0 | "<N> security update(s) pending; run 'unattended-upgrade -d' or 'sovereign-osctl maintenance security-check'" |
| R6 | WARN | metric name matches `*_last_run_timestamp` AND value > 0 AND value < now - SOVEREIGN_OS_ALERTS_STALE_DAYS×86400 | "last successful run was <iso8601>; recurrent timer may not be firing — check systemd timer status" |

### Levels

Exactly two:

- **ALERT** — operator action required; presence triggers `exit 1`
  from `sovereign-osctl alerts` (operator scripts can chain on this).
- **WARN** — visibility only; does not affect exit code.

Future additions MUST justify in a new SDD or amendment why a third
level (INFO? NOTICE? CRITICAL?) is necessary. The two-level model
keeps the operator's mental model small.

### Inputs

Only files matching the glob
`${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-*.prom`
(default `SOVEREIGN_OS_METRICS_DIR=/var/lib/node_exporter/textfile_collector`).

No journald query. No filesystem walk beyond that one directory. No
network. No reading any file outside the textfile collector dir.
This is a hard contract — auditors can verify by inspection.

### Output formats

Two:

1. **Human pretty-print** (default): `[LEVEL] <metric> {labels}` followed by
   `value:` + `fix:` lines. Counts header at top.
2. **JSON array** (`--json` flag): each entry has fields
   `level`, `metric`, `labels` (object), `value` (number),
   `remediation` (string). Stable schema — fields are additive only.

JSON mode emits `[]` for the empty-alert state. Never null, never an
error message — fleet aggregation tools depend on parseable output.

### Meta-observability (SDD-016 closure)

The hourly recurrent hook `scripts/hooks/recurrent/alerts-check.sh`
runs the rule engine and emits meta-counters back into Layer B:

- `sovereign_os_meta_alert_count{level="ALERT"}` — gauge
- `sovereign_os_meta_alert_count{level="WARN"}` — gauge
- `sovereign_os_meta_alerts_check_last_run_timestamp` — gauge

Zero-counters are ALWAYS emitted (no Prometheus blind-spot for
"no alerts" state — graphing this metric must work even on a healthy
fleet). The alert payload is also persisted to
`/var/lib/sovereign-os/alerts.json` so a freshly-logged-in operator
can `cat` current state without re-running the rule engine.

**Meta metrics MUST NOT trigger rules**: the rules above filter by
metric name; none reference `sovereign_os_meta_*`. This is intentional —
otherwise the system could enter a self-reinforcing alert loop.

### Surfaces

Operators reach the rule engine three ways. All three apply the same
rules to the same inputs:

| Surface | When to use |
|---|---|
| `sovereign-osctl alerts` | interactive: "what's wrong right now?" |
| `sovereign-osctl alerts --json` | scripted: fleet aggregation, CI gates |
| `sovereign-osctl maintenance alerts-check` | on-demand re-run of the hourly hook (also writes .prom + alerts.json) |
| `sovereign-alerts-check.timer` | hourly auto-execution; same hook |

### Sovereignty posture (operator verbatim)

- "Reach our ultimate sovereignty" — the alert engine is in-tree, no
  third-party network call, no opaque rules-file format.
- "observable and operable, at all stages of lifecycle" — the rule
  engine itself emits Layer B metrics about its own runs (R6 catches
  the case where the hook stops firing).
- "we always deliver IaC" — the rules are code, not config; reviewers
  can audit changes via `git log`.

## Tunables

| Env var | Default | Meaning |
|---|---|---|
| `SOVEREIGN_OS_METRICS_DIR` | `/var/lib/node_exporter/textfile_collector` | input glob root |
| `SOVEREIGN_OS_ALERTS_STALE_DAYS` | 7 | R6 staleness threshold |
| `SOVEREIGN_OS_ALERTS_STATE_FILE` | `/var/lib/sovereign-os/alerts.json` | offline alert payload |
| `SOVEREIGN_OS_OSCTL` | (auto-detect) | path to sovereign-osctl (alerts-check.sh resolver) |
| `SOVEREIGN_OS_DRY_RUN` | (unset) | when set on the hook, print intent without emitting .prom or alerts.json |

## Test gates

| Layer | Gate | Asserts |
|---|---|---|
| L3 | `tests/nspawn/test_sovereign_osctl_alerts.sh` | one assertion per rule + json/text/clean/absent/combined |
| L3 | `tests/nspawn/test_alerts_check_hook.sh` | DRY-RUN / tally accuracy / .prom emission / alerts.json persistence / maintenance dispatch / zero-state emission |
| L1 | `tests/lint/test_hook_layer_b_coverage.py` | alerts-check.sh participates in Layer B emission |
| L1 | `tests/lint/test_metric_inventory_lockstep.py` | meta_alert_count + meta_alerts_check_last_run_timestamp documented in README |
| L1 | `tests/lint/test_systemd_unit_hardening.py` | sovereign-alerts-check.service is ProtectSystem/NoNewPrivileges/PrivateTmp hardened |

## Complementary Prometheus rule path (Amendment, 2026-06-09)

The in-tree engine above (`sovereign-osctl alerts`, rules R1-R6) is the
**no-Prometheus** surface — it derives alerts directly from the `.prom`
files so the sovereignty posture holds without standing up
Prometheus+Alertmanager. Operators who **do** run Prometheus get a
**richer, native** surface: the Prometheus alert-rule file
`config/prometheus/alerts/sovereign-os-health.rules.yml` (sister to the
already-shipped four-watchdog / M060 / MS022 / sovereign-telemetry rule
files). Both surfaces read the same Layer-B metrics; they are
complementary, not redundant — the in-tree engine is the floor (always
available), the Prometheus rules are the ceiling (when Prometheus is
deployed).

### Why a second surface

R2-R5 already cover friction-audit / perimeter / ZFS-pool / security in
the in-tree engine, but ONLY those four axes, and only as the two flat
ALERT/WARN levels with no `for:` debounce, no time-since-timestamp
staleness, and no native Alertmanager routing/inhibition. The OS's own
health metrics were otherwise **scraped but never alerted in Prometheus**:
a failing audit / downed Tetragon fence / degraded pool / stalled backup /
unpatched vuln / overheating sensor / fired UPS-shutdown / OOM kill
produced no Prometheus page. `sovereign-os-health.rules.yml` closes that —
13 alerts across 8 axes:

| Axis | Alerts (severity) | Key metric |
|---|---|---|
| hardware integrity | SovereignOsFrictionAuditFailing (crit) | `sovereign_os_friction_audit_failures` |
| security perimeter | SovereignOsPerimeterDown (crit), SovereignOsPerimeterVerifierSilent (warn) | `sovereign_os_perimeter_status`, `…verify_last_run_timestamp` |
| data integrity | SovereignOsZfsPoolDegraded (crit), SovereignOsZfsScrubOverdue (warn) | `sovereign_os_zfs_pool_health`, `…scrub_last_run_timestamp` |
| backups | SovereignOsBackupSnapshotStale (warn) | `sovereign_os_snapshot_last_created_timestamp` |
| security patching | SovereignOsSecurityUpdatesPending (warn), SovereignOsSecurityUpdateCheckStale (warn) | `sovereign_os_security_updates_available`, `…check_last_run_timestamp` |
| thermal | SovereignOsThermalCritical (crit), SovereignOsThermalWatchSilent (warn) | `sovereign_os_thermal_severity`, `…last_run_unix` |
| power | SovereignOsPowerShutdownGuardFired (crit), SovereignOsPowerUpsCritical (crit) | `sovereign_os_power_shutdown_guard_{fired,verdict}` |
| memory | SovereignOsMemoryOomKills (crit) | `sovereign_os_memory_oom_kill_count` |

Severity vocabulary stays the bounded two-tier (`warning`/`critical`,
mapping to the in-tree WARN/ALERT) per the §"Levels" contract. Every alert
carries a `runbook_url` into `docs/operator/m060-deployment-guide.md`
(per-alert Diagnosis/Fix sections); the generic
`tests/lint/test_alert_runbook_anchor_coverage.py` gate proves each anchor
resolves. Deployment snippet lives in the same m060 guide.

### Every-metric-has-a-home coverage gate

`tests/lint/test_metric_observability_coverage.py` is the P4 enforcement
that prevents this gap from recurring: every emitted `sovereign_os_*`
metric (counted comprehensively — `emit_metric` call sites AND `# HELP`
lines, in lockstep with `test_metric_inventory_lockstep.py`) must have an
observability **home** — a Prometheus alert, a Grafana panel, a recording
rule, or a justified info-tier exemption (build/lifecycle/sampling/notify
telemetry). A new metric that pages/charts nowhere fails the gate, forcing
a deliberate alert-vs-dashboard-vs-info decision. Sister direction to
`test_metric_inventory_lockstep.py` (code→inventory) and
`test_dashboard_metrics_lockstep.py` (dashboard→emitter).

### Test gates (Prometheus path)

| Layer | Gate | Asserts |
|---|---|---|
| L1 | `tests/lint/test_sovereign_os_health_alerts_contract.py` | the 13 alerts present; each expr references an emitted metric; severity/for/runbook-anchor shape; criticals are critical; staleness alerts are time()-since-timestamp |
| L1 | `tests/lint/test_alert_runbook_anchor_coverage.py` | every alert's runbook anchor resolves in the m060 guide |
| L1 | `tests/lint/test_metric_observability_coverage.py` | every emitted metric has a home or justified exemption (+ no stale/contradictory exemption) |

## Open sub-questions (Q23-X tracked)

- **Q23-A** — Should `--json` output sort alerts by severity (ALERT
  before WARN, then alpha by metric)? Currently: yes (Python `sort()`
  with a (level_rank, metric) key). Recommend: lock this as part of
  the JSON schema, not implementation detail.
- **Q23-B** — Should `alerts-check.sh` also emit a HISTOGRAM of how
  many of each rule fired (vs just a sum across rules)?
  **RESOLVED (Round 121)** — shipped. Hook emits
  `sovereign_os_meta_alert_by_metric{metric,level}` gauge per
  (metric, level) combination on every run; operators graph WHICH
  underlying metric is the noisiest over time (single counter doesn't
  tell you whether 5 alerts came from 1 metric or 5 different metrics).
- **Q23-C** — Should the rule engine support operator-supplied custom
  rules (e.g. `/etc/sovereign-os/alerts.d/*.yaml`)? Recommend: NO
  in foundation phase — operators with custom rules already run
  Prometheus + Alertmanager + their own rules.yml, and shipping a
  parallel rules engine multiplies maintenance burden. Reconsider at
  Stage 4+ if operator demand surfaces.
- **Q23-D** — Should `sovereign-osctl alerts` also surface the
  ROUND-TRIP cost (rule engine wall time) as a metric? Recommend:
  NO — overhead is ~50ms; not worth a metric. Add only if a profiler
  shows the rule engine is the bottleneck on any deployment.

## Cross-references

- `scripts/sovereign-osctl` § `cmd_alerts` — 6-rule engine
- `scripts/hooks/recurrent/alerts-check.sh` — hourly run + meta metrics
- `systemd/system/sovereign-alerts-check.{service,timer}` — cadence
- `docs/observability/dashboards/README.md` § Recurrent maintenance —
  documented `sovereign_os_meta_alert_count` + `sovereign_os_meta_alerts_check_last_run_timestamp`
- `docs/src/install-runbook.md` § 5b — operator walkthrough
- SDD-016 — Layer A/B/C foundation
- `config/prometheus/alerts/sovereign-os-health.rules.yml` — the 13-alert
  Prometheus operational-health rule file (complementary surface)
- `docs/operator/m060-deployment-guide.md` § sovereign-os operational-health
  alerts — per-alert Diagnosis/Fix runbooks + deploy snippet
- `tests/lint/test_sovereign_os_health_alerts_contract.py` /
  `tests/lint/test_metric_observability_coverage.py` — the contract +
  every-metric-has-a-home enforcement
- Operator verbatim (sacrosanct): "Reach our ultimate sovereignty",
  "observable and operable, at all stages of lifecycle"
