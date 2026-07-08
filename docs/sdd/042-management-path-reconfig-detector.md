# SDD-042 — Management-path reconfiguration detector (the dropout gotcha's missing witness)

**Status**: ACTIVE
**Owner**: @cyberpunk042 (Architect)
**Created**: 2026-06-10
**Source milestone**: `backlog/milestones/M084-opnsense-sdwan-boundary-contract-tetragon-dropout-resilience.md` (R14124–R14126; authored SDD-first per R14216)
**Implementation surface**: `scripts/hooks/recurrent/` (new watcher) + `config/prometheus/alerts/sovereign-os-auditor.rules.yml` (existing churn alert gains its diagnostic counterpart) + `docs/observability/dashboards/README.md` (inventory) + `docs/operator/m060-deployment-guide.md` (runbook diagnosis upgrade)

> Closes findings: M084 R14124–R14126 (the catalogued-pending reconfig-detector; cause-side witness for the dump-762 chain).
> Derived from: transposition dump lines 761–765 (the gotcha/prevention, verbatim), M084 catalog rows R14124–R14126, the shipped dropout resilience (`47632d0` BindsTo + EOF sentinel; `73bf7c4` EOF metric + `SovereignOsAuditorStreamEofChurn`).

## Mission

The dump's gotcha names a CAUSE → EFFECT chain:

> "If your OPNsense/SD-WAN firewall dynamically re-shuffles interface
> addresses or drops a lease connection along the management path, the
> system loopback hooks used by the Tetragon socket stream can
> experience buffer disconnects." (dump 762)

