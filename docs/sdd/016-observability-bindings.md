# SDD-016 — Observability bindings (Q-013 resolution)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: Q-013 (observability bindings)
> Derived from: `profiles/*.yaml` § observability, IaC bar verbatim
> ("observable and operable, at all stages of lifecycle"), existing
> JSONL logging via `scripts/build/lib/logging.sh`, log-rotate hook
> (SDD section in Round-9 commit), `sovereign-osctl status/doctor`.

## Problem

Q-013 ("Observability bindings") has been open since PR 1. Profiles
declare `observability.telemetry_sink: prometheus-local` and
`log_retention_days` and `audit_hooks`, but no SDD ties these to a
concrete observability stack or specifies what the contract is. The
operator's IaC bar requires "observable and operable, at all stages
of lifecycle" — that needs to be load-bearing, not aspirational.

## Decision: three-layer observability stack, all local-default

| Layer | What | Where | When |
|---|---|---|---|
| **Layer A — structured logs** | JSONL events from every script via `scripts/build/lib/logging.sh` | `~/.sovereign-os/log/build-<ts>.jsonl` (build host) + `/var/log/sovereign-os/*.jsonl` (installed system) | always-on; opt-out only via SOVEREIGN_OS_LOG_LEVEL=error |
| **Layer B — metrics** | Prometheus textfile collector | `/var/lib/node_exporter/textfile_collector/sovereign-os.prom` | when `telemetry_sink: prometheus-local` (default) |
| **Layer C — operator dashboard** | `sovereign-osctl status` (CLI) + Grafana JSON dashboards (template-shipped, operator-installed) | local CLI + `docs/observability/dashboards/*.json` (future, deferred) | local CLI: always-on; Grafana: opt-in |