The EFFECT side is now fully instrumented: the guardian exits nonzero on
stream EOF, `sovereign_os_auditor_stream_eof_total` counts dropouts, and
`SovereignOsAuditorStreamEofChurn` pages on churn. But the CAUSE side —
the management-path reconfiguration events themselves — has **no
witness**. When the churn alert fires, the runbook tells the operator to
go read `journalctl -u systemd-networkd` by hand; nothing in the metric
plane says *whether* the management NIC actually bounced, *when*, or
*how often*. R14126 ("guardian restarts correlatable with reconfig
windows") is therefore only manually satisfiable today.

This SDD specs the missing witness: a recurrent watcher that turns
management-NIC reconfiguration events into Layer-B metrics, so
cause (reconfig) and effect (stream EOF) sit side-by-side on the same
time axis in Prometheus.

## Required coverage

| Requirement | Source |
|---|---|
| R14124 — interface re-shuffle events surfaced to the operator | M084 / dump 762 |
| R14125 — lease-drop events on the management path surfaced | M084 / dump 762 |
| R14126 — guardian restarts correlatable with reconfig windows | M084 |
| R14130 — new series inventoried per the metric-inventory lockstep gate | M084 |
| R14133 — any new alert carries a resolving runbook anchor | M084 |

## Design

### Mechanism: journald-cursor poll (recurrent hook), not a daemon

A new recurrent hook `scripts/hooks/recurrent/net-reconfig-watch.sh`
(systemd timer cadence: 1m, same family as
`sovereign-telemetry-textfile.sh`), each tick:

1. Resolves the management NIC from the active profile (the §8.1
   `hardware.network` entry with `default_gateway: true` — same source
   of truth `render-asymmetric.sh` reads; no hardcoded `enp6s0`).
2. Reads `journalctl -u systemd-networkd --cursor-file
   <state>/networkd.cursor -o json` — only NEW lines since the last
   tick (cursor persisted under `/var/lib/sovereign-os/net-reconfig/`).
3. Classifies lines mentioning the management NIC into three kinds,
   mapped to the dump's vocabulary:
   - `carrier-loss` — "Lost carrier" (the interface re-shuffle's
     visible edge)
   - `lease-drop` — "DHCP lease lost" / lease expiry without renewal
   - `addr-change` — address added/removed outside boot
4. Appends Layer-B textfile metrics (same `_emit_metric` shape as the
   sibling hooks, file `sovereign-os-net-reconfig.prom`):
   - `sovereign_os_net_reconfig_events_total{kind}` (counter)
   - `sovereign_os_net_reconfig_last_event_timestamp` (gauge)

A polling hook (not an rtnetlink daemon) is deliberate: the signal's
consumer is a 30m-window churn alert, 1-minute granularity is ample,
and the recurrent-hook family already carries the operational pattern
(timer + textfile + R171-hardened unit) — no new daemon class needed.

### Alerting: diagnosis-tier, not a second pager

No new page by default. The churn pager stays
`SovereignOsAuditorStreamEofChurn` (the effect is what hurts). The new
series make its runbook diagnosis one PromQL query instead of a manual
journal dig, and the existing alert's runbook section gains the
correlation query:

```promql
increase(sovereign_os_net_reconfig_events_total[30m])
  and increase(sovereign_os_auditor_stream_eof_total[30m]) > 0
```

(Open question Q-2 below: whether a cause-side warning alert is wanted
at all.)

### Observability homes (gate compliance, decided up front)

- `sovereign_os_net_reconfig_events_total` — referenced by the upgraded
  runbook + (pending Q-2) alert expr; inventoried in the dashboards
  README. Satisfies the metric-observability-coverage gate via the
  alert/runbook home, NOT via exemption.
- `sovereign_os_net_reconfig_last_event_timestamp` — freshness gauge,
  dashboard-tier.

## Goals

1. Cause-side witness for the dump-762 chain with the dump's own
   vocabulary (re-shuffle / lease drop), per-NIC-role aware.
2. R14126 correlation answerable from Prometheus alone.
3. Zero new daemons; zero new privileges; the watcher reads journald +
   profile YAML and writes one `.prom` file.

## Non-goals

- Mutating firewall or networkd state (R10212 read-only doctrine; the
  fix for flapping lives at the OPNsense side).
- Watching the data-plane NIC (VLAN 200 carries no Tetragon stream;
  scope creep until an R-row demands it).
- Replacing the EOF sentinel (effect-side instrumentation is shipped).

## Open questions

| Q | Question | Default until answered |
|---|---|---|
| Q-1 | Cadence: is 1m the right tick, or should the timer match the telemetry hook's existing cadence exactly? | 1m (sibling parity) |
| Q-2 | Should a cause-side warning alert exist (e.g. ≥5 mgmt reconfig events in 30m even with zero EOFs), or is cause strictly diagnosis-tier? | diagnosis-tier only (no second pager for one incident) |
| Q-3 | Classify `systemd-networkd` restart itself as a reconfig event (it bounces all NICs) or filter it as noise? | count it, label `kind="networkd-restart"` |

## Way forward

1. (this SDD) review + Q-1..Q-3 answers → `docs/decisions.md` D-NNN rows.
2. Scaffold: hook script skeleton + timer/service units (R171 posture) +
   test stubs (`tests/lint/test_net_reconfig_watch_contract.py`
   asserting script/unit/metric-name lockstep, hardware-free).
3. Implement: classifier + cursor persistence + textfile emit;
   inventory rows; runbook correlation-query upgrade.
4. Test: nspawn-style execution test feeding canned journald JSON;
   metric-inventory + observability-coverage + alert gates green.

## Cross-references

- M084 (R14124–R14126, R14216) — the catalog rows this SDD decomposes
- Transposition dump 761–765 — the gotcha/prevention verbatim
- `47632d0` / `73bf7c4` — shipped effect-side resilience + observability
- SDD-016 — Layer A/B observability architecture (textfile collector)
- `scripts/hooks/recurrent/sovereign-telemetry-textfile.sh` — the
  sibling pattern (timer + textfile emit)
- `scripts/network/render-asymmetric.sh` — the §8.1 profile fields the
  watcher reuses to resolve the management NIC