**Sovereignty principles enforced:**
- **Local-default** — no remote sink without operator action
- **No phone-home** — `prometheus-local` writes to disk; operator
  decides whether/how to scrape (local Prometheus, `node_exporter`,
  Datadog agent, whatever; sovereign-os doesn't dictate)
- **Operator-pullable retention** — `log_retention_days` per-profile
  (default 14d for sain-01/old-workstation, 7d for minimal); auto-
  rotation via the `sovereign-log-rotate.timer` (SDD logged in
  previous commit)

## Layer A — structured logs (already shipped)

`scripts/build/lib/logging.sh`:
- emits JSONL events with: timestamp (ISO-8601), level (info/warn/
  error/debug), step (orchestrator step id or hook id), message
- one file per build/run; rotated by `log-rotate.sh` recurrent hook
- log_step_header emits a separator + level=info event
- `SOVEREIGN_OS_LOG_FILE` env var overrides path

Log retention contract:
- `profile.observability.log_retention_days` controls primary-dir
  retention (default 14 if unset)
- `SOVEREIGN_OS_LOG_RETENTION_DAYS` env overrides profile
- after retention window: gzip → archive/
- after `SOVEREIGN_OS_LOG_ARCHIVE_DAYS` (default 90): delete

Gated by `tests/nspawn/test_log_rotate.sh` (10 assertions).

## Layer B — metrics (contract; implementation deferred to Stage 2+)

**Format**: prometheus textfile collector
(https://github.com/prometheus/node_exporter/tree/master/text_collector_examples).
Files named `sovereign-os-*.prom` under
`/var/lib/node_exporter/textfile_collector/`.

**Metric naming convention**:
```
sovereign_os_<subsystem>_<metric_name>{<labels>} <value>
```

Examples (sketch — actual emission lands at Stage 2+ when timers
mature):

```
# HELP sovereign_os_build_step_duration_seconds Wall-clock duration of build steps
# TYPE sovereign_os_build_step_duration_seconds summary
sovereign_os_build_step_duration_seconds{step="01-bootstrap-forge",profile="sain-01"} 47.2
sovereign_os_build_step_duration_seconds{step="04-kernel-compile",profile="sain-01"} 1830.5

# HELP sovereign_os_log_rotation_files_rotated Files rotated by last log-rotate run
# TYPE sovereign_os_log_rotation_files_rotated gauge
sovereign_os_log_rotation_files_rotated 3
sovereign_os_log_rotation_files_purged 1
sovereign_os_log_rotation_last_run_timestamp 1734316200

# HELP sovereign_os_inference_route_total Total requests per tier
# TYPE sovereign_os_inference_route_total counter
sovereign_os_inference_route_total{tier="pulse"} 42
sovereign_os_inference_route_total{tier="logic_engine"} 137
sovereign_os_inference_route_total{tier="oracle_core"} 18

# HELP sovereign_os_zfs_pool_health Pool health (1=ONLINE, 0=DEGRADED+)
# TYPE sovereign_os_zfs_pool_health gauge
sovereign_os_zfs_pool_health{pool="tank"} 1
```

**Emission cadence**:
- One-shot scripts (orchestrator, hooks): emit on completion. Timer-
  driven scripts (zfs-scrub, log-rotate, model-catalog-sync): emit
  per run.
- The collector reads the .prom files atomically (write to tempfile,
  rename) — no file-locking needed.

**No black-box dispatchers**:
- sovereign-os does NOT ship a Prometheus exporter daemon.
- sovereign-os does NOT ship Telegraf, Datadog agent, etc.
- Operator picks the scraper. The textfile collector pattern composes
  with any of them.

**What lands in this SDD**: the contract. Not the metrics emission
yet — that's a Stage 2+ batch. Future commits add an `emit_metric`
helper in `scripts/build/lib/observability.sh` and wire it into the
existing hooks.

## Layer C — operator dashboards

**Now**: `sovereign-osctl status` + `doctor` cover the immediate-state
inspection. Gated by `test_sovereign_osctl.sh` (23 assertions).

**Future (Stage 2+ deferred)**: ship a few starter Grafana dashboards
in `docs/observability/dashboards/*.json`:
- `sovereign-os-overview.json` — across-the-stack pulse
- `sovereign-os-inference.json` — per-tier route counts + latency
- `sovereign-os-zfs.json` — pool health + scrub progress
- `sovereign-os-tetragon.json` — perimeter event rate + policy verify

Operator imports them post-install. Dashboards are templates, not
auto-installed (operator may not run Grafana).

## Goals

1. **Profile field has a binding** — `telemetry_sink: prometheus-local`
   means "write prometheus textfile collector files locally"; nothing
   else. Schema enum already enforces.
2. **Local-default sovereignty** — no remote sink without explicit
   operator config.
3. **Zero black-box dispatchers** — the operator can read every line
   of the observability stack.
4. **Composable** — textfile collector pattern works with any scraper.
5. **Honest scope** — Layer A shipped, gated. Layer B contract locked;
   emission lands Stage 2+. Layer C CLI shipped; Grafana dashboards
   Stage 2+.

## Non-goals (this SDD)

- Does NOT mandate Prometheus over alternatives — operator can run
  no scraper at all and the textfile collector files just rotate.
- Does NOT prescribe alert rules — operator-driven (different
  contexts demand different alerting).
- Does NOT add a sovereign-os-managed time-series database.
- Does NOT define remote-sink integration (Loki, ClickHouse, etc.) —
  operator wires that themselves if they want it.

## Cross-references

- `profiles/*.yaml` § observability.telemetry_sink + log_retention_days
- `scripts/build/lib/logging.sh` (Layer A)
- `scripts/hooks/recurrent/log-rotate.sh` (Layer A rotation)
- `scripts/sovereign-osctl status / doctor` (Layer C CLI)
- `tests/nspawn/test_log_rotate.sh` (Layer A gate)
- `tests/nspawn/test_sovereign_osctl.sh` (Layer C gate)
- Operator IaC bar (verbatim, sacrosanct): "observable and operable,
  at all stages of lifecycle"

## Open sub-questions (Q-016-X tracked)

- **Q16-A** — Should sovereign-os ship `node_exporter` itself, or just
  declare the textfile collector path and let operators install
  `node_exporter` via their package manager? Recommend: **operator
  installs** — keeps surface smaller, lets operator pick the version /
  configure ports.
- **Q16-B** — Should Layer A logs be journald-aware (so the systemd
  units use systemd journal) instead of JSONL files? Recommend: **both**
  — systemd units already log to journal (per existing service unit
  files); the JSONL files remain for one-shot orchestrator runs and
  cross-host shipping.
- **Q16-C** — Should the metrics include a `sovereign_os_arc_size_bytes`
  ZFS ARC gauge? Recommend: **yes**, when zfs-arc-clamp.sh is
  expanded to emit it (Stage 2+).
- **Q16-D** — Should Grafana dashboards ship as code (provisioned
  via grafana-provisioning YAML) or as JSON templates? Recommend:
  **JSON templates** — operator-imports — keeps Grafana opt-in.
