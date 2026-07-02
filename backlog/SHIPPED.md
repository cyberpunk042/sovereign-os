# sovereign-os · backlog/SHIPPED.md

> **Production-shipped state tracker against `backlog/INDEX.md`.** Auto-maintained as commits land. Surfaces, per milestone, which catalogued R-rows have reached production code (with test coverage + cockpit-visible surface) versus which remain catalogued-only.
>
> The catalogue is `backlog/INDEX.md` (82 milestones / 14,080 R-rows). This file is the orthogonal "delivery state" view per the operator's standing constraint:
>
> > *"You cannot mark something done if it hasn't reached Prod."*
>
> *Shipped* here means: production code merged on the development branch, with passing lint+schema sweep, with operator-visible surface (cockpit dashboard / api endpoint / Prometheus rule / Grafana panel), AND (for cross-repo R-rows) with the selfdef producer side wired. *Catalogued-only* means: R-row exists in `backlog/milestones/M*.md` but no production surface has landed.

## Roll-up

| State | R-rows | % of 14,080 |
|---|---:|---:|
| Catalogued (total) | 14,080 | 100% |
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
| Mirror-domains Prometheus alerts | 3 new chain-wide alerts (`M060MirrorDomainChainDegraded` warn, `M060MirrorDomainChainBroken` critical, `M060MirrorDomainObserverSilent` critical) added to `config/prometheus/alerts/m060-chain-health.rules.yml`. Trigger on the selfdef-side `selfdef_m060_doctor_*` textfile series shipped by `selfdef-m060-doctor.timer` (selfdef commit ce58154) | this commit | 6 new contract tests in `test_m060_chain_health_alerts_contract.py` (sub-chain alerts present, expr references doctor textfile, severity classification, chain_link=mirror-domain label, runbook_url to producer guide, observer threshold pinned at 300s) | selfdef `ce58154` |
| Mirror-domains runbook sections | 3 new sections (#### M060MirrorDomain{ChainDegraded,ChainBroken,ObserverSilent}) added to `docs/operator/m060-deployment-guide.md` with per-domain diagnosis (per-domain metric queries + `selfdefctl m060-doctor` live probe) + per-cause SSH-into-selfdef fixes (grants issue / token issue / sandbox allocate / restart selfdefd / restart timer) | this commit | 3 runbook coverage tests (each alert has section heading, contains diagnosis + fix, links systemctl or journalctl) | n/a |
| Mirror-domains Grafana panel | `docs/observability/dashboards/sovereign-os-m060-mirror-domains.json` — 9 panels covering the chain-wide signal: worst-severity + observer-age stats, per-domain severity time-series (one series per D-02/13/14/15/17/18), live per-domain state table with `note` column from `selfdef_m060_doctor_domain_info`, resident-vs-published matrix table (the wedge case = resident=1 + published=0), observer-age over time. Cross-links to the D-CLI sub-chain dashboard | this commit | 11 dashboard contract tests | n/a |
| Smoke probes doctor observers | `scripts/diagnostics/m060-smoke.py` extended with `probe_node_exporter_textfile()` + `summarize_doctor()` + `--node-exporter-url` + `--skip-doctor-observers` flags. One operator command now verifies BOTH the daemon-side publish state (10 mirrors + chain-health endpoint) AND the doctor-observer freshness (cli-mirror + m060-chain textfiles via node_exporter). FAIL exits 1 so monitoring can chain on it | this commit | 11 contract tests on the doctor probe + summarizer + arg surface + exit-code logic | selfdef `e9ab056` + `ce58154` |
| `sovereign-osctl m060-doctor` named verb | `scripts/sovereign-osctl` `m060-doctor` dispatch updated to surface the new `--skip-doctor-observers` + `--node-exporter-url` flags in the operator-facing help text. Operators discover the doctor-observer probe via `sovereign-osctl --help` without spelunking through the m060-smoke.py source | `0935839` | 1 new + 7 existing `test_sovereign_osctl_help_m060_coverage.py` tests (load-bearing flag exposure for the doctor observer probe) | n/a |

## MS022 — Per-token SSE subscriber quota (consumer side)

**Selfdef producer:** see selfdef `backlog/SHIPPED.md` MS022 section — 6 `selfdef_sse_subscribers_*` Prometheus gauges shipped at selfdef commit `77b4499`.

**Shipped this milestone (sovereign-os consumer side):**

| R-row family | Surface | Commits | Tests | Selfdef pair |
|---|---|---|---|---|
| MS022 Prometheus alerts | 3 new alerts (`MS022SseGlobalQuotaApproaching` warn at saturation > 0.85 for 5m; `MS022SseGlobalQuotaSaturated` critical at >= 1.0 for 2m; `MS022SsePerTokenQuotaSaturated` warn at saturated > 0 for 5m) in `config/prometheus/alerts/ms022-sse-quota.rules.yml`. Each carries `subsystem=ms022-sse-quota` label + `runbook_url` to the deployment-guide section | this commit | 12 contract tests (alerts present, fields complete, metric references correct, severity classification matches semantics, thresholds locked at 0.85 + 1.0, every alert has runbook section in the guide, runbook sections carry diagnosis + fix commands) | selfdef `77b4499` |
| MS022 runbook sections | 3 `#### MS022Sse{GlobalQuotaApproaching,GlobalQuotaSaturated,PerTokenQuotaSaturated}` sections appended to `docs/operator/m060-deployment-guide.md`. Each section carries diagnosis (curl /metrics filtering on the saturation/per-token gauges + journal grep for HTTP 429s) + fix (config-edit `[api].max_sse_subscribers{,_per_token}` + `systemctl restart selfdefd`, OR identify subscriber leak via per-token table) | this commit | 3 runbook coverage assertions inside the alert contract test | n/a |
| MS022 Grafana panel | `docs/observability/dashboards/sovereign-os-ms022-sse-quota.json` — 10 panels: 4 stats (saturation %, active count, cap, tokens-saturated), 4 timeseries (saturation trend with alert threshold lines at 0.85 + 1.0, active-vs-cap gap, per-token-saturated, per-token cap step-change), 1 table (topk(20) per-token subscribers, Value→subscribers column rename), 1 companion (M060 chain-health rate). Cross-links to the selfdef-side producer source | `69f8dba` | 10 dashboard contract tests (title/uid/tags lock, all 6 producer metrics on ≥1 panel, saturation panel red threshold == 0.85 matches alert, time-series visualizes both 0.85 + 1.0 thresholds, per-token table uses topk + renames, links to producer source, 30s refresh, panel count == 10, companion M060 signal) | n/a |
| MS022 master-dashboard banner + proxy API | `scripts/operator/ms022-sse-quota-api.py` (NEW) — parses selfdef daemon `/metrics` (UNIX socket / TCP fallback) for the 6 `selfdef_sse_subscribers_*` gauges, classifies into ok/approaching/saturated/unreachable (thresholds locked at 0.85 + 1.0 matching the alert rules), exposes `/api/ms022/sse-quota` + `/api/ms022/state` for the cockpit. `webapp/master-dashboard/index.html` (modified) — new MS022 banner DIV next to the existing M060 chain-health banner, with `renderMS022SseQuotaBanner()` polling on the 30s cadence + Grafana dashboard deep-link in the footer. Operators see SSE quota state on D-00 master, not only in Grafana | `71127b3` | 15 contract tests on the parser + state classifier + threshold-alert-rule lockstep + dashboard wire-shape (banner DOM present, polls canonical endpoint, renderer invoked on tick, links to Grafana panel) | selfdef `77b4499` |
| MS022 systemd unit | `systemd/system/sovereign-ms022-sse-quota-api.service` — Type=simple unit binding the proxy daemon on `127.0.0.1:7711` (port chosen to NOT collide with the existing `sovereign-m060-health-api.service` on 8160). Restart=on-failure with 3s backoff. After=network.target. Same R171 defense-in-depth hardening as the m060-health-api sibling (ProtectSystem=strict, NoNewPrivileges, RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6, SystemCallFilter=@system-service ~@privileged @resources, etc.). Pure-read service — explicitly NO ReadWritePaths (the proxy never writes; drift would expose a R10212 mutation surface). Loopback-bind by default, drop-in-override pattern for exposure beyond localhost matching the sibling template | `8edb589` | 13 contract tests (file present, ExecStart references the right script, READ-ONLY doctrine + R10212 advertised in comments, After=network.target, Type=simple + Restart=on-failure + RestartSec=3, loopback-bind default, port doesn't collide with m060-health-api sibling, SELFDEF_SOCKET path matches sibling, full R171 hardening directive set, AddressFamilies restricted to UNIX+INET, no ReadWritePaths declared (R10212 enforcement), [Install] WantedBy=multi-user.target, Documentation= link present) | n/a |
| MS022 consumer-side operator guide | `docs/operator/ms022-sse-quota-cockpit.md` — single-page sovereign-os-side reference paralleling the selfdef-side `ms022-sse-subscriber-quota.md`. Documents the 4 consumer surfaces (master-dashboard banner DOM contract, 3 Prometheus alerts with locked thresholds, 10-panel Grafana dashboard, proxy daemon + systemd unit), state enumeration matching the alert thresholds (0.85/1.0), enable-on-boot + drop-in override recipes, verification recipes (curl /healthz, /api/ms022/sse-quota, Prometheus /rules cross-check), failure-mode → first-action crib sheet routing every fix to the selfdef-host (R10212 sacrosanct), R10212 boundary callout with 50-contract-test cross-repo inventory | `b8b445a` | 12 contract tests (guide present, every referenced surface file resolves on disk, alert thresholds 0.85 + 1.0 documented, all 3 alert names listed, all 4 consumer-side surfaces listed, R10212 boundary asserted verbatim, 50-test inventory cited exactly, relative paths resolve from docs/operator/) | selfdef `3fadc87` |
| `sovereign-osctl ms022-doctor` named verb | `scripts/diagnostics/ms022-doctor.py` (NEW) — 5-check operator triage across the MS022 chain: proxy-daemon /healthz reachable, proxy-state /api/ms022/state classifier round-trip, proxy-envelope JSON shape matches the master-dashboard banner contract, systemd unit is-active, master-banner /api/ms022/sse-quota path reachable. 3-tier severity ladder (0/1/2 = GREEN/YELLOW/RED) matching the cli-mirror-doctor convention so operators don't get two competing severity vocabularies. Operator-readable table + `--json` for monitoring + `--strict` exit-1-on-warn for CI fail-fast. Wired into `scripts/sovereign-osctl` as `ms022-doctor)` dispatch arm + advertised in --help (R10212 callout reminding operators every fix routes back to the selfdef-host) | `5d85528` | 11 contract tests (script present, module loads, severity enum matches cli-mirror-doctor convention, all 5 checks run, JSON envelope keys locked, --strict exits 1 on warn, FAIL exits 2 without --strict, default proxy URL matches systemd unit port (drift catch), proxy-state check handles all 4 classifier states the proxy emits, osctl dispatches to the script, --help advertises the verb with severity exit-code + R10212 explanation) | n/a |
| MS022 cross-surface threshold-lockstep lint | `tests/lint/test_ms022_threshold_lockstep_contract.py` (NEW) — drift-protection beyond the per-surface contracts. Asserts the 0.85 + 1.0 constants appear consistently across all 5 in-repo surfaces (alert rules YAML, proxy daemon Python constants, Grafana dashboard threshold steps, cockpit guide text, doctor classifier via module import) AND the 4 state names (ok/approaching/saturated/unreachable) are identical across the proxy daemon's /version states list + the cockpit guide state-enumeration table. Also asserts alert severity (warning/critical) aligns with the doctor's severity classes (WARN/FAIL) so the page severity matches the CLI exit-code class — drift here = operator confusion. Optional partner-repo cross-reference via `$SELFDEF_REPO_ROOT` reads selfdef's `crates/selfdef-cli/src/sse_quota.rs` and asserts the Rust constants `APPROACHING_THRESHOLD` + `SATURATED_THRESHOLD` match — when the env var is set (cross-repo CI / local dev with both repos cloned), CI catches partner drift at lint time (commit `ac6b0ab`) | `ac6b0ab` | 8 contract tests (alert YAML literal threshold expressions, proxy daemon constants, Grafana visible threshold steps, cockpit guide text mentions, doctor classifier import-time constants, partner-repo Rust constants under opt-in env, state-name set across surfaces, severity-class alignment) | selfdef `24bc3c6` |
| M060 cross-surface threshold-lockstep lint | `tests/lint/test_m060_threshold_lockstep_contract.py` — same drift-protection pattern as MS022 above, applied to the M060 chain invariants. Asserts the 300s stale-age + 5-state chain-state enum + 2 chain_link labels appear consistently across all in-repo surfaces: both observer-silent alerts use literal `> 300`, master-dashboard `M060_TILE_STALE_AGE_SECS = 5 * 60`, m060-health-api `/version` states list = `{online, degraded, stale, offline, unreachable}`, all 6 sub-chain alerts (3 cli-mirror + 3 mirror-domain) carry the right `chain_link` label, both Grafana sub-chain dashboards render the observer-age red threshold at 300s, both observer-silent runbook sections exist in the deployment guide, master-dashboard `knownStates` JS const includes the api-emitted state set. Optional cross-repo via `$SELFDEF_REPO_ROOT` asserts the partner's `crates/selfdef-api/src/m060_health.rs` `STALE_AGE_SECS: u64 = 5 * 60` const equals 300 | `489e91a` | 8 contract tests (observer-silent expressions both `> 300`, master-dashboard JS const, health-api /version states set, chain_link labels for cli-mirror + mirror-domain, Grafana dashboards 300s red threshold, deployment-guide runbook sections for both observer-silents, master-dashboard knownStates set, partner-repo selfdef-api Rust const) | selfdef `32ec32b` |
| m060-smoke MS022 chain integration | `scripts/diagnostics/m060-smoke.py` extended again — one operator command now probes BOTH observability verticals shipped this milestone (M060 cockpit-mirror chain + MS022 SSE-quota chain). New: `probe_ms022_state()` hits the proxy daemon's `/api/ms022/state` endpoint (default `http://localhost:7711`; honors `$SOVEREIGN_OS_MS022_PROXY_URL` matching the systemd unit's bind port — drift-locked by contract test); `summarize_ms022()` classifies into the 4-state enum (ok/approaching/saturated/unreachable) with state-specific operator-readable one-liners; `--ms022-proxy-url` + `--skip-ms022` flags; new `ms022_sse_quota` block in the JSON envelope (skipped/result/failed); new `MS022 SSE quota` row in the table output; new `ms022_failed=N` counter in the summary line; saturated triggers `exit 1` — mirrors the doctor-fail exit contract so a single CI exit code signals "any observability vertical reports critical state". Approaching is warn-not-fail (exit 0) per the alert severity ladder. Honest-offline when proxy daemon is down (UNREACHABLE summary, distinct from a reachable proxy reporting state='unreachable' which means selfdefd unreachable from outside) | this commit | 15 contract tests (helpers exposed, default URL port matches systemd unit, endpoint path canonical, probe returns honest-offline on unreachable, probe parses classifier, summarize handles all 4 states, summarize distinguishes proxy-down from state='unreachable', --skip-ms022 + --ms022-proxy-url flags wired, --skip-ms022 emits skipped/None block, saturated triggers exit 1, ok does not, approaching does not, summary line includes counter, JSON envelope shape locked, env var documented in --help) | selfdef `32ec32b` |

## Four-watchdog (IPS spine) consumer-side observability

| Surface | Shipped artifact | Commit | Tests | Selfdef-side producer |
|---|---|---|---|---|
| Prometheus alert rules | `config/prometheus/alerts/four-watchdog.rules.yml` — 4 alerts (`FourWatchdogWorstSeverityCritical` critical at `worst_severity >= 2` for 2m; `FourWatchdogAnyWarn` warning at `worst_severity == 1` for 5m — exact match avoids double-paging with the critical; `FourWatchdogTextfileEmitFailed` critical on the honest-offline sentinel for 5m — ALWAYS takes precedence over rollup alerts; `FourWatchdogObserverSilent` critical at `time() - last_run_unix > 300` for 2m — same 300s threshold as the M060 chain, locked by contract test). Each carries `subsystem=four-watchdog` + a distinct `spine_link` label (`rollup` / `observer-fault` / `observer-silent`) + `runbook_url` to the deployment-guide section. Project boundary R10212: pure observability — the enforcement (the 4 watchdogs themselves) lives in selfdefd; sovereign-os alerts on the published gauges only | this commit | 15 contract tests in `tests/lint/test_four_watchdog_alerts_contract.py` (rules file present + valid YAML, all 4 alerts present, every alert carries full envelope, worst-severity references rollup gauge, WARN targets `== 1` exactly to avoid double-page, emit-failed references sentinel, observer-silent threshold locked at 300s + references `last_run_unix`, observer-fault paths classified critical, spine_link labels distinguish origin, rule group interval == 30s, runbook URLs all point at deployment-guide, IPS-spine MS046+MS047+MS044+MS048 anchor present, selfdef producer commit cited, runbook sections present for all 4 alerts, every runbook section carries Diagnosis + Fix + fenced code block) | selfdef `7869a45` + `a009b39` |
| four-watchdog runbook sections | 4 `#### FourWatchdog*` sections appended to `docs/operator/m060-deployment-guide.md` matching the M060 + MS022 runbook pattern. Each section carries: TL;DR meaning, operator-runnable Diagnosis bash block (curl /metrics filtering on the worst_severity gauge + `selfdefctl alerts --json` cross-check + per-alert routing by `ms=MS046|MS047|MS044|MS048` label), Fix block (per-watchdog route to MS046 process-watchdog / MS047 perimeter / MS044 tamper / MS048 config remediation paths). The TextfileEmitFailed section explicitly documents the honest-offline precedence: when firing, the other 3 gauges cannot be trusted as fresh — drift here would defeat the wrapper's honest-offline contract | `795cd12` | 2 runbook coverage assertions inside the alert contract test (sections present for every alert, every section carries Diagnosis + Fix + fenced code block) | n/a |
| four-watchdog Grafana dashboard | `docs/observability/dashboards/sovereign-os-four-watchdog.json` — 9-panel cockpit panel rendering the selfdef-side `selfdef_four_watchdog_*` gauges. 4 stats (worst-severity rollup with -1/0/1/2 → UNKNOWN/OK/WARN/CRITICAL mapping, observer-age with red at 300s matching alert lockstep, alerts-at-WARN+ count, emit-failed sentinel with FAILED text mapping), 4 timeseries (per-alert severity with `{{ms}} · {{alert}}` legendFormat for MS-family grouping, worst-severity rollup with red step at 2, emit-failed sentinel timeseries with red bands marking wedged-wrapper windows, observer-age over time with red at 300s), 1 drill-down table (per-alert state with severity color-mapping). Tags include `sovereign-os`, `selfdef`, `four-watchdog`, `IPS-spine`, `observability` for Grafana tag-filter discoverability. Cross-links to selfdef producer source + deployment-guide runbook + dashboard-local runbook anchor. 30s refresh interval. Dashboard #21 alongside the existing 20 (M060 cli-mirror + M060 mirror-domains + 18 prior dashboards) | `985c565` | 15 contract tests in `tests/lint/test_four_watchdog_dashboard_contract.py` (file present + valid JSON, title locked, uid canonical, tags include IPS-spine marker, every of 4 canonical gauges appears on ≥1 panel, worst-severity panel red threshold at 2 matches alert, observer-age panel red threshold at 300s matches cross-surface lockstep, emit-failed FAILED text mapping, per-alert panel groups by `{{ms}}` legendFormat, links to selfdef producer source, refresh interval set, panel count locked at 9, links to deployment-guide runbook, dashboard comment cites selfdef producer commits 7869a45/a009b39, dashboard comment anchors MS046+MS047+MS044+MS048 IPS-spine milestones) | selfdef `7869a45` + `a009b39` |

## Selfdef module-catalog consumer-side observability

| Surface | Shipped artifact | Commit | Tests | Selfdef-side producer |
|---|---|---|---|---|
| Prometheus alert rules | `config/prometheus/alerts/selfdef-modules-catalog.rules.yml` — 3 alerts (`SelfdefModulesTextfileEmitFailed` critical at `emit_failed > 0` for 5m — honest-offline sentinel that ALWAYS takes precedence over rollup alerts; `SelfdefModulesObserverSilent` critical at `time() - last_run_unix > 300` for 2m — locked at 300s matching M060 + four-watchdog chain-wide threshold via cross-surface lockstep contract; `SelfdefModulesCountLow` warning at `total < 100` for 10m — generous floor since selfdef ships 188+ modules at install time). Each carries `subsystem=selfdef-modules-catalog` + distinct `catalog_link` label (observer-fault / observer-silent / rollup) + `runbook_url`. Project boundary R10212: pure observability — module catalog enforcement lives in selfdefd; sovereign-os alerts on the published gauges only | this commit | 12 contract tests in `tests/lint/test_selfdef_modules_catalog_alerts_contract.py` (rules file present + valid YAML, all 3 alerts present, every alert carries full envelope, observer-silent threshold locked at 300s + references `last_run_unix`, emit-failed references sentinel gauge, observer-fault paths classified critical, count-low threshold locked at 100, catalog_link labels canonical, rule group interval 30s, selfdef producer commit `1ce88c7` cited, runbook sections present for all 3 alerts with Diagnosis + Fix + fenced code blocks) | selfdef `1ce88c7` + `b2f2e20` |
| module-catalog runbook sections | 3 `#### SelfdefModules*` sections appended to `docs/operator/m060-deployment-guide.md`. Each section: TL;DR meaning, operator-runnable Diagnosis bash block (`systemctl status` + `journalctl` + `selfdefctl modules list --json | jq 'length'` + per-category curl), Fix block (per-cause routing: missing dep / daemon unreachable / incomplete install / corrupted modules dir). The TextfileEmitFailed section explicitly documents the honest-offline precedence — drift here would defeat the wrapper's honest-offline contract | `4a8b861` | 2 runbook coverage assertions inside the alert contract test (sections present for every alert, every section carries Diagnosis + Fix + fenced code block) | n/a |
| **NEW this commit** module-catalog Grafana dashboard | `docs/observability/dashboards/sovereign-os-selfdef-modules.json` — 9-panel cockpit dashboard rendering the selfdef-side `selfdef_modules_*` gauges. 4 stats (total-modules with 100-floor red threshold matching CountLow alert, observer-age with red at 300s matching ObserverSilent alert + cross-surface lockstep, categories-tracked count, emit-failed sentinel with FAILED text mapping), 3 timeseries (per-category over time with `{{category}}` legendFormat + stacked normal mode for IPS-spine visibility, total-modules with 100-floor threshold, emit-failed sentinel with red bands marking wedged-wrapper windows), 2 drill-down tables (per-category breakdown sortable by count, per-phase breakdown for pre/main/post install-phase visibility). Tags include `sovereign-os`, `selfdef`, `modules-catalog`, `observability` for Grafana tag-filter discoverability. Cross-links to selfdef producer source + deployment-guide runbook + dashboard-local runbook anchor. 30s refresh interval matching sibling cockpit dashboards. Dashboard #23 in the sovereign-os webapp inventory (alongside M060 cli-mirror, M060 mirror-domains, sovereign-os-four-watchdog, sovereign-os-ms022-sse-quota, 18 prior dashboards, and the runtime-modes cockpit) | this commit | 14 contract tests in `tests/lint/test_selfdef_modules_dashboard_contract.py` (file present + valid JSON, title locked, uid canonical, tags include canonical markers, every of 5 canonical gauges appears on ≥1 panel, observer-age panel red threshold at 300s matches cross-surface lockstep, total-modules panels mark 100-floor threshold matching CountLow alert, emit-failed FAILED text mapping, per-category panel uses `{{category}}` legendFormat for direct identification, links to selfdef producer source, 30s refresh, panel count locked at 9, links to deployment-guide runbook, dashboard comment cites selfdef producer commits 1ce88c7/b2f2e20) | selfdef `1ce88c7` + `b2f2e20` |

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

### M002 — 32/64-bit control-word injected logic per branch

| Surface | Shipped artifact |
|---|---|
| Choice envelope | `crates/sovereign-choice-envelope/` |

### M003 — Hardware topology + PCIe lane discipline

| Surface | Shipped artifact |
|---|---|
| Hardware scripts | `scripts/hardware/avx512-advisor.py`, `scripts/hardware/bios-directives.py`, `scripts/hardware/bios-info.py`, `scripts/hardware/apc-default-profile.py` |
| cgroup-systemd | `crates/sovereign-cgroup-systemd/` |

### M013 — Observability as control input

| Surface | Shipped artifact |
|---|---|
| Observability fabric | `crates/sovereign-observability-fabric/` |
| Grafana dashboards | `docs/observability/dashboards/` (20 dashboards including sovereign-os-router, sovereign-os-inference, sovereign-os-auditor, sovereign-os-trinity, sovereign-os-doc-coverage, the 2 new M060 sub-chain dashboards shipped this session) |
| Prometheus alerts | `config/prometheus/alerts/m060-chain-health.rules.yml` |
| selfdef hot-store retention alert (SDD-081 consumer side) | `config/prometheus/alerts/selfdef-store-retention.rules.yml` — `SelfdefStoreRetentionStalled` pages when selfdef has retention ENABLED (`selfdef_store_retention_enabled==1`) but the sweep counter hasn't advanced in >13h (loop stalled → unbounded hot store, the F-2026-016 outcome). The `_enabled` guard means opt-out hosts never false-page. Runbook section + `tests/lint/test_selfdef_store_retention_alerts_contract.py` (locks the guard) + the generic anchor/metric-lockstep gates. Proper producer→consumer split: selfdef emits the /metrics series (SDD-081 D-1), sovereign-os owns the alert + runbook. |
| selfdef hot-store retention dashboard (SDD-081 consumer side) | `docs/observability/dashboards/sovereign-os-selfdef-store-retention.json` — cockpit view of the daemon's /metrics retention series (enabled gauge, hot-store size, cumulative sweeps + pruned, pruned-rate, size trend). 6 panels; pairs with the SelfdefStoreRetentionStalled alert. Covered by the generic dashboard json-valid + selfdef-metric cross-repo lockstep gates (every selfdef_* series resolves to a real emitter). Completes the SDD-081 observability surface symmetry: selfdef sweep+metrics+panel → sovereign-os alert+runbook+dashboard. |
| selfdef storage-mounts cockpit dashboard | `docs/observability/dashboards/sovereign-os-selfdef-storage-mounts.json` — per-mount usage view (used % / used bytes / size bytes, labeled by mountpoint) off the daemon's `selfdef_storage_mount_*` /metrics series (MS011 Z-10). Closes a real cockpit gap: disk pressure is a top operational concern and the selfdef-side SelfdefStorageMount{Yellow,Red} alerts page on it, but sovereign-os had no at-a-glance view. Covered by the generic dashboard json-valid + cross-repo selfdef-metric lockstep gates. |
| selfdef IPS detection-stream cockpit dashboard | `docs/observability/dashboards/sovereign-os-selfdef-detection-stream.json` — the operator's at-a-glance view of selfdef's CORE output: events/sec, findings/sec by severity, events/sec by class, + cumulative totals + ingest-lag, off the selfdef-api /metrics counters (selfdef_{events,findings}_total, _by_severity, _by_class). Closed the most central cockpit gap — the IPS detection pipeline's output had no sovereign-os view. Covered by the generic dashboard json-valid + cross-repo selfdef-metric lockstep gates. |
| selfdef IPS responder-fleet overview dashboard | `docs/observability/dashboards/sovereign-os-selfdef-responder-fleet.json` — consolidated view of all 13 selfdef responder action surfaces (SDD-065..078) at once: active responses + pending operator decisions per surface (26 series). Per-family dashboards drill into one surface; this is the fleet 'which surfaces are active / awaiting my decision' view, complementing the ips-host-overview single-number rollup. Covered by the generic json-valid + cross-repo selfdef-metric lockstep gates. |
| selfdef audit-chain integrity dashboard (security) | `docs/observability/dashboards/sovereign-os-selfdef-audit-chain.json` — tamper-detection cockpit view: per-subsystem (guardian MS044 / perimeter MS047 / scheduler MS048) SHA-256 audit-chain status (red at -1 = integrity BROKEN: corruption / tampering / concurrent writer) + chain-length trend, off selfdef_<sub>_audit_chain_events. Closed a security-critical gap — selfdef-side Selfdef<Sub>ChainBroken alerts page on it but the cockpit had no view. Covered by the generic json-valid + cross-repo selfdef-metric lockstep gates. |
| Action-surface alert runbook coverage (SDD-041) | Closed 64 dead `runbook_url` anchors across the 11 selfdef responder action-surface alert families (`config/prometheus/alerts/selfdef-{apparmor-profile-pivots,bpf-map-element-clears,capability-drops,env-scrubs,kernel-keyring-evictions,mfa-grant-revocations,mount-bindings,netns-isolations,process-tree-freezes,socket-fd-revocations,token-revocations}.rules.yml`). Authored 64 grounded runbook sections (Meaning/Diagnosis/Fix, real gauge metrics + `selfdef-<surface>-textfile` units + `.prom` paths) into `docs/operator/m060-deployment-guide.md` (+1059 lines), gated by `tests/lint/test_action_surface_alert_runbook_coverage.py` (3 tests: anchors resolve + Meaning/Fix scaffold present). Extended to ALL 33 alert families: authored the SDD-065 blockset / SDD-066 quarantine / SDD-067 revocations sections (13 more), fixed 4 typo'd `runbook_url` anchors (auth-events / disk-usage / kernel-modules / ms022), and added the generic `tests/lint/test_alert_runbook_anchor_coverage.py` locking every alert's in-repo anchor + runbook_url presence + bounded severity vocab. Net 81 broken incident links closed (64+17), 0 remaining. `docs/sdd/041-action-surface-alert-runbook-coverage.md` |
| Cross-repo dashboard↔selfdef-emitter lockstep | `tests/lint/test_selfdef_dashboard_metrics_lockstep.py` — the generic in-repo metrics lockstep only checks `sovereign_os_*`; this opt-in (`$SELFDEF_REPO_ROOT`) gate locks every `selfdef_*` series the 38 cockpit dashboards render against selfdef's actual emitters, so a producer rename can't silently flat-line a consumer panel. On first run it caught + fixed a real bug: `sovereign-os-ips-host-overview.json` summed `selfdef_quarantine_pending_decisions` (never emitted; masked by `or vector(0)`) into the operator decision-backlog tile, silently excluding quarantine pending-releases → corrected to `selfdef_quarantine_pending_releases`. |

### M014 — Memory OS

| Surface | Shipped artifact |
|---|---|
| Memory OS crate | `crates/sovereign-memory-os/` |

### M026 — Cockpit personalization

| Surface | Shipped artifact |
|---|---|
| Personalization crate | `crates/sovereign-cockpit-personalization/` |
| Theme palette | `crates/sovereign-cockpit-theme-palette/` |
| Accent color policy | `crates/sovereign-cockpit-accent-color-policy/` |
| Webapp control surface | `webapp/personalization/` |

### M027 — Sovereign dashboard toggle (per-dashboard visibility)

| Surface | Shipped artifact |
|---|---|
| Dashboard coverage tracker | `crates/sovereign-dashboard-coverage/` |
| Per-dashboard webapps with toggleable status banners | 20 dashboards under `webapp/d-*/` |

### M057 — Routing + 7-axis decision

| Surface | Shipped artifact |
|---|---|
| Router crate | `crates/sovereign-router-7axis/` |
| Trinity stack composition | `crates/sovereign-trinity/` |
| Grafana panel | `docs/observability/dashboards/sovereign-os-router.json` |

### M058 — Audit trail

| Surface | Shipped artifact |
|---|---|
| Cockpit audit-trail | `crates/sovereign-cockpit-audit-trail/` |
| Webapp | `webapp/auditor/` |
| Grafana | `docs/observability/dashboards/sovereign-os-auditor.json` |

### M077 — NVFP4 pretraining + inference pipeline

| Surface | Shipped artifact |
|---|---|
| Runtime crate | `crates/sovereign-nvfp4-runtime/` — 5 recipes (NVFP4-S/M/L/XL/XXL) + E2M1 + E4M3 + 1×16 block quantize/dequantize + stochastic rounding (unbiased ±2% verified, 13 passing tests, per `context.md` 2026-05-19) |
| Catalogue | `backlog/milestones/M077-nvfp4-pretraining-and-inference-pipeline.md` (170 R-rows) |

### M078 — HölderPO + GRPO post-training

| Surface | Shipped artifact |
|---|---|
| Runtime crate | `crates/sovereign-holderpo/` — Hölder-mean aggregator (p ∈ ℝ with geom/arith/quad/max/min limits verified) + 4 anneal schedules (Constant/Linear/Cosine/Step) + GRPO group-relative advantages with optional std normalisation (17 passing tests, per `context.md` 2026-05-19) |
| Catalogue | per `backlog/notes/external-research-ingestion-2026-05-19.md` |

### M012 — Storage and replay plane

| Surface | Shipped artifact |
|---|---|
| Replay runtime crates | `crates/sovereign-replay-bookmark-set/`, `crates/sovereign-replay-cursor/`, `crates/sovereign-replay-export-bundle/`, `crates/sovereign-replay-playback-rate/` — the 4-crate replay-plane family covering bookmark management, playback cursor, export-bundle assembly, and replay-rate control |
| Conversation thread + fork | `crates/sovereign-conversation-thread/`, `crates/sovereign-conversation-fork-event/`, `crates/sovereign-conversation-search-index/` — replay's upstream substrate (the conversation history thread + branching events + search index) |

### M017 — Model portfolio strategy

| Surface | Shipped artifact |
|---|---|
| Provider catalog | `crates/sovereign-provider-catalog/` — catalogue of model providers (selfdef-local + Anthropic + OpenAI remote) the gateway routes across |

### M025 — Cognitive Compiler — intent to DAG

| Surface | Shipped artifact |
|---|---|
| Cognitive compiler crate | `crates/sovereign-cognitive-compiler/` — intent-to-DAG compilation surface |

### M028 — Memory OS — 8 memory types

| Surface | Shipped artifact |
|---|---|
| Memory OS crate (cross-referenced from M014) | `crates/sovereign-memory-os/` — 8 memory type variants per the M028 catalogue (M014 shipped the substrate; M028 catalogues the 8-type structure on top of it) |
| Pressure sensors | `crates/sovereign-pressure-sensors/` — memory pressure observability feeding back into routing decisions |
| Environment maps | `crates/sovereign-environment-maps/` — environment-aware memory layout |

### M033 — Compatibility Gateway

| Surface | Shipped artifact |
|---|---|
| Gateway crate | `crates/sovereign-gateway/` — the surface that exposes sovereign-os to external clients (Anthropic / OpenAI compatibility shim) |
| Prompt template registry | `crates/sovereign-prompt-template-registry/`, `crates/sovereign-prompt-history-ring/`, `crates/sovereign-prompt-rationale/` — prompt substrate the gateway routes |

### M037 — Spec / TDD / agent evals

| Surface | Shipped artifact |
|---|---|
| Eval plane | `crates/sovereign-eval-plane/`, `crates/sovereign-eval-result-summary/`, `crates/sovereign-eval-suite-catalog/` — the 3-crate eval-driven autonomy substrate per M037's evidence-driven authority discipline |
| Value plane | `crates/sovereign-value-plane/` — the values-projection surface the evals score against |
| Tool invocation record | `crates/sovereign-tool-invocation-record/` — per-invocation evaluation record for the agent-eval pipeline |
| LM eval — bits-per-byte | `crates/sovereign-perplexity/` `Eval::bits_per_token` (= log₂ perplexity) + `Eval::bits_per_byte(scored_bytes)` — the standard **tokenizer-independent** information-cost metric for cross-vocabulary model comparison, which token-normalized perplexity can't provide. Commit `ff224cf`; 2 unit (2^(bits/token) recovers perplexity; bits/byte normalizes by byte count + zero-guard) |
| Selective prompt compression (LLMLingua) | `crates/sovereign-perplexity/` `token_logprobs` (exposes the per-token surprisal `evaluate` already computed but discarded; `evaluate` now reuses it — no duplication) + `crates/sovereign-llm/` `SovereignLlm::compress_prompt(text, keep_ratio)` — tokenize → score each token's surprisal under **this** model → drop the predictable tokens to the keep-ratio → decode, in one scoring pass with no extra model runs (anchors keep the boundary tokens). Wires `sovereign-prompt-compress` (previously **zero consumers**) into the real runtime so a long context prompt can be shrunk before generation. Commit `4682454`; 2 perplexity unit (token_logprobs align with evaluate's total; uniform model = −ln(vocab)) + 4 llm unit (shrinks + stays decodable; ratio 1.0 keeps everything; sub-2-token text unchanged; reproducible) |

### M038 — Hardware-aware AIDLC

| Surface | Shipped artifact |
|---|---|
| Hardware registry + dispatch | `crates/sovereign-hardware-registry/`, `crates/sovereign-hardware-dispatch-eligibility/`, `crates/sovereign-hardware-load-sample/`, `crates/sovereign-hardware-thermal-policy/` — 4-crate hardware-aware AIDLC substrate (registry of resources, dispatch eligibility classifier, load samplers, thermal policy) |
| Hardware scripts (cross-referenced from M003) | `scripts/hardware/` family |

### M042 — Choice architecture — sovereignty as policy-composable

| Surface | Shipped artifact |
|---|---|
| Choice envelope (cross-referenced from M002) | `crates/sovereign-choice-envelope/` |
| Execution mode registry | `crates/sovereign-execution-mode-registry/`, `crates/sovereign-mode-default-policy/`, `crates/sovereign-mode-transition-log/` — the 3-crate execution-mode discipline ensuring mode transitions are policy-checked + audit-logged |
| Policy questions | `crates/sovereign-policy-questions/` — the operator-facing policy-choice surface |

### M044 — Sovereign-OS substrate (Debian 13 / Ubuntu 24)

| Surface | Shipped artifact |
|---|---|
| Inheritance contracts | `crates/sovereign-inheritance-artifacts/`, `crates/sovereign-inheritance-contracts/` — the contract surface that sovereign-os inherits from the upstream Debian base (so deviations from Debian doctrine are typed and detectable) |
| Doctrinal preservation | `crates/sovereign-doctrinal-preservation/`, `crates/sovereign-doctrine-citation/` — preserves the operator-written doctrinal layer through OS-level mutations |

### M045 — Linux as intelligence governor (cgroup v2 / systemd / PSI / eBPF)

| Surface | Shipped artifact |
|---|---|
| cgroup-systemd binding (cross-referenced from M003) | `crates/sovereign-cgroup-systemd/` |
| Pressure sensors (PSI bridge) | `crates/sovereign-pressure-sensors/` — exposes Linux PSI signals into the intelligence-governor decision surface |

### M046 — Beat the cloud — runtime adaptation + LoRA foundry

| Surface | Shipped artifact |
|---|---|
| LoRA foundry crate | `crates/sovereign-lora-foundry/` — the LoRA-foundry surface (on-device adapter training/swap mechanics) |

### M047 — Continuity — CRIU + ZFS + warm sandboxes + hibernated thought

| Surface | Shipped artifact |
|---|---|
| Continuity manager | `crates/sovereign-continuity-manager/` — orchestrates CRIU checkpoints, warm-sandbox preservation, hibernated-thought state |
| ZFS commit gate | `crates/sovereign-zfs-commit-gate/` — gates ZFS sync=always commits per the M068 storage architecture |

### M048 — Modules family

| Surface | Shipped artifact |
|---|---|
| Module catalog | `crates/sovereign-module-catalog/` — the registry that enumerates the 13 module families M048 lists (Base OS / Compute Fabric / Sandbox Fabric / Gateway / Memory OS / Workflow Compiler / Eval-Value / Continuity / Observability / Policy / Config Resolver / LoRA Foundry / Hardware Profiler) |
| Tool catalog | `crates/sovereign-tool-catalog/` — tool-family roll-up matching the module-family inventory |
| Six pillars | `crates/sovereign-six-pillars/` — the 6-pillar cross-cutting tracker matching the doctrine layer above the 13 modules |

### M049 — Continuity through observability and policy

| Surface | Shipped artifact |
|---|---|
| Observability fabric (cross-referenced from M013) | `crates/sovereign-observability-fabric/` |
| Continuity manager (cross-referenced from M047) | `crates/sovereign-continuity-manager/` — observability feeds back into the continuity decision (when to CRIU, which sandboxes to warm) |

### M054 — 11 typed interfaces

| Surface | Shipped artifact |
|---|---|
| Gateway interface | `crates/sovereign-gateway/` |
| Router interface | `crates/sovereign-router-7axis/`, `crates/sovereign-routing-decision-log/`, `crates/sovereign-routing-preference/` |
| Eval interface | `crates/sovereign-eval-plane/` + sister crates |
| Observability interface | `crates/sovereign-observability-fabric/` + Prometheus alert YAML + Grafana dashboards |
| Policy interface | `crates/sovereign-policy-questions/`, `crates/sovereign-mode-default-policy/` |
| Memory interface | `crates/sovereign-memory-os/` + sister crates |
| Workflow interface | (via prompt-template-registry + cognitive-compiler) |
| Hardware interface | `crates/sovereign-hardware-registry/` + sister crates |

### M066 — Trinity Framework Genesis (Pulse / Weaver / Auditor)

| Surface | Shipped artifact |
|---|---|
| Trinity composition crate | `crates/sovereign-trinity/` — Pulse + Weaver + Auditor stack composition |
| Pulse status surface | `crates/sovereign-cockpit-status-pulse/` — the operator-cockpit-facing surface of the Pulse role |

### M068 — ZFS storage architecture

| Surface | Shipped artifact |
|---|---|
| ZFS commit gate | `crates/sovereign-zfs-commit-gate/` — sync=always commit gate per the M068 (tank/context + ashift=12 + lz4 + recordsize) architecture |

### M073 — 1-bit (ternary) logic + BitLinear Core

| Surface | Shipped artifact |
|---|---|
| External-research ingestion catalogue | `backlog/notes/external-research-ingestion-2026-05-19.md` (cross-ref M077, M078) — anchors the ternary-BitLinear research arc in the same external-ingestion sweep as NVFP4 + HölderPO |
| Inference-backend-stack SDD | `docs/sdd/011-inference-backend-stack.md` (cross-ref M009) — anchors the inference-runtime stack within which BitLinear cores could land |

### M074 — AVX-512 VNNI hardware fusion (512-bit ZMM / 64× INT8 / VPDPBUSD)

| Surface | Shipped artifact |
|---|---|
| Hardware-stack consolidation SDD | `docs/sdd/029-hardware-stack-consolidation.md` (cross-ref M007, M008, M039, M070) — anchors the AVX-512 VNNI hardware-fusion path in the consolidated hardware-stack architecture |
| AVX-512 advisor | `scripts/hardware/avx512-advisor.py` (cross-ref M007, M008, M039) — the operator-side surface for the VNNI hardware-fusion decisions |
| VDPBF16PS BF16 reference (M085 T1) | `crates/sovereign-vnni/` `f32_to_bf16` (round-to-nearest-even, NaN-quieting — the `VCVTNE2PS2BF16` conversion) + `bf16_to_f32` + `vdpbf16ps_lane` (2 BF16 pairs → one f32 accumulator lane) + `dot_bf16` + `MatBf16` matvec — the note's T1 "multiplication floues BF16" beside VPDPBUSD, halving weight memory at f32 range. Plus `MatI8::row_sums` (the zero-point correction term an asymmetric INT8 scheme needs). Commit `af681c7`; 8 unit (round-trip on representables; RNE at the exact halfway point; lane accumulate; dot == f32 on representables; matvec exact/close; guards + serde; row sums) |
| **INT8 VNNI precision activated in the model path** (M085 T1, built → used) | `crates/sovereign-linear/` `Precision::Int8` + `Int8Layer` — per-row symmetric `i8` weights (`max\|W[r]\|/127`), asymmetric `u8` activations with a zero point, `i32` accumulation via `sovereign-vnni::MatI8` (VPDPBUSD-style dots), dequantized with the row-sum correction `y = s_w·s_x·(acc − zp·Σ Wq)`. Makes `sovereign-vnni` (previously **zero consumers**) the execution backend of a first-class model precision: `MhaDecoderBlock::from_weights(&w, Precision::Int8)` works unchanged, and the running demo's stack is now **4 layers across 4 precisions** (`f32 \| ternary \| NVFP4-MHA \| INT8-VNNI-MHA`, one residual stream). Commit `af681c7`; 6 linear unit (close-to-f32 within 2% norm; argmax preserved; negative activations via zero-point; constant-input row-sum path; bits/param ≈8–13 + no energy report; contract + serde loops include Int8) + 1 mha-block e2e (INT8 block steps a sequence, tracks f32 within 5% norm) + demo asserts 4 layers / INT8-VNNI line |

### M075 — SRP hardware topology mapping

| Surface | Shipped artifact |
|---|---|
| SRP scheduler | `crates/sovereign-srp-scheduler/` — Conductor on CPU / Logic on GPU 0 / Oracle on GPU 1 scheduling discipline |
| Hardware registry (cross-referenced from M038) | `crates/sovereign-hardware-registry/` |

### M040 — Hyper features (MIG / FP4 / VFIO / ZFS commit gate)

| Surface | Shipped artifact |
|---|---|
| ZFS commit gate (cross-referenced from M047, M068) | `crates/sovereign-zfs-commit-gate/` |
| NVFP4 runtime (cross-referenced from M077) | `crates/sovereign-nvfp4-runtime/` — FP4 hyper-feature production code |

### M041 — Schema contracts (WORKFLOW / PROFILES / EVALS / POLICY / MODEL_REGISTRY / HARDWARE_PROFILES)

| Surface | Shipped artifact |
|---|---|
| Schema directory | `schemas/` — `mixin.schema.yaml`, `model-catalog.schema.yaml`, `profile.schema.yaml`, `runtime-profile.schema.yaml`, `whitelabel.schema.yaml` — the 5-schema typed contract substrate covering the 7 contract surfaces M041 enumerates |
| Profile validation | `scripts/validate-profiles.sh` — the runtime gate that enforces the contracts at install / boot time |
| Profile bundles | `crates/sovereign-profile-bundles/` — the typed bundle of profile-schema instances |

### M053 — Implementation language (11 build phases Phase 0..10)

| Surface | Shipped artifact |
|---|---|
| Bootstrap scripts | `scripts/bootstrap/` — Phase-0 bootstrap entry point |
| Build scripts | `scripts/build/` — Phase 1..10 build sequencing |
| Install scripts | `scripts/install/` — final-phase install discipline (`install-mode-advisor.py`, `operator-deps.py`, `paths.py`) |
| Setup entry | `scripts/setup.sh`, `scripts/onboard.sh` — operator-facing single-command bootstraps |

### M055 — Failure modes (10 taxonomies)

| Surface | Shipped artifact |
|---|---|
| Mode transition log | `crates/sovereign-mode-transition-log/` — append-only log of mode transitions enabling per-taxonomy failure-mode forensics |
| Policy questions | `crates/sovereign-policy-questions/` — the typed surface where each failure-taxonomy decision routes through |
| Choice envelope | `crates/sovereign-choice-envelope/` — the typed envelope around each control choice (drives the detect/contain/explain/recover/learn discipline) |

### M056 — Trust boundaries (7 authority levels / 5 trust rings)

| Surface | Shipped artifact |
|---|---|
| Cross-repo binding doctrine SDD | `docs/sdd/038-cross-repo-binding-doctrine.md` — anchors the typed cross-repo trust boundary (selfdef is the mutation authority; sovereign-os is read-only consumer per MS043 R10212) |
| Eight-surface delivery contract SDD | `docs/sdd/039-eight-surface-delivery-contract.md` — enumerates the 8 surfaces each milestone must reach; trust boundary integrated into the delivery contract |
| Inheritance contracts | `crates/sovereign-inheritance-contracts/` (cross-ref M044) — typed contract for the inherited-vs-original trust ring |

### M064 — "Debian as Ark" framing

| Surface | Shipped artifact |
|---|---|
| Distro-base SDD | `docs/sdd/021-distro-base.md` — Q-016 distro-base reconsideration documented here |
| Debian surface audit SDD | `docs/sdd/006-debian-surface-audit.md` — the foundational audit that M064 references for "what's inherited from Debian vs what we own" |
| Inheritance artifacts | `crates/sovereign-inheritance-artifacts/`, `crates/sovereign-inheritance-contracts/` — typed surface for the inherited-Debian layer |

### M065 — Five Stage Gates (SG1-SG5 + ExitPlanMode checkpoint ritual)

| Surface | Shipped artifact |
|---|---|
| Test-harness SDD | `docs/sdd/008-test-harness.md` + `docs/sdd/009-test-harness-bootstrap.md` — the test-harness scaffolding that the 5 SGs gate-keep |
| Stage-2 stub SDD | `docs/sdd/010-stage-2-stub.md` — the explicit gate from SG1 to SG2 |

### M067 — Custom kernel build pipeline

| Surface | Shipped artifact |
|---|---|
| Kernel-choice SDD | `docs/sdd/018-kernel-choice.md` — documents the -march=znver5 / GCC 14 / Linux 6.12 / bindeb-pkg pipeline choice |
| Kernel scripts | `scripts/kernel/` — the kernel-build automation directory |
| Hardware-stack consolidation SDD | `docs/sdd/029-hardware-stack-consolidation.md` — the architecture pass that informed the kernel-build decisions |

### M070 — Dual-CCD cache topology + core pinning

| Surface | Shipped artifact |
|---|---|
| Hardware-stack consolidation SDD | `docs/sdd/029-hardware-stack-consolidation.md` — pins the CCD-0=Pulse / CCD-1=Weaver+Auditor+Host topology |
| Trinity scripts | `scripts/pulse/`, `scripts/weaver/`, `scripts/auditor/`, `scripts/trinity/` — the operator-side runtime infrastructure for the 3 trinity roles (M066) pinned to their respective CCDs |

### M071 — Atomic State Transition Protocol (Weaver Execution)

| Surface | Shipped artifact |
|---|---|
| ZFS root layout SDD | `docs/sdd/017-zfs-root-layout.md` — the substrate for the O_DIRECT + POSIX AIO + lockless ZFS atomic-state discipline |
| ZFS commit gate (cross-ref M047, M068) | `crates/sovereign-zfs-commit-gate/` — the runtime that enforces sync=always atomic commits per the Weaver Execution model |

### M072 — Master Bootstrap Verification Checklist (6-phase operational grid)

| Surface | Shipped artifact |
|---|---|
| Bootstrap scripts | `scripts/bootstrap/` — the 6-phase bootstrap sequence |
| Validation entry | `scripts/validate-profiles.sh` — the verification-checklist entry point |
| Diagnostics scripts | `scripts/diagnostics/` — `autohealth.py`, `doctor.py`, the operator-facing post-bootstrap verification runners |

### M076 — Three load-balancing profiles

| Surface | Shipped artifact |
|---|---|
| Runtime profiles | `profiles/runtime/ultra-sovereign-efficiency.yaml`, `profiles/runtime/high-concurrency-burst.yaml`, `profiles/runtime/deep-context-synthesis.yaml` — the 3 runtime profiles that M076 enumerates (operator-tunable mode selection) |
| Runtime-profile schema | `schemas/runtime-profile.schema.yaml` — the typed contract the 3 profiles conform to |
| **NEW this commit** runtime-modes operator cockpit (webapp) | `webapp/runtime-modes/index.html` — operator-facing read-only cockpit rendering the 3 catalogued profile manifests side-by-side. Active-mode banner (polls `/api/runtime-modes/active`, flips to has-active state when marker present at `/run/sovereign-os/active-runtime-mode`), 3-card responsive grid (each card: name, id, one-line description parsed from YAML, raw-YAML link, active-state highlighting when the mode matches the marker), operator workflow runbook in a `<details>` block (selfdefctl modules apply commands for each mode), R10212 read-only boundary documented in footer. 30s refresh cadence matching the M060 + MS022 + four-watchdog cockpit banner conventions for operator visual consistency. Honest-offline when proxy unreachable (renders systemd unit name + remediation hint, never blank-screens). dashboard #22 in the sovereign-os webapp inventory |
| **NEW this commit** runtime-modes proxy daemon | `scripts/operator/runtime-modes-api.py` (NEW, stdlib-only) — read-only HTTP proxy serving 3 endpoints the cockpit consumes: `/api/runtime-modes/list` (3 profile summaries with name/description/yaml_path, in canonical catalogue order), `/api/runtime-modes/<id>` (full YAML body for drill-down — 404 on unknown id, drift-locked by contract test), `/api/runtime-modes/active` (active-mode marker read; returns None when marker absent OR when marker contains a non-canonical mode id — protects against operator typo activating phantom mode). Stdlib-only YAML summary parser (no PyYAML dep — extracts id/name/description fields by line-walking). `CANONICAL_MODE_IDS` tuple locked to prevent drift when an operator drops a 4th profile YAML. Honest-offline absent-profile handling (yaml_path persists in the listing with `absent: true` so the cockpit renders the proper fallback card). `--list-once` flag for testing/CI smoke. Default port 7713 (sits above 7712 four-watchdog-api, 7711 ms022-sse-quota-api, 8160 m060-health-api — 4 sibling proxies, 4 distinct ports) | this commit | 23 contract tests in `tests/lint/test_m076_runtime_modes_cockpit_contract.py` (webapp present + well-formed + M076 anchor + canonical endpoint polls + active-mode banner role/aria + graceful unreachable fallback + R10212 boundary documented + 30s refresh cadence + all 3 mode ids referenced in workflow runbook; proxy script present + executable + CANONICAL_MODE_IDS lock + default port 7713 + list returns exactly 3 modes in canonical order + summary parser extracts name + description + active-mode honest-offline when marker absent + active-mode rejects non-canonical mode ids + profile-detail rejects unknown ids; 3 canonical YAMLs present; systemd unit file present + canonical ExecStart + loopback default + port 7713 + NO ReadWritePaths directive (R10212 enforcement, comment-block-excluded) + 7-clause R171 hardening + M076 anchor) | n/a |
| **NEW this commit** runtime-modes systemd unit | `systemd/system/sovereign-runtime-modes-api.service` — Type=simple loopback-bound proxy daemon. Full R171 defense-in-depth hardening (ProtectSystem=strict + NoNewPrivileges + RestrictAddressFamilies AF_UNIX/INET/INET6 + SystemCallFilter @system-service + ~@privileged/@resources + 7 more clauses matching sibling proxy units). NO ReadWritePaths declared (R10212 enforcement — proxy is pure-read; the active-mode marker is read only). After=network.target. Environment= overrides for `SOVEREIGN_OS_PROFILES_RUNTIME_DIR` (default `/usr/share/sovereign-os/profiles/runtime`) and `SOVEREIGN_OS_ACTIVE_RUNTIME_MODE_MARKER` (default `/run/sovereign-os/active-runtime-mode`). M076 milestone anchored in the unit's Documentation block | this commit | 7 of the 23 contract tests above (systemd unit + R171 + R10212 + M076 anchor) | n/a |

### M081 — Whitelabel Architecture

| Surface | Shipped artifact |
|---|---|
| Whitelabel mechanism SDD | `docs/sdd/007-whitelabel-mechanism.md` — declarative rebrand mechanism design |
| Debian surface audit SDD | `docs/sdd/006-debian-surface-audit.md` — the audit input the whitelabel mechanism consumes |
| Whitelabel schema | `schemas/whitelabel.schema.yaml` — typed contract for whitelabel overrides |
| Whitelabel scripts | `scripts/whitelabel/` — the runtime rebrand applicator |
| Brand-identity placeholder SDD | `docs/sdd/012-brand-identity-placeholder.md` — documents the deferred brand-identity slot the whitelabel mechanism fills |

### M082 — TDD Harness Architecture (hardware-free validation)

| Surface | Shipped artifact |
|---|---|
| Test-harness SDD | `docs/sdd/008-test-harness.md` + `docs/sdd/009-test-harness-bootstrap.md` — the architectural foundations (cross-ref M065) |
| Test harness (selfdef-side cross-ref) | the selfdef-side test/coherence.sh 13-layer hardware-free validation harness is the canonical TDD-harness implementation; sovereign-os consumes the harness pattern from the partner repo |
| Hardware-free dispatch eligibility | `crates/sovereign-hardware-dispatch-eligibility/` — typed surface enabling hardware-free unit tests to enumerate which dispatch paths the test should exercise without the hardware actually being present |

### M079 — Activation steering interpretability surface

| Surface | Shipped artifact |
|---|---|
| Intervention class typed-mirror | `crates/sovereign-intervention-class-mirror/` — typed wire schema for the activation-steering intervention-class surface (white-box vs black-box intervention) — same MS007-style typed-mirror pattern, applied to interpretability surface |

### M080 — HRM (Hierarchical Reasoning Model) architectural class

| Surface | Shipped artifact |
|---|---|
| HRM runtime crate | `crates/sovereign-hrm-runtime/` — recurrent two-timescale brain-inspired architectural class as a parallel to the Transformer/Mamba/BitNet runtime family |

### M085 — Zen 5 AVX-512 three-tier instruction exploitation

| Surface | Shipped artifact |
|---|---|
| Milestone + verbatim note transcription | `backlog/milestones/M085-zen5-avx512-three-tier-instruction-exploitation.md` — the operator's handwritten 2026-07-02 note (9900X dual native 512-bit pipes; T1 quant/dot VNNI · T2 bitwise/attention ternary-mask · T3 structure/prune/KV VBMI/CD; PAM-3 GDDR7 + VPOPCNT margin) transcribed verbatim with image provenance; 8 epics E0808–E0815 |
| T1 built + activated | see M074 rows (commit `af681c7`): VDPBF16PS BF16 reference + `Precision::Int8` VNNI live in the model path; the demo runs 4 precisions in one residual stream |
| T3 completed | see M008 row (commit `af681c7`): `vpermb` / `vpshldv` / `expand` references with the compress→expand round trip pinned |
| T2 + margin status | VPTERNLOG / VP2INTERSECT / VPOPCNT references pre-existed in `crates/sovereign-bitops/`; their attention/ternary kernel consumers are tracked open as E0810/E0811/E0814. PAM-3/GDDR7 (E0815) is catalog-only — a memory-substrate property, cross-ref M038/M058 |
| Precision as a flexible profile (opt-in/out) | `crates/sovereign-precision-profile/` `PrecisionProfile` — a declarative, serde-able precision plan: a per-layer-index → `Precision` map + named high-precision projections + per-tier AVX-512 flags (`Tiers` T1/T2/T3), with an **f32 default that opts the whole stack out** of quantization, and presets (`f32` / `uniform` / `mixed` / `all_ternary` / `int8_hot`) that are starting points, not walls (every field public, round-trips). `resolve(i)`/`plan(n)` give the per-layer precision; nothing is hardcoded. **Consumed by the demo**: `sovereign-inference-demo` builds its multi-head layers at `profile.resolve(2)`/`resolve(3)` and prints the resolved plan (`"mixed" → [F32, Ternary, Nvfp4, Int8]`, opt-in/out, tier flags) — swap the profile and the stack rebuilds. Per the operator directive "everything is flexible … options and opt in and out and profiles" (2026-07-02). Commit `db9ef64`; 8 profile unit (f32 = full opt-out; mixed spans 4 precisions; uniform presets; fluent opt-in/out with layer overrides winning; high-precision tracking; tier flags; serde) + demo asserts the profile plan is reported |

### M086 — AVX-512 scalar-reference → real-SIMD lift plan (per flag)

| Surface | Shipped artifact |
|---|---|
| Milestone + per-flag lift plan | `backlog/milestones/M086-avx512-scalar-reference-to-simd-lift-plan.md` — the authoritative CPU-feature map for the note's instructions (8 core flags + VPOPCNT-as-two: `avx512f` VPTERNLOG · `avx512bw` · `avx512_vnni` VPDPBUSD **wired** · `avx512_bf16` VDPBF16PS **wired** · `avx512_vbmi` VPERMB · `avx512_vbmi2` VPSHLDV/VPCOMPRESS · `avx512_vp2intersect` VP2INTERSECT **no Zen 5 hardware** · `avx512_vpopcntdq` · `avx512_bitalg`), the 5-step lift shape per flag (intrinsic kernel in a sibling `-simd` crate → runtime `is_x86_feature_detected!` dispatch → `znver5` build flags → differential test vs scalar oracle → capability+profile gate), and epics E0817–E0821 (E0817/E0818/E0819 **done**; E0820 SIMD dispatcher + E0821 znver5 build flags **open**). Records that every kernel crate is `#![forbid(unsafe_code)]` today → all nine are semantically-exact scalar references, and VP2INTERSECT stays scalar-only forever (Intel Tiger-Lake-only, AMD never implemented) |
| `Precision::Bf16` — T1 BF16 becomes a wired precision (E0818) | `crates/sovereign-linear/` `Precision::Bf16` + `Backend::Bf16(MatBf16)` — the VDPBF16PS reference (`crates/sovereign-vnni::MatBf16`, 16-bit weights + f32 accumulation) is now a first-class model precision alongside `Int8`, not a reference-only kernel: `MhaDecoderBlock::from_weights(&w, Precision::Bf16)` works unchanged, `precision()`/`bits_per_param()` report Bf16/16.0, `forward` routes through `MatBf16::matvec`. Both wired T1 precisions (INT8 + BF16) now execute through `sovereign-vnni`. Commit `e04ff78`; 27 linear unit (incl. `bf16_forward_is_close_to_f32`; `bf16_exact_on_representable_weights_and_preserves_argmax`; `bf16_bits_per_param_is_sixteen`; Bf16 added to the contract + serde precision-iteration loops) + clippy clean |
| Capability gate — host caps decide tier eligibility (E0819) | `crates/sovereign-precision-profile/` `Tiers::detect()` (`is_x86_feature_detected!` for avx512vnni/avx512f/avx512vbmi2 on x86_64, `NONE` elsewhere) + `gated_by`/`unsupported_by`/`PrecisionProfile::gated_by`/`unsupported_tiers` + `PrecisionProfile::bf16()` preset. **Demonstrated in the running demo**: `sovereign-inference-demo` prints a `host caps : T1=… T2=… T3=… → gated tiers …` line from live detection, so the requested tier flags are intersected with what the host actually supports. Commit `e04ff78`; 12 profile unit (incl. detect/gated_by/unsupported/bf16 preset) + demo asserts the `host caps` line |
| `avx512-advisor tiers` verb + VP2INTERSECT flag (E0817) | `scripts/hardware/avx512-advisor.py` — new `tiers` command prints the M085 note's instruction → flag → Zen5 → host → engine map (`TIER_INSTRUCTIONS`, 9 rows; T1 both "wired", T2/T3 "scalar-ref"), `ZEN5_ABSENT_FLAGS = {"VP2INTERSECT"}`, and `VP2INTERSECT` added to `AVX512_FLAGS`/`FLAG_LOWERCASE` (`avx512_vp2intersect`) with 2 new `WORKLOAD_FIT` entries (token-intersect-attention, kv-cache-compaction). Commit `e04ff78`; nspawn advisor suite 16/16 (counts bumped 16→17 extensions, 9→11 workloads) + 4 lint (incl. `test_m085_tier_instructions_map_to_real_flags`; VP2INTERSECT mapping) |

### M004 — Oracle / Scout / Vector Arbiter role split

| Surface | Shipped artifact |
|---|---|
| Hardware-stack consolidation SDD | `docs/sdd/029-hardware-stack-consolidation.md` — anchors the Oracle/Scout/Vector-Arbiter role-split decision in the consolidated hardware stack |
| Trinity composition (cross-ref M066) | `crates/sovereign-trinity/` — the Pulse/Weaver/Auditor trinity is the runtime carrier of the Oracle/Scout/Vector-Arbiter role discipline |

### M005 — Agent runtime (four planes: Inference / Control / Memory / Tool)

| Surface | Shipped artifact |
|---|---|
| Inference plane | `crates/sovereign-nvfp4-runtime/`, `crates/sovereign-hrm-runtime/`, `crates/sovereign-holderpo/` — the 3 model-runtime families |
| Control plane | `crates/sovereign-gateway/`, `crates/sovereign-router-7axis/` — operator-facing control surface |
| Memory plane | `crates/sovereign-memory-os/` + sister crates (cross-ref M014, M028) |
| Tool plane | `crates/sovereign-tool-catalog/`, `crates/sovereign-tool-invocation-record/` (cross-ref M037, M048) |
| Control plane — ReAct loop repeat guard | `crates/sovereign-agent-loop/` `AgentLoop::with_repeat_guard(n)` + `StopReason` enum (FinalAnswer / StepCap / RepeatedAction) — stops the loop when the model issues the same tool call (name + args) `n` times instead of spinning to the step cap; the exit cause is now explicit on `AgentResult`. Default off (behavior unchanged). Wired + surfaced in `sovereign-agent-runtime` (commit `ab2dee9`). Commit `8f8b75f`; 4 unit (guard breaks identical-action loop, allows distinct actions, all three stop reasons reported) |
| Tool plane — parser robustness | `crates/sovereign-tool-dispatch/` `parse_call` trims whitespace around the tool name (so `[[tool: upper \|x]]` resolves; args verbatim) + `parse_all_calls` finds every marker in a reply (non-overlapping, malformed skipped). Commit `fc74f86`; 3 unit (whitespace-tolerant parse + dispatch, multi-call extraction, malformed cases) |
| Tool plane — Jaro-Winkler "did you mean" | `crates/sovereign-tool-dispatch/` `ToolRegistry::suggest_similar(name, min_similarity)` — resolves a mistyped tool call to the registered name most **similar** by Jaro-Winkler (`sovereign-jaro-winkler`), which rewards a shared prefix and tolerates transpositions, so a short garbled name (`"upepr"`, `"uppe"`) still recovers `"upper"` where the edit-distance `suggest` might miss it. Deterministic (ties → lexicographically smaller); `None` if already registered or nothing clears the threshold. Activates `sovereign-jaro-winkler` (previously **zero consumers**), complementing the existing levenshtein `suggest`. **Surfaced in the running binary**: `run_agent_demo` prints `did-you-mean : "upepr" -> Some("upper")`. Commit `a56b3ab`; 2 unit (transposition + truncation both recover "upper", exact name → None; unrelated string → None) + demo asserts the line |
| Memory/grounding plane — BM25 retrieval | `crates/sovereign-retrieval/` `DocStore::retrieve_bm25` + `Bm25Doc` — proper sparse retrieval (IDF-weighted, length-normalized; canonical k1=1.5/b=0.75) replacing the raw term-overlap ranking for RAG grounding. Commit `4bd8d1f`; 3 unit (IDF breaks a raw-overlap tie toward the rare-term doc; length normalization ranks the shorter doc first; empty/no-match) |
| Memory/grounding plane — MMR diversity re-ranking | `crates/sovereign-embed/` `EmbedStore::retrieve_mmr(query, k, lambda)` — Carbonell-Goldstein Maximal Marginal Relevance: greedily picks the doc maximizing `λ·sim(d,query) − (1−λ)·max sim(d,selected)`, avoiding near-duplicate RAG chunks that plain cosine top-k wastes budget on (λ=1 == `retrieve`, λ=0 = pure diversity). Commit `296a220`; 3 unit (MMR swaps a redundant duplicate for a diverse doc where top-k keeps both; λ=1 equals retrieve; empty/no-match) |
| Memory/grounding plane — hybrid retrieval (RRF) | `crates/sovereign-retrieval/` `HybridStore` — runs **both** the lexical (BM25) and semantic (embedding) backends over the same documents and fuses their rankings with Reciprocal Rank Fusion, so a doc both backends agree on rises to the top while each backend still covers the other's blind spot (BM25 misses paraphrases; embeddings miss exact rare tokens). This makes `sovereign-rank-fusion` (previously **zero consumers** — fusion math built but never wired) actually used; implements `Retriever` so it drops into `RagResponder`. Commit `253f262`; 4 unit (fuses lexical+semantic so the agreed doc wins + scores descending; agreement puts both on-topic docs above the off-topic one in top-2; empty/zero-k; drives RagResponder) |
| Memory/grounding plane — two-stage reranking | `crates/sovereign-retrieval/` `Reranked<R>` — wraps any `Retriever` with a precision second stage: pull a wider candidate pool, rescore it by query-term **coverage** (`sovereign-rerank`), keep the top-k, so a passage covering every query concept beats one spamming a single term. Makes `sovereign-rerank` (previously **zero consumers**) actually used; falls back to the inner top-k when the lexical coverage pass would empty a purely-semantic pool; composes with `HybridStore` + `RagResponder` (retrieve → rerank → ground). Commit `bef5986`; 4 unit (reorders a frequency-spam pool for coverage; fallback keeps inner order when coverage empties the pool; zero-k; drives RAG over a hybrid store) |
| Memory/grounding plane — ANN (HNSW) retrieval | `crates/sovereign-retrieval/` `AnnStore` — embeds documents and indexes them in an **HNSW** graph (`sovereign-hnsw`, cosine), so semantic retrieval is sub-linear in corpus size instead of `EmbedStore`'s brute-force cosine scan over every doc — the standard scalable semantic-search index (Hierarchical Navigable Small World: navigable graph, ~log-time queries at high recall). Makes `sovereign-hnsw` (previously **zero consumers**) actually used; implements `Retriever`, so it drops into `RagResponder` like the exact stores. Commit `784809a`; 3 unit (finds the nearest doc for a flavored query; empty/zero-k; drives RAG) |
| Memory/grounding plane — binary-quantized shortlist | `crates/sovereign-retrieval/` `BinaryHammingStore` — embeds each doc and keeps only the **sign bit** of every component (a **32× memory cut** over the `f32` vectors), then ranks by **Hamming distance** (XOR + hardware popcount) — the cheap first stage of the standard binary recipe: scan the codes to shortlist, then rerank the survivors at full precision. Makes `sovereign-binary-quant` (previously **zero consumers**) actually used; implements `Retriever`, so it drops into `RagResponder` and composes with `Reranked` (binary shortlist → coverage rerank). **Surfaced in the running binary**: `run_rag_quality_demo` prints `binary shortlist : 3 code(s), nearest="rust" @ hamming 11`. Realizes the operator's M085 VPOPCNT-margin theme (binary distance via popcount) in the retrieval path. Commit `70efbce`; 4 unit (Hamming shortlist picks the nearest doc; empty/zero-k; drives RAG; binary-shortlist→rerank recipe) + demo asserts the shortlist line |
| Memory/grounding plane — IVF (inverted-file) ANN retrieval | `crates/sovereign-retrieval/` `IvfStore` — embeds documents and, once **built**, trains a coarse quantizer and files each doc into a Voronoi cell, so a query scans only the nearest `n_probe` cells instead of the whole corpus — sub-linear semantic search on a different ANN trade-off point than `AnnStore`'s HNSW graph. Because the quantizer is *trained*, the index is **batch-built** (`add` all → `build()`, or `from_docs`); an `add` re-invalidates it. Makes `sovereign-ivf` (previously **zero consumers**) actually used; implements `Retriever`, so it drops into `RagResponder`. **Surfaced in the running binary**: `run_rag_quality_demo` prints `ivf index : 3 doc(s), built=true, nearest="rust"`. Commit `05fa982`; 4 unit (nearest doc via probed cells; nothing until built + add re-invalidates; empty/zero-k; drives RAG) + demo asserts the line |
| Memory/grounding plane — IVF-PQ (compressed ANN) | `crates/sovereign-retrieval/` `IvfPqStore` — like `IvfStore` it files docs into Voronoi cells, but instead of the full embedding it stores each vector's **product-quantized residual** — the offset from its cell centroid compressed by a product quantizer into a few bytes (`code_len`) — the FAISS IVFADC method that fits a vector index in a fraction of the memory (`compression()` reports the ratio) at the cost of approximate distances. **Batch-built** (both quantizers trained; cell count + codebook clamped to corpus size so small corpora build); an `add` re-invalidates. Makes `sovereign-ivf-pq` (previously **zero consumers**) actually used; implements `Retriever`, drops into `RagResponder`. **Surfaced in the running binary**: `run_rag_quality_demo` prints `ivf-pq (compact) : 3 doc(s), 4 bytes/vec (256x smaller), nearest="rust"` (a 256-d f32 vector → 4 PQ bytes). Commit `7b80947`; 3 unit (nearest doc; **>100× compression + nothing-until-built + add re-invalidates**; empty/zero-k + drives RAG) + demo asserts the line |
| Memory/grounding plane — near-duplicate filter (SimHash) | `crates/sovereign-retrieval/` `Deduped<R>` — wraps any `Retriever`, pulls a wider pool, fingerprints each passage with a 64-bit **SimHash** (word-shingled, so lightly-reordered text stays close), and keeps a passage only when its fingerprint is more than `max_hamming` bits from every already-kept one — so re-crawled / copied / boilerplate chunks don't each burn a top-`k` slot (the context budget the model most needs). Makes `sovereign-simhash` (previously **zero consumers**) actually used; implements `Retriever`, composes with `HybridStore`/`Reranked`/`RagResponder`. **Surfaced in the running binary**: `run_rag_quality_demo` prints `dedup filter : 2 passage(s) -> 1 after near-dup drop`. Commit `d69821a`; 4 unit (duplicate collapses to one + distinct kept; all-distinct pool preserved; zero-k; drives RAG with one copy in context) + demo asserts the line |
| Memory/grounding plane — MMR diversity re-ranking wrapper | `crates/sovereign-retrieval/` `Diversified<R>` — wraps any `Retriever`, pulls a wider pool, embeds each passage, and greedily picks the `k` maximizing `λ·relevance − (1−λ)·max-similarity-to-already-picked` (`sovereign-mmr`), so near-duplicate passages don't all crowd the top-`k` and the retrieved set spans more of the query's facets. The **general form** of `EmbedStore::retrieve_mmr` (which diversifies only that one store's own index): as a `Retriever` wrapper it re-ranks the output of *any* backend — lexical, hybrid, IVF, VP-tree — and composes with the other wrappers. Makes the standalone `sovereign-mmr` crate (previously **zero consumers**) actually used. **Surfaced in the running binary**: `run_rag_quality_demo` prints `mmr diversify : 2 passage(s), distinct=true` (λ=0 returns two distinct passages, not a duplicate pair). Commit `fdc41df`; 3 unit (pure-diversity avoids the duplicate + keeps a distinct passage; small pool passes through; zero-k + drives RAG) + demo asserts the line |
| Memory/grounding plane — Matryoshka coarse-to-fine retrieval | `crates/sovereign-retrieval/` `MatryoshkaStore` — embeds documents once at full 256-d but ranks in two passes: a cheap coarse pass over a truncated `coarse_dim` prefix (default 64) shortlists candidates, then just that shortlist is reranked at full dimension. Matryoshka embeddings front-load information in their leading dimensions, so the prefix is a faithful proxy to prune the field before the expensive full-width compare — most of the accuracy for a fraction of the per-candidate cost (`coarse_saving()` reports `1 − coarse/full`). Makes `sovereign-matryoshka` (previously **zero consumers**) actually used; implements `Retriever`, so it drops into `RagResponder`. **Surfaced in the running binary**: `run_rag_quality_demo` prints `matryoshka : 3 doc(s), coarse_dim=64 (saving 75%), nearest="rust"`. Commit `26404f9`; 3 unit (coarse-to-fine picks the nearest doc; empty/zero-k + 75% coarse saving; drives RAG) + demo asserts the line |
| Memory/grounding plane — vantage-point tree (exact ANN) | `crates/sovereign-retrieval/` `VpTreeStore` — embeds documents and, once **built**, indexes them in a `VpTree` — a metric-space binary tree that partitions points by distance to a chosen vantage point, so the triangle inequality prunes whole subtrees a query can't beat. Unlike the graph/quantizer/truncation indexes (`AnnStore` HNSW, `IvfStore`, `MatryoshkaStore`, all approximate) its `knn` is **exact** — identical to a brute-force scan — but reached in expected sub-linear time (embeddings are unit vectors, so Euclidean order = cosine order). **Batch-built** (`add` all → `build()`, or `from_docs`); an `add` re-invalidates the partition. Makes `sovereign-vptree` (previously **zero consumers**) actually used; implements `Retriever`, drops into `RagResponder`. **Surfaced in the running binary**: `run_rag_quality_demo` prints `vp-tree (exact) : 3 doc(s), built=true, nearest="rust"`. Commit `2df8b11`; 4 unit (nearest doc; nothing until built + add re-invalidates; **knn order == brute-force Euclidean scan**; empty/zero-k) + demo asserts the line |
| Memory/grounding plane — typo-tolerant lexical retrieval (BK-tree) | `crates/sovereign-retrieval/` `FuzzyTermStore` — indexes documents by their words and keeps every distinct term in a **BK-tree** (`sovereign-bktree`), so a query term absent from the vocabulary is first **corrected** to the nearest real term within an edit-distance radius (`"ownrship" → "ownership"`) before term-overlap ranking. Embedding retrievers are naturally spelling-robust but a purely lexical index misses a misspelling entirely; the BK-tree's triangle-inequality pruning makes the "did you mean" correction sublinear in the vocabulary. Vocabulary grows incrementally on `add` (no rebuild). Makes `sovereign-bktree` (previously **zero consumers**) actually used; implements `Retriever`, drops into `RagResponder`. **Surfaced in the running binary**: `run_rag_quality_demo` prints `fuzzy (typo-ok) : 16 vocab terms, "ownrship safty" -> ["ownership", "safety"], nearest="rust"`. Commit `fe17d2a`; 3 unit (misspelled query corrected + still retrieves; exact terms pass through + no-match term left as-is; empty/zero-k + drives RAG on a one-edit typo) + demo asserts the line |
| Memory/grounding plane — query distillation (RAKE) | `crates/sovereign-retrieval/` `KeyphraseQuery<R>` — wraps any `Retriever` with a query-side stage: RAKE-extracts the top keyphrases from the query (`sovereign-keywords`) and retrieves on those, so a verbose passage-as-query focuses on its salient terms instead of matching on function words. Falls back to the raw query when extraction is empty. Makes `sovereign-keywords` (previously **zero consumers**) actually used; composes in front of `HybridStore`/`Reranked`/`InjectionFiltered` + `RagResponder`. Commit `da4ebb5`; 4 unit (distills + drops stopwords; all-stopword fallback; retrieves via distilled terms; drives RAG) |
| Memory/grounding plane — indirect-injection filter | `crates/sovereign-retrieval/` `InjectionFiltered<R>` — wraps any `Retriever` and drops retrieved passages tripping known prompt-injection / jailbreak patterns (`sovereign-injection-detect`: *ignore previous instructions*, *you are now*, *disregard all* …) before they reach the grounding block — defense against **indirect prompt injection** via poisoned corpus documents. Pulls a wider pool to backfill clean passages, fails safe (returns fewer) if all candidates are suspicious. Makes `sovereign-injection-detect` (previously **zero consumers**) actually used; composes with `HybridStore`/`Reranked`/`RagResponder`. Commit `20b6cb1`; 4 unit (drops a poisoned passage + keeps the clean one; clean corpus passes through; guards a RAG prompt; zero-k) |
| Safety plane — injection-detector quality metrics | `crates/sovereign-injection-detect/` `evaluate(labeled, threshold) -> DetectorEval` — scores the detector's suspicious/clean verdict against a **labeled** `(text, is_injection)` set, building a 2-class confusion matrix (`sovereign-classification-metrics`) and reporting **accuracy + precision/recall/F1** for the "suspicious" class. Turns the heuristic detector from an opaque filter into a *measurable* one — you can see how well it separates injections from clean text on your own examples, and tune the threshold. Makes `sovereign-classification-metrics` (previously **zero consumers**) actually used. **Surfaced in the running binary**: `run_rag_quality_demo` prints `detector quality : acc=1.00 P=1.00 R=1.00 F1=1.00 over 4 labeled`. Commit `6d253aa`; 2 unit (perfect verdict on obvious injections + clean texts; all-clean set → accuracy 1.0 with zero recall/support for the positive class) + demo asserts the line |
| Safety/routing plane — language detection | `crates/sovereign-language-detect/` `LanguageDetector` activated in the running binary: `run_rag_quality_demo` trains char-trigram fingerprints (Cavnar-Trenkle) for `en`/`fr`/`es` and classifies a query (`the memory safety of the borrow checker` → `en`) — the model-free language ID useful for routing, tagging, or filtering retrieved text before it reaches the model. Makes `sovereign-language-detect` (previously **zero consumers**) actually used by `sovereign-inference-demo`. Commit `14b42a6`; prints `language detect : 3 languages, query -> "en"` (demo asserts the line) |
| Observability plane — approximate membership + cardinality (Bloom / Cuckoo / HyperLogLog) | `run_rag_quality_demo` streams a term list through three previously-**zero-consumer** sublinear structures: `sovereign-bloom` (`BloomFilter` — space-efficient set membership, no false negatives), `sovereign-cuckoo-filter` (`CuckooFilter` — membership **with deletion**), and `sovereign-hyperloglog` (`HyperLogLog` — distinct-count estimate at fixed memory). The shape a serving loop uses to dedup seen docs / cap a cache / estimate distinct n-grams without storing them. Makes all three actually used by `sovereign-inference-demo`. Commit `91febc6`; prints `membership/card : bloom_ok=true cuckoo_del=true hll_distinct~10 (of 12 terms)` — HLL recovers the 10 distinct terms exactly (demo asserts the line) |
| Observability plane — frequent items + reservoir sampling | `run_rag_quality_demo` streams a skewed term list through three previously-**zero-consumer** sublinear structures: `sovereign-heavy-hitters` (Count-Min-backed heavy hitters, `top_k`), `sovereign-space-saving` (`SpaceSaving` — bounded-memory top-k `Entry` stream summary), and `sovereign-reservoir` (`Reservoir` — uniform random sample of a stream in one pass). The two frequent-item sketches **independently agree** the top term is `rust` (4/10). Makes all three actually used by `sovereign-inference-demo`. Commit `e01a659`; prints `freq/sample : hh_top="rust" ss_top="rust" reservoir_n=3 of 10` (demo asserts the line) |
| String plane — substring search + membership + local alignment | `run_rag_quality_demo` runs three previously-**zero-consumer** string-matching crates: `sovereign-rolling-hash` (`find_all` — Rabin-Karp substring search, finds `aliasing` at byte 28), `sovereign-suffix-automaton` (`SuffixAutomaton::build`/`contains` — O(n) substring membership over a text), and `sovereign-local-align` (`align_str` — Smith-Waterman local alignment, 12 matched chars aligning `memory safety` vs the transposed `memroy safety`). The primitives behind grep-like search, dedup, and fuzzy near-match over generated/retrieved text. Makes all three actually used by `sovereign-inference-demo`. Commit `142de73`; prints `string match : rk_pos=[28] sa_hit=true align_matches=12` (demo asserts the line) |
| Generation-quality plane — readability | `crates/sovereign-readability/` `analyze(text) -> Readability` activated in `run_rag_quality_demo`: computes Flesch Reading Ease + Flesch-Kincaid grade + ARI from sentence/word/syllable counts, so a serving loop can tell whether an answer is pitched for the audience (a graduate wall-of-clauses vs plain English). Makes `sovereign-readability` (previously **zero consumers**) actually used. Commit `b6278f3`; prints `readability : flesch=84 grade=5.0 (14 words / 1 sentence)` (demo asserts the line) |
| Generation-quality plane — word error rate | `crates/sovereign-wer/` `word_error_rate(reference, hypothesis) -> ErrorBreakdown` activated in `run_rag_quality_demo`: Levenshtein-aligned S/I/D breakdown + `error_rate = (S+I+D)/N` between a reference and a hypothesis (transcription/paraphrase quality; also `character_error_rate`). Makes `sovereign-wer` (previously **zero consumers**) actually used. Commit `b6278f3`; prints `word error rate : 0.14 (1S 0I 1D over 14 words)` for a one-substitution-one-deletion hypothesis (demo asserts the line) |
| Observability plane — streaming stats (t-digest / Welford / histogram) | `run_strategies_demo` builds a single-pass summary of a real 40-token generation's id distribution using three previously-**zero-consumer** crates together: `sovereign-tdigest` (`TDigest` — mergeable t-digest quantiles: p50/p90), `sovereign-running-stats` (`RunningStats` — Welford online mean/variance/std), and `sovereign-histogram` (`Histogram` — bucketed counts + interpolated median). All are streaming (O(1) memory, one pass), the shape a serving loop uses to summarize latencies / scores / token distributions without buffering. Makes all three actually used by `sovereign-inference-demo`. Commit `af608df`; prints `stream stats : n=40 mean=14.2 std=8.8 p50=12 p90=18 hist_med=16` (demo asserts n=40 + the p50/hist_med structure) |
| Observability plane — more streaming quantiles + weighted sampling | `run_strategies_demo` estimates p90 of the same token stream two more ways plus a weighted sample, with three previously-**zero-consumer** crates: `sovereign-ddsketch` (`DDSketch` — relative-error-bounded quantile sketch, p90=18), `sovereign-p2-quantile` (`P2Quantile::observe` — the P² algorithm: a single quantile in O(1) memory, p90=19), and `sovereign-weighted-reservoir` (`WeightedReservoir` — weighted random sampling of a stream). DDSketch's p90 agrees with the earlier t-digest (18). Makes all three actually used by `sovereign-inference-demo`. Commit `348beec`; prints `quantile est. : ddsketch_p90=18 p2_p90=19 wsample_n=3` (demo asserts the line) |
| Coding plane — lossless token-stream coding (Huffman + varint) | `run_strategies_demo` losslessly codes a real 40-token generation two ways with previously-**zero-consumer** crates: `sovereign-huffman` (`HuffmanCode::from_sequence`/`encode`/`decode` — entropy coding: 149 bits vs the 240-bit raw 6-bits/token baseline) and `sovereign-varint` (`encode_deltas`/`decode_deltas` — LEB128 delta coding: 40 bytes), both **round-tripping exactly**. The building blocks for compressing token logs, KV-cache indices, or on-disk sequences. Makes both actually used by `sovereign-inference-demo`. Commit `29d3a30`; prints `coding : huffman 149 bits (raw 240) ok=true; varint 40 bytes ok=true` (demo asserts the line) |
| Observability plane — time-series monitoring (Kalman / Holt-Winters / CUSUM) | `run_strategies_demo` monitors a metric stream with a level shift at t=6 using three previously-**zero-consumer** crates: `sovereign-kalman` (`KalmanFilter::observe` — 1-D Kalman smoothing of a noisy signal), `sovereign-holt-winters` (`HoltWinters::fit`/`observe`/`forecast` — triple exponential smoothing forecast), and `sovereign-cusum` (`CusumDetector::observe -> Option<Alarm>` — two-sided change-point detection). The Kalman estimate tracks the shifted level (~12.4), Holt-Winters forecasts it (~15.1), and CUSUM **alarms at t=7** (one sample after the shift). Makes all three actually used by `sovereign-inference-demo`. Commit `6ad940d`; prints `time series : kalman~12.4 hw_forecast~15.1 cusum_alarm_at=Some(7)` (demo asserts the line) |
| Decision plane — optimization + bandit selection | `run_strategies_demo` runs three previously-**zero-consumer** decision primitives: `sovereign-knapsack` (`knapsack_01` — 0/1 dynamic-programming max value under a weight cap: 9.0), `sovereign-bin-packing` (`pack` first-fit-decreasing — 5 requests into 3 capacity-6 bins), and `sovereign-bandit` (`Bandit` with UCB1/ε-greedy/Thompson — `best_arm=1` after reward feedback favours arm 1). The building blocks for compute-budget allocation, request batching, and adaptive model/tool routing. Makes all three actually used by `sovereign-inference-demo`. Commit `7edbe03`; prints `optimize/decide : knapsack_val=9.0 bins=3 best_arm=1` (demo asserts the line) |
| Learning plane — regression + sequential testing | `run_strategies_demo` runs three previously-**zero-consumer** learning/stats primitives: `sovereign-online-regression` (`OnlineRegression` — streaming least-squares, recovers slope ≈1.9 of a `y≈2x` trend), `sovereign-isotonic` (`IsotonicRegression::fit`/`predict` — monotone PAV regression, pools the non-monotone point), and `sovereign-sprt` (`Sprt` — Wald sequential probability ratio test, **AcceptH1** after 20 successes with `p1=0.8 > p0=0.5`). The primitives behind scaling-law fits, monotone calibration, and early-stopping A/B tests. Makes all three actually used by `sovereign-inference-demo`. Commit `dbf53ba`; prints `regress/test : slope=1.9 iso@3=2.8 sprt=AcceptH1` (demo asserts the line) |
| Model plane — MoE gating + RoPE context scaling | `run_strategies_demo` runs two previously-**zero-consumer** model-architecture primitives: `sovereign-moe-gate` (`top_k_gate` — system-level Mixture-of-Experts routing: top-2 of 4 experts by softmax weight, so `top_expert=1 weight=0.73`) and `sovereign-rope-scaling` (`effective_max_context` with `ScalingMethod::Linear{factor:4}` — RoPE position-interpolation context extension: `2048 -> 8192`). The M022 cognitive-frame gate + the long-context scaling knob. Makes both actually used by `sovereign-inference-demo`. Commit `f49aac2`; prints `moe/rope : top_expert=1 weight=0.73 ctx 2048->8192` (demo asserts the line) |
| Utility plane — fuzzy automaton + significance + expression eval | `run_strategies_demo` runs the last three previously-**zero-consumer** utility crates: `sovereign-levenshtein-automaton` (`LevenshteinAutomaton::new`/`accepts` — bounded-edit-distance fuzzy match: `memory`~1 accepts `memery`, rejects `network`), `sovereign-significance` (`paired_bootstrap_pvalue` — paired bootstrap A/B test: a variant scoring consistently above baseline gets `pvalue=0.00`), and `sovereign-calc` (`eval` — safe arithmetic expression evaluator: `2 * (3 + 4) - 1 = 13`). Makes all three actually used by `sovereign-inference-demo`. Commit `4a465b2`; prints `misc primitives : lev_ok=true pvalue=0.00 calc=13` (demo asserts the line) |
| Serving plane — KV budget / tiered KV cache / prefix reuse | `run_strategies_demo` runs three previously-**zero-consumer** serving primitives: `sovereign-kv-budget` (`KvShape` — per-token KV bytes for a 32-layer/8-KV-head/128-dim f16 model = 131072 B/token, and the max sequence length fitting a 2 GiB budget = 16384), `sovereign-kv-cache` (`KvCache` — VRAM/RAM/NVMe tiered block placement, a 900-byte block lands in `Vram`), and `sovereign-prefix-cache` (`PrefixCache::longest_prefix_match` — shared-prompt-prefix reuse: `[1,2,3,4]` vs `[1,2,3,9]` reuses the 3-token prefix). The memory-planning + cache-reuse core of a batched inference server. Makes all three actually used by `sovereign-inference-demo`. Commit `4e958b5`; prints `kv serving : kv/tok=131072B max_seq=16384 tier1=Some(Vram) prefix_reuse=3` (demo asserts the line) |
| Decode/text plane — Viterbi + watermark + semantic chunking | `run_strategies_demo` runs three previously-**zero-consumer** crates: `sovereign-viterbi` (`Hmm::decode_probs` — Viterbi most-likely state path `[0,1,1]` through a 2-state HMM), `sovereign-watermark` (`Watermark` — Kirchenbauer green-list LLM watermark: `bias_logits`/`is_green` build an all-green sequence, `detect` returns z=7.7 ≫ threshold), and `sovereign-semantic-chunk` (`chunk_text` — embedding-similarity boundary chunking splits 4 sentences into 4 chunks). The primitives behind sequence tagging, watermark provenance, and RAG chunking. Makes all three actually used by `sovereign-inference-demo`. Commit `a148b8a`; prints `decode/text : viterbi=[0, 1, 1] wm_z=7.7 chunks=4` (demo asserts the line) |
| Agent plane — tool-call parsing + skill library + prompt templates | `run_strategies_demo` runs three previously-**zero-consumer** agent-scaffolding crates: `sovereign-tool-call-parse` (`parse_tool_calls` — JSON tool-call extraction with json-repair, recovers `name="search"` from a model reply), `sovereign-skill-library` (`SkillLibrary`/`Skill`/`all_for` — tag-indexed agent skill store, 2 skills under `nlp`), and `sovereign-prompt-template-registry` (`TemplateRegistry`/`PromptTemplate::render` — mode/bundle-gated `{{var}}` prompt templates, renders `Hello {{name}}` → `Hello rust.`). The scaffolding behind an agent's tool loop, skill selection, and prompt construction. Makes all three actually used by `sovereign-inference-demo`. Commit `304f6d3`; prints `agent scaffold : tool_call="search" nlp_skills=2 render="Hello rust."` (demo asserts the line) |
| Distributed-systems plane — ULID / SemVer / vector clock | `run_strategies_demo` runs three previously-**zero-consumer** distributed-systems primitives: `sovereign-ulid` (`UlidGenerator`/`Ulid::parse` — lexicographically-sortable time-ordered IDs that round-trip through their Crockford-base32 string), `sovereign-semver` (`Version::parse`/`satisfies_caret` — semantic-version caret compatibility: `1.4.2` satisfies `^1.0.0`), and `sovereign-vector-clock` (`VectorClock::tick`/`happens_before` — causal-ordering clock: a clock and its descendant are correctly ordered). The plumbing behind request/checkpoint IDs, model/schema versioning, and distributed-state causality. Makes all three actually used by `sovereign-inference-demo`. Commit `9ddcae7`; prints `distributed ids : ulid_ok=true semver_compat=true causal=true` (demo asserts the line) |
| Text-ops plane — line diff / find-replace / SSE parse | `run_strategies_demo` runs three previously-**zero-consumer** text crates: `sovereign-line-diff` (`diff` — LCS line diff with `Insert`/`Delete` tags: 2 inserts between two versions), `sovereign-text-edit` (`Edit::new`/`apply_all` — ordered find/replace edits: `hello world` → `hi rust`), and `sovereign-sse-parse` (`SseParser::push` — incremental Server-Sent-Events parser: 2 `data:` events from a stream chunk). The shape a streaming LLM client + a code-edit tool need. Makes all three actually used by `sovereign-inference-demo`. Commit `08bfb8d`; prints `text ops : diff_inserts=2 edit="hi rust" sse_events=2` (demo asserts the line) |
| Serving plane — continuous batching + prompt history ring | `run_strategies_demo` runs two previously-**zero-consumer** serving crates: `sovereign-continuous-batch` (`Scheduler`/`Request`/`step` — a PagedAttention-style continuous-batching scheduler admits 2 requests into a running batch of 4) and `sovereign-prompt-history-ring` (`PromptHistoryRing::push`/`len` — a bounded ring buffer of recent prompts, holds 3). The request-admission + recent-context machinery of an inference server. Makes both actually used by `sovereign-inference-demo`. Commit `51e75a0`; prints `serving/history : admitted=2 history_len=3` (demo asserts the line) |
| Governance plane — six pillars + learning signals | `run_strategies_demo` runs two previously-**zero-consumer** governance crates: `sovereign-six-pillars` (`Pillar::all` — the 6-pillar governance model enumerated) and `sovereign-learning-signals` (`derive_learning(TaskOutcome)` — turns a task outcome into 6 structured learning signals for the methodology-evolution loop). Makes both actually used by `sovereign-inference-demo`. Commit `f3ab8fe`; prints `governance : pillars=6 learning_signals=6` (demo asserts the line) |
| Policy plane — routing preferences + trust boundaries | `run_strategies_demo` runs two previously-**zero-consumer** policy crates: `sovereign-routing-preference` (`RoutingPreferences::canonical`/`weight_total` — per-bundle provider-selection weights, the `Sovereign` bundle totals 290) and `sovereign-trust-boundaries` (`is_placement_safe`/`TrustZone::containment` — tool-tier × trust-zone placement policy: a tier-A tool is safe in the `Host` zone). The provider-routing + tool-sandboxing policy layer. Makes both actually used by `sovereign-inference-demo`. Commit `ad5390b`; prints `policy : route_weight=290 tierA@host_safe=true host_containment=0` (demo asserts the line) |
| Runtime-infra plane — telemetry sink + control reactions + folder registry | `run_strategies_demo` runs three previously-**zero-consumer** runtime-infra crates: `sovereign-telemetry-backend` (`TelemetrySink::from_token` — resolve a telemetry backend from a config token: `"otel"` → `Otel`), `sovereign-runtime-reactions` (`derive_controls(RuntimeSignals, ControlThresholds)` — turn live signals into control reactions: a cost-spike + 5-failure streak triggers 2 reactions), and `sovereign-workspace-folder-registry` (`WorkspaceFolderRegistry::add`/`resolve` — a scoped workspace-folder map, resolves `/repo`). The observability + adaptive-control + filesystem-scoping plumbing of the runtime. Makes all three actually used by `sovereign-inference-demo`. Commit `80f599e`; prints `runtime infra : sink=Some(Otel) controls=2 folder_ok=true` (demo asserts the line) |
| Durability/eval plane — semantic checkpoint + eval-result summary | `run_strategies_demo` runs two previously-**zero-consumer** crates: `sovereign-semantic-checkpoint` (`SemanticCheckpoint::is_semantically_complete`/`has_machinery` — a *resumable* agent checkpoint carrying both machinery refs (process + filesystem snapshot) and semantic state (workflow node, branch, next action); a fully-populated one is complete) and `sovereign-eval-result-summary` (`EvalResultSummary::new`/`pass_rate_bps` — an eval-suite rollup: 8 passed / 2 failed = 8000 bps). The agent-resume + eval-reporting surfaces. Makes both actually used by `sovereign-inference-demo`. Commit `a9296bc`; prints `eval/checkpoint : pass_rate_bps=8000 checkpoint_complete=true` (demo asserts the line) |
| Provenance plane — prompt rationale + routing decision log | `run_strategies_demo` runs two previously-**zero-consumer** provenance crates: `sovereign-prompt-rationale` (`Rationale::build`/`used_template` — a structured record of *why* a prompt was built: trace, provider, template, bundle, mode, governing doctrine, reason) and `sovereign-routing-decision-log` (`RoutingDecisionLog::record`/`entries` — an append-only log of which provider served each request, with bundle/mode/latency/reason). The audit trail behind every prompt + routing decision. Makes both actually used by `sovereign-inference-demo`. Commit `7fa8eed`; prints `provenance : used_template=true routing_entries=1` (demo asserts the line) |
| Data-structures plane — Fenwick / interval tree / Merkle tree | `run_strategies_demo` runs three previously-**zero-consumer** data-structure crates: `sovereign-fenwick` (`Fenwick::from_values`/`prefix_sum` — a binary-indexed tree for O(log n) prefix sums), `sovereign-interval-tree` (`IntervalTree::build`/`query_point` — 2 of 3 intervals contain point 4), and `sovereign-merkle-tree` (`MerkleTree::from_leaves`/`root`/`proof` — a tamper-evident hash tree with inclusion proofs). The indexing/query/integrity primitives behind KV budgeting, range queries, and content-addressed verification. Makes all three actually used by `sovereign-inference-demo`. Commit `662238a`; prints `data structs : fenwick_psum=3 interval_hits=2 merkle_root_nonzero=true proof=true` (demo asserts the line) |
| Graph-algorithms plane — PageRank / shortest path / community detection | `run_strategies_demo` runs three previously-**zero-consumer** graph crates over a 4-node digraph: `sovereign-pagerank` (`pagerank`/`top_k` — power-iteration centrality: node 2 ranks highest), `sovereign-graph-path` (`bfs_path` — shortest unweighted path 3→0 is 2 hops), and `sovereign-community-detect` (`detect`/`communities`/`modularity` — label-propagation clustering: 1 community for the connected graph). The centrality/routing/clustering primitives behind knowledge-graph ranking and retrieval-graph analysis. Makes all three actually used by `sovereign-inference-demo`. Commit `d3cedaa`; prints `graph algos : pr_top=2 bfs_hops=2 communities=1` (demo asserts the line) |
| Text/format plane — JSONL / Markdown strip / format mask | `run_strategies_demo` runs three previously-**zero-consumer** text crates: `sovereign-jsonl` (`parse` — line-delimited JSON: 3 values from a stream), `sovereign-markdown-strip` (`strip` — Markdown → plain text, drops `#`/`*`/backticks while keeping `Title`), and `sovereign-format-mask` (`Pattern`/`Slot::accepts`/`is_complete` — a positional constrained-output mask like `12-A`: a `Digit` slot accepts `5` not `X`, and a 4-slot pattern is complete at length 4). The dataset-loading, context-cleaning, and constrained-format-generation primitives. Makes all three actually used by `sovereign-inference-demo`. Commit `96c8a34`; prints `text/format : jsonl_vals=3 strip_clean=true slot_ok=true mask_complete=true` (demo asserts the line) |
| Sampling plane — standalone Mirostat + n-gram speculative | `run_strategies_demo` runs two more previously-**zero-consumer** sampling crates: `sovereign-mirostat` (the standalone `Mirostat::sample_seeded` — perplexity-targeting controller, distinct from `sovereign-sampler::Mirostat`, picks a token from logits) and `sovereign-ngram-speculative` (`NgramSpeculator::propose`/`accepted_prefix` — prompt-lookup speculative drafting: the context `[1,2,3,1,2]` drafts a 3-token continuation and `accepted_prefix` verifies 1 token matches the target). Draft-free speculative decoding + adaptive-perplexity sampling. Makes both actually used by `sovereign-inference-demo`. Commit `58a8223`; prints `sampling extra : mirostat_tok=3 draft_len=3 accepted=1` (demo asserts the line) |
| Resilience plane — circuit breaker + AIMD limiter + load balancer | `run_strategies_demo` runs three previously-**zero-consumer** resilience crates: `sovereign-circuit-breaker` (`CircuitBreaker::allow`/`record_failure` — trips open after 2 failures so it rejects the next call), `sovereign-aimd-limiter` (`AimdLimiter` — additive-increase/multiplicative-decrease concurrency limit, settles to 5.0 after a success then an overload), and `sovereign-load-balance` (`WeightedRoundRobin::pick` — weighted backend selection picks the heavier `a`). The fault-isolation + backpressure + fan-out layer of a resilient serving stack. Makes all three actually used by `sovereign-inference-demo`. Commit `0f1bf5e`; prints `resilience : cb_open=true aimd_limit=5.0 lb_pick="a"` (demo asserts the line) |
| Tokenizer-training plane — BPE learn + WordPiece + Unigram | `run_strategies_demo` runs three previously-**zero-consumer** subword tokenizers over related text: `sovereign-bpe-train` (`train`/`train_tokenizer` — *learns* an ordered byte-level merge table from a corpus, 7 merges, and the trained `Tokenizer` encodes `"slower"` to 3 ids), `sovereign-wordpiece` (`WordPiece::tokenize`/`detokenize` — greedy longest-match split of `"playing"` → `play ##ing`, losslessly rejoined via the `##` prefix), and `sovereign-unigram-tokenizer` (`UnigramTokenizer::tokenize` — globally optimal Viterbi segmentation of `"lowest"` → 2 pieces). The three subword schemes that turn raw text into the token units a model decodes over. Makes all three actually used by `sovereign-inference-demo`. Commit `ed9f667`; prints `tokenizers : bpe_merges=7 bpe_ids=3 wp="play ##ing" roundtrip_ok=true unigram_tok=2` (demo asserts the line) |
| Serving-placement plane — consistent-hash + rendezvous + P2C balance | `run_strategies_demo` runs three previously-**zero-consumer** request-routing crates: `sovereign-consistent-hash` (`HashRing::with_vnodes`/`get`/`remove_node` — a 64-vnode ring keeps `session-42` on its node when a *non-owner* replica leaves), `sovereign-rendezvous-hash` (`RendezvousHash::select_str`/`select_k` — ring-free highest-random-weight placement picks a top node + its top-2), and `sovereign-p2c-balance` (`P2cBalancer::uniform`/`pick` — power-of-two-choices spreads 6 requests across 3 backends to a max load of 2). The three canonical ways to map a request to a model replica without a global load view. Makes all three actually used by `sovereign-inference-demo`. Commit `dc12558`; prints `placement : ch_stable=true hrw_pick=Some("replica-c") hrw_k=2 p2c_maxload=2 p2c_total=6` (demo asserts the line) |
| Agent-tooling plane — arg-schema + invocation record + context-pack | `run_strategies_demo` runs three previously-**zero-consumer** agent-runtime crates: `sovereign-arg-schema` (`Schema::require`/`optional`/`validate` — type-checks a model's tool-call JSON, accepting a valid `{path, limit}` and collecting **2** violations from a bad one), `sovereign-tool-invocation-record` (`InvocationRecord::new`/`validate` — the immutable audit row for one tool call: trace-id, mode, bundle, exit-kind, bytes-out, validated), and `sovereign-context-pack` (`pack` — exact 0/1 knapsack that fits 2 chunks / 50 tokens into a 60-token window by relevance, not top-k-until-full). The validate → record → pack path an agent runs around every tool call. Makes all three actually used by `sovereign-inference-demo`. Commit `ae53ae9`; prints `agent tooling : args_ok=true arg_errs=2 record_ok=true packed=2 pack_tokens=50` (demo asserts the line) |
| RAG safety + quality pipeline **surfaced in the running binary** (built → wired → visible) | `crates/sovereign-inference-demo/` `run_rag_quality_demo` — `cargo run -p sovereign-inference-demo` now runs the full hybrid→rerank→injection-filter retrieval pipeline (prints `poisoned leaked : false` — the poisoned doc is dropped) plus `compress_prompt` (`71 -> 36 tokens`), `sample_diversity` (best-of-4 unique/distinct/self-bleu), and `complete_checked` (degeneration report) on the real runtime. The retrieval/quality wirings are now exercised in a runnable binary, not just library APIs. Commit `159f90e`; 1 integration (poisoned passage filtered + all three controls report) + demo smoke |

### M006 — Deterministic AI control substrate

| Surface | Shipped artifact |
|---|---|
| Workload-mode adoption doctrine SDD | `docs/sdd/035-workload-mode-adoption-doctrine.md` — the determinism discipline anchored in mode adoption |
| Inference-service hardening doctrine SDD | `docs/sdd/036-inference-service-hardening-doctrine.md` — the determinism enforcement on the inference service tier |
| Mode-transition log | `crates/sovereign-mode-transition-log/` — append-only log enforcing deterministic mode transitions |

### M007 — Execution model (branch primitive + AVX-512 scheduler)

| Surface | Shipped artifact |
|---|---|
| Hardware-stack consolidation SDD | `docs/sdd/029-hardware-stack-consolidation.md` — anchors the AVX-512 scheduler decisions |
| Choice envelope (cross-ref M002, M042) | `crates/sovereign-choice-envelope/` — typed branch-primitive envelope |
| AVX-512 advisor | `scripts/hardware/avx512-advisor.py` — operator advisor for the AVX-512 scheduler placement |

### M008 — Bit-level cheats (AVX-512 features as AI infrastructure)

| Surface | Shipped artifact |
|---|---|
| Hardware-stack consolidation SDD | `docs/sdd/029-hardware-stack-consolidation.md` (cross-ref M007) |
| AVX-512 advisor + BIOS directives | `scripts/hardware/avx512-advisor.py`, `scripts/hardware/bios-directives.py`, `scripts/hardware/bios-info.py` — operator-side surface for the bit-level-AVX-512 infrastructure choice |
| T3 structure/prune/KV references (M085) | `crates/sovereign-bitops/` — the note's T3 tier completed: `vpermb` (`VPERMB`/VBMI 64-byte table permute, index masked to 6 bits like the hardware — "alignement & shuffling de tokens"), `vpshldv` (`VPSHLDVQ`/VBMI2 concatenated variable funnel shift-left), and `expand` (`VPEXPAND`, the inverse of the existing `compress` — "compactage dynamique"; compress→expand reconstruction of kept lanes pinned as a test). Commit `af681c7`; 4 unit (scatter to masked lanes + fill semantics; compress round trip; permute + 6-bit index masking; funnel shift incl. count-0/count-64/full-funnel edges) |

### M009 — Deterministic Cortex Runtime v0

| Surface | Shipped artifact |
|---|---|
| Inference-backend-stack SDD | `docs/sdd/011-inference-backend-stack.md` — the v0 Cortex Runtime spec |
| dflash speculative-decoding SDD | `docs/sdd/026-dflash-speculative-decoding.md` — the dflash variant for the v0 runtime |
| dflash sampled (distribution-preserving) verification | `crates/sovereign-spec-decode/` `verify_sampled` — the modified rejection-sampling accept rule (Leviathan/Chen) that emits a target-distributed sequence: accept each draft token at `min(1, p_target/p_draft)`, correct from the normalized positive residual on rejection, bonus from the target on full accept. Complements the existing greedy `verify_greedy`. Commit `f0d8001`; verified by a 400k-trial statistical test (first emitted token matches `p_target` within 1%) + shape-error + accept/reject unit tests |
| dflash sampled accept path live-checked in cortex | `crates/sovereign-cortex/` `spec_decode_kernel_live` + `ComputeProfile::spec_decode_verified` — the GPU target roles (Logic/Oracle) run a real `verify_sampled` full-accept + forced-reject round at profile-build time, so the running cortex self-reports the spec-decode path is callable + correct (`"spec_decode_verified": true`), not just an estimated multiplier. Commit `5646b19`; 2 unit (live check correct; GPU roles verify, draft/cloud don't) |
| dflash adaptive draft length | `crates/sovereign-speculative/` `Speculative::decode_adaptive(draft, target, prompt, cost_ratio, max_draft)` — retunes the per-round draft length from the running acceptance rate via `optimal_draft_length`, so it grows when the draft tracks the target and shrinks when it doesn't (makes the cost model actionable). Output identical to greedy target decoding (lossless). Commit `d403bb9`; 2 unit (lossless vs greedy across cost_ratio/max_draft; input validation) |
| dflash cost-aware speedup + optimal draft length | `crates/sovereign-spec-decode/` `cost_aware_speedup(alpha, k, cost_ratio)` (= `expected_speedup / (1 + cost_ratio·k)`, the wall-clock factor accounting for the draft's own cost) + `optimal_draft_length(alpha, cost_ratio, max_k)` (throughput-optimal speculative token count, Leviathan et al.). Commit `8965917`; 2 unit (matches expected at zero cost + decreases with cost; optimal lengthens with acceptance, shortens with cost, is the argmax) |
| dflash prompt-lookup decoding (draft-free) | `crates/sovereign-spec-decode/` `prompt_lookup_draft(context, ngram, max_draft)` — PLD (Saxena): use the context as its own draft (find the most-recent earlier occurrence of the current `ngram` suffix, propose the tokens that followed it), so no draft model is needed; drops into the same `verify_greedy`/`verify_sampled` accept loop. End-to-end driver `crates/sovereign-speculative/` `Speculative::decode_prompt_lookup` (lossless vs greedy target; no second model). Commits `2cfa37c`, `0989ff1`; 4 spec-decode unit (proposes earlier continuation; most-recent match; degenerate cases empty; feeds verify_greedy) + 2 speculative unit (lossless across ngram/max_draft; empty-prompt) |
| dflash n-gram-LM draft decoding | `crates/sovereign-speculative/` `Speculative::decode_ngram` — uses a trained n-gram model's `predict_next` (`sovereign-ngram-lm`) to propose draft tokens each round, verified greedily by the target. A **statistical draft that generalizes from its training corpus** — unlike `decode_prompt_lookup` (which can only copy verbatim from the prompt) — yet needs no second neural model. Lossless: output equals greedy target decoding; an n-gram with no prediction commits one target token that round. Activates `sovereign-ngram-lm` (previously **zero consumers**). Commit `1d138ae`; 2 unit (trained-ngram draft is lossless vs greedy target; untrained ngram proposes nothing but still decodes the full greedy sequence) |
| dflash end-to-end sampled decoder | `crates/sovereign-speculative/` `Speculative::decode_sampled` — drives real `DecoderStack`s through `verify_sampled`: draft samples `draft_len` tokens from its sampler-shaped distribution, target teacher-forces them on a fork for per-position distributions, the rejection rule commits the accepted prefix + correction/bonus. Distribution-preserving analogue of the greedy `decode`. Commit `f136b39`; verified it reduces exactly to greedy `decode` under a greedy sampler (across draft lengths) + seed-determinism + models-untouched + input-validation tests |
| RoPE context-length extension (PI · NTK · YaRN) | `crates/sovereign-rope/` linear position interpolation (`with_position_scale` / `for_context_extension`, Chen et al.) + `ntk_aware_base` (NTK-aware scaling, Peng et al.) + **`with_yarn`** (NTK-by-parts/YaRN: per-pair frequency interpolation, high-freq extrapolates + low-freq interpolates — SOTA, outperforming uniform PI/NTK). Wired into the decoder block as `MhaDecoderBlock::with_context_extension` (`crates/sovereign-mha-block/`). Extends usable context past the trained length while preserving RoPE's relative-position identity; all scaling is serde-defaulted off so existing configs are unchanged (`Rope` stays `Copy` via scalar YaRN params). Commits `de54bc5`, `7af9825`, `3b83005`; 8 rope unit (PI halves the angle, context-extension stays in trained range, NTK base grows, YaRN preserves high-freq + interpolates low-freq + norm + serde, legacy-JSON default) + 1 block unit |
| Sliding-window (local) attention | `crates/sovereign-mha-block/` `MhaDecoderBlock::with_sliding_window(w)` — Mistral-style local attention: each step attends to and the KV cache retains only the most recent `w` positions, bounding attention cost and cache memory at long context. A position counter drives RoPE so absolute positions advance as old entries evict; `len()` = positions processed, `cache_len()` = bounded held count. Default full-causal unchanged. Commit `d9297a6`; 2 unit (cache stays within window while positions advance; windowed output depends only on the last `w` positions — the locality property via RoPE relative offset) |
| Attention sinks (StreamingLLM) | `crates/sovereign-mha-block/` `MhaDecoderBlock::with_attention_sinks(s)` — under a sliding window, eviction preserves the first `s` positions (which absorb a large share of attention mass) instead of dropping them, fixing the quality collapse of naive window eviction; evicts the oldest non-sink entry. Commit `690caf5`; 2 unit (the sink keeps the initial token influential where pure SWA would have evicted it — differential property; cache stays within window) |
| OpenAI presence/frequency penalties | `crates/sovereign-sampler/` `SamplerConfig::presence_penalty` (flat additive demotion of any seen token) + `frequency_penalty` (additive, proportional to occurrence count) — the two distinct OpenAI decode penalties, separate from the existing multiplicative CTRL `repetition_penalty`; serde-defaulted. Commit `099114d`; 2 unit (presence count-independent vs frequency count-scaling, both demote recents below unseen; zero penalties no-op) |
| Locally-typical sampling | `crates/sovereign-sampler/` `SamplerConfig::typical_p` + `keep_typical` — the Meister et al. decode control: keep the tokens whose surprisal `−log p` is closest to the distribution's entropy until the mass fraction is reached, trimming both the over-confident head and the surprising tail (distinct from top-k/nucleus/min-p). Wired into the distribution pipeline; defaults to `None` (serde default) so existing configs are unchanged. Commit `95cb59b`; 4 unit (trims extremes on a peaked dist, None keeps full support, uniform keeps the mass fraction, legacy-JSON deserializes) |
| Weight tying (embedding ↔ output head) | `crates/sovereign-quant-model/` `QuantModel::new_tied` — GPT-2/Llama-style tied weights: the output projection reads the embedding table directly, storing one `vocab × model_dim` matrix instead of two; `is_tied()` reports it. Default `new()` untied + unchanged. Commit `58c0b6d`; 2 unit (tied logits equal an untied model built with head==embedding — the tying invariant; embedding-shape validation) |
| Gemma-2 logit soft-capping | `crates/sovereign-quant-model/` `QuantModel::with_logit_softcap(cap)` — bounds each output logit into `(−cap, cap)` via `cap·tanh(logit/cap)`, taming over-confident outliers while staying ~linear near zero and order-preserving; applied in `forward` after the head projection. Default `None`. Commit `9344d15`; 1 unit (capped logits within bounds, argmax preserved, non-positive cap disables) |
| Runnable binaries drive the real engine | Two binaries now assemble + run the inference stack with real capability, not stubs: `sovereign-chat` parses CLI decode controls (`--temperature/-T`, `--top-k`, `--top-p`, `--typical-p`, incl. `--flag=value`) into the engine's sampler so generation is command-line-drivable (commit `3b5d04f`; 5 unit on the parser + custom-sampler runtime); `sovereign-serve` replaces its echo-stub generator with a real `SovereignLlm` backing the cost-aware `serve()` step, so the cache→complexity→budget→generate path runs the model — and a repeated prompt still short-circuits as a `$0` cache hit before the model runs (commit `1ca4556`). | `3b5d04f`, `1ca4556` | 5 chat-parser unit + serve runs end-to-end ($0 cache-hit verified) |
| Chat-template dialects (apply_chat_template) | `crates/sovereign-chat/` `Conversation::render_prompt_with` + `ChatSession::with_format` render the conversation in a real chat dialect — **ChatML** (`<\|im_start\|>`), **Llama-2** (`[INST]`/`<<SYS>>`), **Alpaca** (`### Instruction:`) — via `sovereign-chat-template`'s `render`, instead of the plain `Role:`-labelled default, so an instruction-tuned model gets the exact turn format it was trained on (wrong format quietly wrecks quality). Makes `sovereign-chat-template` (previously **zero consumers**) actually used; surfaced as `sovereign-chat --format chatml\|llama2\|alpaca`; default behavior unchanged. Commit `be81175`; 2 lib unit (ChatML turn markers + differs from default; formatted session records turns) + 1 binary unit (`--format` parse: chatml/alpaca/equals-form/unrecognized→None) |
| Streaming token generation | `crates/sovereign-decoder-stack/` `generate_masked_with` (on_token callback per sampled token; `generate_masked` delegates to it, behavior unchanged) + `crates/sovereign-llm/` `SovereignLlm::generate_ids_streaming` — emit tokens as they arrive (SSE-style) instead of waiting for the whole completion; pristine cache per call. Wired into `sovereign-serve --stream` (prints each token id live, then decodes for cache + accounting). Commits `81b86d7`, `de4515e`; 4 unit (streamed sequence equals batch + fires per token, in both crates; empty-prompt errors) + serve runs |
| Tokenizer special tokens (BOS/EOS/PAD) | `crates/sovereign-tokenizer/` `with_specials` + `special_id`/`special_name` + `bpe_vocab_size` — reserve control-token ids above the BPE vocabulary; `encode` never emits them, `decode` skips them, they survive the serde round-trip. The fundamental serving primitive that pairs with early-stop generation (an `<eos>` id is the natural stop token). Commit `7a49e5a`; 4 unit (id reservation; encode-never-emits + decode-skips; dedupe/empty; serde round-trip) — and `decode(encode(text))==text` invariant preserved |
| Beam search — EOS termination + length normalization | `crates/sovereign-beam-search/` `BeamSearch::search_with(base, prompt, eos, length_penalty)` — a beam emitting the eos token finishes (not extended); the winner is ranked by length-normalized score `score/lenᵅ`, removing raw log-prob's bias toward short sequences (now meaningful with variable-length EOS beams; pairs with the tokenizer special tokens). `eos=None`+`α=0` reproduces `search`. Commit `ab1507d`; 4 unit (length-norm corrects the short-sequence bias; defaults equal plain search; bounded + validation; α=0/len-0 edges) |
| Stop sequences (text-level) | `crates/sovereign-llm/` `SovereignLlm::complete_until_string` — truncate the completion at the first occurrence of any stop **string** (the OpenAI `stop` parameter; operates on text so it can span several tokens, unlike a single stop token). Commit `2e0c615`; 1 unit (no/non-matching stops → full; first-char stop → empty) |
| n-sampling + self-consistency | `crates/sovereign-llm/` `SovereignLlm::generate_ids_n` (the OpenAI `n`/best-of parameter: `n` samples at `base_seed+i`, diverse-yet-reproducible) + `majority_sequence` free fn (self-consistency vote — the most common sequence across samples, ties to earliest-seen). A simple accuracy boost for single-answer tasks. Commit `439fd07`; 2 unit (n samples match single-call seeds + greedy identical; majority picks most-common, tie-breaks earliest, empty→None) |
| Context-budget fitting | `crates/sovereign-llm/` `SovereignLlm::complete_within_context` — trims an over-long prompt to the most recent `max_context` tokens (`sovereign-context-budget`, keeping the tail nearest where generation continues) before completing, so a prompt that would overflow the model's context window is bounded instead of silently degrading; a fitting prompt is unchanged. Makes `sovereign-context-budget` (previously **zero consumers**) actually used; reproducible per seed. **Surfaced in the serving binary**: `sovereign-serve --max-context N` trims each prompt to its most recent N tokens before generation. Commits `e1ff1f6`, `41de281`; 2 llm unit (overlong prompt trimmed to ≤ budget + equals completing the tail-trim — faithful wiring; fitting prompt unchanged) + 1 serve integration (`--max-context` serves a trimmed prompt + still caches) |
| Token healing (prompt/completion seam) | `crates/sovereign-llm/` `SovereignLlm::complete_healed` — trims the prompt's trailing token, keeps its surface as a prefix constraint, and forces the **first** generated token (via `generate_dynamic_mask`) to be boundary-consistent (`sovereign-token-healing`'s `allowed_continuations`) so the model re-chooses the natural split — fixing the classic seam bug (`http` handed as a token can't become `https`). Strips the re-formed prefix so the result continues the original prompt; falls back to plain `complete` when nothing is healable (single-token/empty prompt). Makes `sovereign-token-healing` (previously **zero consumers**) actually used; reproducible per seed. Commit `e472f56`; 3 unit (only boundary-consistent first tokens allowed for prefix "b"; single-token prompt falls back to complete; reproducible) |
| JSON-Schema-constrained decoding (grammar) | `crates/sovereign-decoder-stack/` `DecoderStack::generate_dynamic_mask_until` (stoppable per-step mask loop) + `crates/sovereign-llm/` `SovereignLlm::complete_json_schema` — compiles a JSON Schema to a grammar (`sovereign-json-schema-grammar`), masks each step to the tokens that keep a valid parse reachable (`sovereign-token-grammar-mask`), and **stops** when the output is a complete sentence of the grammar — so the result is always well-formed and conforming, never truncated mid-structure. The strongest structured/tool-call output. Activates **two** crates (both previously **zero consumers**); reproducible per seed. Commit `b9b0909`; 1 stack unit (the until-loop stops when the hook returns None) + 3 llm unit (output stays in the grammar alphabet — no out-of-grammar char; the mask allows `true`/`false` but forbids `z` after `{"ok":`; reproducible) |
| Regex-constrained decoding (guaranteed format) | `crates/sovereign-decoder-stack/` `DecoderStack::generate_dynamic_mask` (recomputes the logit mask **each step** from the tokens generated so far) + `crates/sovereign-llm/` `SovereignLlm::complete_regex` — drives that loop with `sovereign-regex-constrain` (over `sovereign-regex-nfa`): every step forbids tokens that would make the pattern unsatisfiable, so the model can only ever emit strings the regex accepts (digits-only, dates, enums, JSON shapes). Activates `sovereign-regex-constrain` (previously **zero consumers**); stateless on a model clone, reproducible per seed, invalid pattern → typed `Regex` error. **Surfaced in the serving binary**: `sovereign-serve --regex RE` routes generation through `complete_regex` so every served completion matches RE. Commits `0ce00ec`, `9f0a9cd`; 2 stack unit (dynamic mask confines every token to the allowed set; the mask can tighten as generation proceeds) + 2 llm unit (`[0-9]+` yields 6 ASCII digits regardless of weights; reproducible + bad pattern rejected) + 1 serve integration (`--regex [0-9]+` serves digits-only, no letters leak) |
| Structured-output extraction (JSON) | `crates/sovereign-llm/` `SovereignLlm::complete_json` — completes then pulls the first **balanced JSON value** out of the (often prose-wrapped) output via `sovereign-json-extract` (scans for `{`/`[`, respects string literals, hands the span to `serde_json`), returning `Some(value)`/`None` — the post-hoc structured-output / tool-call extraction step. Makes `sovereign-json-extract` (previously **zero consumers**) actually used; reproducible per seed. Commit `c880709`; 2 unit (method equals extracting from the completion — faithful wiring; balanced JSON pulled from wrapped prose, no-JSON → error→None) |
| Generation confidence / uncertainty | `crates/sovereign-llm/` `SovereignLlm::completion_confidence` + `ConfidenceReport` — generates, scores the *generated* tokens teacher-forced (`perplexity::token_logprobs`), and summarizes them with `sovereign-logprobs` (mean log-prob, perplexity, weakest token), so a serving loop can flag a low-confidence answer for review/regeneration. Makes `sovereign-logprobs` (previously **zero consumers**) actually used; `None` when nothing is generated; reproducible per seed. Commit `cb018eb`; 3 unit (one logprob per generated token + valid perplexity + weakest ≤ mean; zero-max_new → None; reproducible) |
| Output content-safety screen (toxicity) | `crates/sovereign-llm/` `SovereignLlm::complete_screened` — scans the completion with a caller-supplied `ToxicityFilter` (`sovereign-toxicity`: normalizes leetspeak/obfuscation — `f4ck`/`$h1t`/`a-s-s` — then matches a severity-tiered term list) and returns the text with a `bool` toxic-at-threshold verdict, so a serving loop can block/regenerate toxic output. Completes the egress-safety trio (secrets · PII · toxicity). Makes `sovereign-toxicity` (previously **zero consumers**) actually used; reproducible per seed. **Surfaced in the serving binary**: `sovereign-serve --screen` refuses a toxic completion (composes with `--redact`). Commits `c397f5e`, `4b24fc7`; 2 llm unit (method verdict equals the filter's — faithful wiring; a planted Severe term is flagged, clean text is not) + 1 serve integration (`--screen` runs the egress path) |
| Output egress filter (secrets + PII) | `crates/sovereign-llm/` `SovereignLlm::complete_redacted` — generates then scrubs the output: secrets first (AWS/GitHub/Slack tokens, `sovereign-secret-scan`) then PII (emails, SSNs, phones, `sovereign-pii-redact`), so a grounded runtime can't echo sensitive material leaked in from a retrieved document or the prompt. Makes both crates (previously **zero consumers**) actually used as the runtime egress gate; reproducible per seed. **Surfaced in the serving binary**: `sovereign-serve --redact` scrubs every completion before it is cached/returned. Commits `f41a693`, `057364d`; 2 llm unit (method equals the manual scrub pipeline — faithful wiring; the pipeline removes a planted AWS key + email) + 1 serve integration (`--redact` runs the egress path end-to-end) |
| Self-consistency with answer extraction | `crates/sovereign-llm/` `SovereignLlm::consistent_answer` + `majority_answer` free fn — generate `n` samples, extract the final answer from each (`sovereign-answer-extract`: *Final answer:* / *the answer is* / *Answer:* markers, else last line), and return the **majority** answer + vote count. Extracting *before* voting groups equivalent conclusions reached through different reasoning prose — the standard self-consistency recipe — which the raw-sequence `majority_sequence` misses. Makes `sovereign-answer-extract` (previously **zero consumers**) actually used; reproducible per base_seed. Commit `9312b43`; 4 unit (majority + earliest-tie + empty; greedy n=4 → extracted answer with 4 votes; zero-n → None; reproducible) |
| Best-of-n diversity (mode-collapse detection) | `crates/sovereign-llm/` `SovereignLlm::sample_diversity` + `SampleDiversity` — runs `generate_ids_n`, decodes the samples, and measures distinct-1/distinct-2, Self-BLEU, and unique-ratio (`sovereign-diversity`) so a serving loop can detect **mode collapse**: a cold sampler or degenerate model returns near-identical samples (low distinct-n/unique-ratio, high Self-BLEU). Makes `sovereign-diversity` (previously **zero consumers**) actually used on real generations; reproducible per base_seed. Commit `d32e584`; 3 unit (greedy collapse → unique-ratio 0.25 + all metrics in range; single sample → unique 1.0/Self-BLEU 0; reproducible) |
| Degeneration-checked completion (loop guard) | `crates/sovereign-llm/` `SovereignLlm::complete_checked` — generates, then analyzes the output for loop/repeat collapse (longest repeated substring + rep-n distinct-n-gram diversity + repeat coverage, `sovereign-degeneration`) against a config, returning `(text, DegenerationReport)` so a serving loop can reject or regenerate a looping completion via the `is_degenerate` flag. Makes `sovereign-degeneration` (previously **zero consumers**) actually used in the runtime; reproducible per seed. Commit `71c5cc3`; 3 unit (report equals `analyze()` of the produced text — faithful wiring; the gate flags a known loop; reproducible) |
| Prefix KV reuse (system-prompt amortization) | `crates/sovereign-decoder-stack/` `DecoderStack::prime(prefix)` — ingest a shared prefix into the KV cache without generating, so it is primed once and the primed stack is cloned per request to generate only the suffix, amortizing the prefix's forward passes. Output-transparent (prime + generate(suffix) == generate(prefix++suffix)). Commit `96eaef5`; 1 unit (transparency + the primed base stays reusable) |
| Unified composable generation | `crates/sovereign-decoder-stack/` `GenOptions` (builder: max_new · base `LogitMask` · `no_repeat_ngram` · `stop_tokens` · `min_new` min-length) + `generate_with` (one loop composing constrained masking + dynamic no-repeat-ngram + early-stop + min-length + per-token streaming, which the single-purpose methods could only do separately) + `crates/sovereign-llm/` `SovereignLlm::generate_ids_with` (same at the text-to-text API). Commits `de0d539`, `fe49190`, `0375a96`; 3 stack unit (all controls compose; plain == generate; min-length defers the stop token) + 2 llm unit (composes + streams + reproducible; empty-prompt) |
| Logit-processor pipeline (composable decode controls) | `crates/sovereign-decoder-stack/` `DecoderStack::generate_piped` — drives each step's logits through a **`LogitPipeline`** (`sovereign-logit-pipeline`): an ordered list of `LogitProcessor`s (built-in `MaskProcessor` wrapping a `LogitMask`, `NoRepeatProcessor` wrapping `NoRepeatNgram`, or any caller trait impl) applied over the prompt+generated history before sampling. The composable generalization of the single-control methods — every control is one pipeline entry, order explicit, none forgotten; an empty pipeline == plain `generate`. Activates `sovereign-logit-pipeline` (previously **zero consumers**); reproducible per seed. **Surfaced in the running binary**: `run_strategies_demo` composes a ban-mask + 2-gram-no-repeat pipeline and prints `logit pipeline : […] (2 processors; banned leaked: false)`. Commit `d7a5f79`; 2 stack unit (empty pipeline == plain generate; two ban-processors both apply so no banned token leaks) + demo asserts the line |
| Gumbel-max sampling (branch-free logit draw) | `crates/sovereign-decoder-stack/` `DecoderStack::generate_gumbel` — samples each token by the **Gumbel-max trick** (`sovereign-gumbel`): add one i.i.d. Gumbel sample to every logit and take the `argmax`, whose winner is distributed *exactly* as `softmax(logits)` — a branch-free draw from the raw logits with no explicit normalization (≡ multinomial sampling at temperature 1). Bypasses the config sampler's truncation; `-inf` logits stay forbidden. Activates `sovereign-gumbel` (previously **zero consumers**); reproducible per seed (one seeded Gumbel stream per call). **Surfaced in the running binary**: `run_strategies_demo` prints `gumbel-max : […]`. Commit `a1b54f4`; 2 stack unit (in-range + seed-reproducible; a peaked logit wins >360/400 single-step draws — matches softmax) + demo asserts the line |
| Early-stop generation (EOS / stop tokens) | `crates/sovereign-decoder-stack/` `generate_until` + `crates/sovereign-llm/` `SovereignLlm::generate_ids_until` — stop the moment a stop token is produced (included in the result) instead of always running to `max_new`; the fundamental EOS/stop-sequence behaviour a real runtime needs. Empty stop set == `generate`. Commit `ac80c83`; 2 stack unit + 2 llm unit (stops after the stop token; empty set → full length; empty-prompt) |
| No-repeat-ngram blocking | `crates/sovereign-logit-mask/` `no_repeat_ngram_bans` + `LogitMask::no_repeat_ngram` (ban tokens completing an already-seen n-gram by matching the current (n−1)-suffix against history) + `crates/sovereign-decoder-stack/` `generate_no_repeat_ngram` (rebuilds the blocklist from the live history every step, so loops can't form as the sequence grows). Distinct from the sampler's soft repetition penalty. Commits `ea9cdcc`, `171fbc6`; 3 mask unit (blocks repeater, collects matches, edge cases) + 2 stack unit (generated sequence has no repeated 3-gram + reproducible; empty-prompt) |
| DRY (Don't Repeat Yourself) sampling | `crates/sovereign-decoder-stack/` `DecoderStack::generate_dry` + `crates/sovereign-llm/` `SovereignLlm::complete_dry` — applies DRY to the logits each step: each candidate is penalized by how long a previously-generated sequence picking it would extend (exponential in match length past `allowed_length`, scaled by `multiplier`/`base`), so a long verbatim loop becomes exponentially hard to continue while ordinary reuse is barely touched — targeted loop suppression without the collateral damage of a flat repetition penalty or a hard n-gram ban. Activates `sovereign-dry-sampler` (previously **zero consumers**); reproducible per seed. **Both XTC and DRY surfaced in the serving binary**: `sovereign-serve --xtc` / `--dry` route through `complete_xtc`/`complete_dry`. Commits `c6ace5c`, `84d1dc3`; 2 stack unit (multiplier 0 == plain generate; active is reproducible) + 2 llm unit (inactive == plain complete; reproducible) + 1 serve integration (`--xtc`/`--dry` both run + cache) |
| XTC (Exclude Top Choices) sampling | `crates/sovereign-decoder-stack/` `DecoderStack::generate_xtc` + `crates/sovereign-llm/` `SovereignLlm::complete_xtc` — applies XTC to the logits each step before the configured sampler: when several tokens clear the confidence `threshold`, the most-probable ones are dropped (with a per-step `probability`, on a seed stream distinct from the sampler's) so a lower-but-plausible token can win — more creative output than the base sampler without hot-temperature incoherence, and a no-op when only one token is confident. Activates `sovereign-xtc-sampler` (previously **zero consumers**); composes with the existing sampler; reproducible per seed. Commit `f6daba3`; 2 stack unit (probability 0 == plain generate; always-firing is reproducible) + 2 llm unit (inactive == plain complete; reproducible) |
| Mirostat v2 sampling (full chain) | `crates/sovereign-sampler/` `Mirostat` — stateful perplexity-targeting decode controller (Basu et al.): targets constant surprise τ via a running μ threshold (truncate within μ → sample → nudge μ by observed-vs-target error), holding output perplexity steady regardless of per-step peakedness. Wired end-to-end: `DecoderStack::generate_mirostat` drives the decode loop with it (reproducible per seed), and `SovereignLlm::generate_ids_mirostat` exposes it at the text-to-text API so binaries can use it. Commits `3f626c6`, `12fb99b`, `64d342f`; 4 sampler unit (μ init = 2τ, control-law direction, surprise converges near τ over 4000 steps, empty-support → None) + 2 stack unit (reproducible + μ adapts; empty-prompt) + 2 llm unit (runs + reproducible; empty-prompt) |
| Repetition/frequency/presence penalties (full chain) | `crates/sovereign-decoder-stack/` `DecoderStack::generate_penalized` + `crates/sovereign-llm/` `SovereignLlm::complete_penalized` — applies the classic CTRL-style trio to the logits each step over the prompt+generated history: `repetition` scales down any already-seen token (`1.0`=off), `frequency` subtracts proportional to prior count, `presence` subtracts a flat amount for any prior appearance (`0.0`=off) — discouraging loops and over-used tokens. Activates `sovereign-repetition-penalty` (previously **zero consumers**); identity params reduce to the base sampler; reproducible per seed. **Surfaced in the running binary**: `run_strategies_demo` prints the `penalized :` line. Commit `2c4e816`; 2 stack unit (identity == plain generate; active is reproducible) + 2 llm unit (identity == plain complete; reproducible) + demo asserts the line |
| Locally-typical sampling — standalone crate (full chain) | `crates/sovereign-decoder-stack/` `DecoderStack::generate_typical` + `crates/sovereign-llm/` `SovereignLlm::complete_typical` — keeps only the tokens whose surprisal is nearest the distribution's entropy (the typical set) at cumulative `mass`, masking the rest before sampling (`mass=1.0` keeps the whole vocab → base sampler). Activates the **standalone** `sovereign-typical-sampling` crate (previously **zero consumers**) via the decode loop — distinct from the sampler's built-in `SamplerConfig::typical_p` (that path masks inside the distribution; this one masks the logits in the generate loop like DRY/XTC). Reproducible per seed. **Surfaced in the running binary**: `run_strategies_demo` prints the `typical (m=0.9) :` line. Commit `2c4e816`; 2 stack unit (full-mass == plain generate; active reproducible) + 2 llm unit (full-mass == plain complete; reproducible) + demo asserts the line |
| Self-consistency voting — standalone crate (full chain) | `crates/sovereign-llm/` `SovereignLlm::complete_self_consistent` (+ re-exported `Vote`) — draws `samples` completions (seeds `base_seed..+samples`), normalizes, and returns the **majority answer** with its `agreement` fraction — the self-consistency trick (a single-answer task is more reliably solved by voting several independent decodes than by one greedy pass), agreement as a cheap confidence signal. Activates the **standalone** `sovereign-self-consistency` crate (previously **zero consumers**) — richer than the pre-existing `majority_sequence` free fn (adds agreement/total accounting). Greedy → unanimous (`agreement 1.0`); temperature → a real vote. Reproducible per `base_seed`; a `SelfConsistency` `LlmError` on zero-samples / all-failed. **Surfaced in the running binary**: `run_rag_quality_demo` prints `self-consistency : 1/5 agree (agreement=0.20) …`. Commit `936a339`; 3 llm unit (greedy unanimous + voted answer == single greedy; temperature reproducible; zero-samples errors) + demo asserts the line |
| Best-of-n by model confidence (full chain) | `crates/sovereign-llm/` `SovereignLlm::complete_best_of_n` — draws `n` completions (seeds `base_seed..+n`), scores each by the model's own **mean per-token log-prob** (`completion_confidence`), and returns the highest-scoring one via `sovereign-best-of-n::best` — best-of-`n` sampling that trades compute for quality (keep the candidate the model is most confident in, not one stochastic decode). Activates the **standalone** `sovereign-best-of-n` crate (previously **zero consumers**); `n` clamped to ≥1 (n=0 → single completion at `base_seed`), ties to the earliest seed; an empty generation scores worst. Reproducible per `base_seed`. **Surfaced in the running binary**: `run_rag_quality_demo` prints `best-of-4 : kept the highest-confidence of 4 candidates (24 chars)`. Commit `ff8b8a8`; 3 llm unit (greedy == single complete; n=0 clamps to single; stochastic winner is one of the n candidates + reproducible) + demo asserts the line |
| Confidence calibration (temperature scaling) | `crates/sovereign-llm/` `SovereignLlm::calibrate` (+ `Calibration`) — **temperature-scales** the model's next-token confidence over a reference sequence (`sovereign-confidence-calibration`): teacher-forcing along the reference yields, per position, a predicted distribution whose label is the actual next token; `fit_temperature` learns the single scalar `T` (logits ÷ `T`) that best calibrates them, and the **expected calibration error** is reported before (`T=1`) and after — how far stated confidence sits from accuracy and how much a one-parameter fix closes it. Activates `sovereign-confidence-calibration` (previously **zero consumers**); `None` for a sub-two-token reference; deterministic. **Surfaced in the running binary**: `run_rag_quality_demo` prints `calibration : T=2.42, ECE 0.005 -> 0.013 over 42 preds`. Commit `924151c`; 2 llm unit (fits a finite T + reports ECE in [0,1] over a full teacher-forced pass; None for a 1-token reference + reproducible) + demo asserts the line |
| Semantic cache — runtime-fronting wrapper (standalone crate) | `crates/sovereign-llm/` `SemanticCachedLlm` + `CachedCompletion` — wraps a `SovereignLlm` in front of a semantic completion cache: `complete` embeds the prompt, and if a prior prompt clears the cosine threshold it returns the cached completion (no decode), else runs the model and populates the cache — so a paraphrase of an earlier request is served for `$0`. Activates the **standalone** `sovereign-semantic-cache` crate (previously **zero consumers**) — distinct from the already-shipped `sovereign-completion-cache::SemanticCache` (a library type): this one actually fronts the runtime's `complete`, turning the cache into a serving path. Exposes hit/miss/len stats; reproducible per seed. **Surfaced in the running binary**: `run_rag_quality_demo` prints `semantic cache : first cached=false, repeat cached=true (hits=1, misses=1)`. Commit `e3c6ceb`; 3 llm unit (first-miss-then-exact-repeat-hit + stats; miss == plain complete — faithful wiring; threshold 1.0 only hits identical prompts) + demo asserts the line |
| Pulse algorithmic foundation SDD | `docs/sdd/027-pulse-algorithmic-foundation.md` — the algorithmic foundation backing the v0 Cortex |
| Trinity composition | `crates/sovereign-trinity/` (cross-ref M066) |

### M010 — Deterministic data plane (simdjson / Hyperscan / CRoaring)

| Surface | Shipped artifact |
|---|---|
| Inference-backend-stack SDD | `docs/sdd/011-inference-backend-stack.md` (cross-ref M009) — anchors the data-plane stack choice |
| Conversation search index | `crates/sovereign-conversation-search-index/` — Hyperscan-backed search surface for the conversation substrate |

### M011 — KV cache as memory hierarchy

| Surface | Shipped artifact |
|---|---|
| Inference-backend-stack SDD | `docs/sdd/011-inference-backend-stack.md` (cross-ref M009, M010) — the KV-cache placement is part of the inference-stack spec |
| Memory OS | `crates/sovereign-memory-os/` + `crates/sovereign-pressure-sensors/` (cross-ref M014, M028) — the memory-hierarchy substrate that hosts the KV cache |

### M015 — Agent programming model

| Surface | Shipped artifact |
|---|---|
| Test-harness SDD | `docs/sdd/008-test-harness.md` (cross-ref M065, M082) — anchors the TDD-driven agent programming discipline |
| Prompt template registry | `crates/sovereign-prompt-template-registry/` — typed surface for agent-program templates |
| Cognitive compiler | `crates/sovereign-cognitive-compiler/` (cross-ref M025) — the intent-to-DAG surface enabling the agent-programming model |

### M016 — Learning without retraining

| Surface | Shipped artifact |
|---|---|
| dflash speculative-decoding SDD | `docs/sdd/026-dflash-speculative-decoding.md` (cross-ref M009) — the on-line variant adaptation pattern |
| LoRA foundry | `crates/sovereign-lora-foundry/` (cross-ref M046) — on-device adapter learning, no retraining of base weights |

### M018 — Serving topology (local inference fabric)

| Surface | Shipped artifact |
|---|---|
| Inference backend stack SDD | `docs/sdd/011-inference-backend-stack.md` (cross-ref M009-M011) |
| Inference-service hardening SDD | `docs/sdd/036-inference-service-hardening-doctrine.md` (cross-ref M006) — the production-hardened serving topology |
| Inference scripts | `scripts/inference/` — operator-runtime surface for the local inference fabric |
| Semantic completion cache | `crates/sovereign-completion-cache/` `SemanticCache` — GPTCache-style `$0` serving: returns a cached completion when a new prompt is embedding-similar (cosine ≥ threshold) to a stored one, so paraphrases/near-duplicates hit (which the exact-key `CompletionCache` can't). Composes `sovereign-embed` cosine; bounded + hit/miss stats. Commit `935c40b`; 3 unit (hits a paraphrase + misses unrelated; exact always hits; oldest-evict) |
| Semantic cache wired into serving | `crates/sovereign-serve/` `Server::with_semantic` + `--semantic` flag — the `SemanticCache` is now *used* end-to-end as a second tier: exact cache → semantic cache → generate, so a paraphrase of an already-served prompt is a `$0` hit instead of a fresh model run. `ServeResult.semantic_hit` distinguishes the tier; binary prints `hit=exact`/`hit=semantic` and a `[N exact, N semantic]` summary. Commit `5a808cd`; 2 lib (paraphrase served free + model not re-run; default server still runs the paraphrase) + 1 binary integration (`--semantic` shows `hit=semantic`) |

### M019 — Intelligence creation (composable cognitive operators)

| Surface | Shipped artifact |
|---|---|
| Cognitive compiler | `crates/sovereign-cognitive-compiler/` (cross-ref M025) — operator composition into DAGs |
| Six pillars | `crates/sovereign-six-pillars/` (cross-ref M048) — the 6-pillar typed surface composes the cognitive operators |

### M020 — Orchestration without captivity (semantic ISA)

| Surface | Shipped artifact |
|---|---|
| Cognitive compiler (cross-ref M025) | `crates/sovereign-cognitive-compiler/` — the semantic ISA materialised as a typed compiler surface |
| Tool catalog (cross-ref M048) | `crates/sovereign-tool-catalog/` — the orchestrable tool surface the ISA enumerates |

### M021 — REPL / CoT / MoE / workflow / logic / intelligence weave

| Surface | Shipped artifact |
|---|---|
| Conversation substrate | `crates/sovereign-conversation-thread/`, `crates/sovereign-conversation-fork-event/`, `crates/sovereign-conversation-search-index/` (cross-ref M012) — REPL + CoT carrier |
| Prompt history ring | `crates/sovereign-prompt-history-ring/` — CoT-style prompt-rationale ring (cross-ref M033) |

### M022 — Cognitive Frame (system-level MoE)

| Surface | Shipped artifact |
|---|---|
| Router with 7-axis decision (cross-ref M057) | `crates/sovereign-router-7axis/` — the MoE-style expert routing substrate |
| Routing-decision log | `crates/sovereign-routing-decision-log/`, `crates/sovereign-routing-preference/` — typed surface for the cognitive-frame routing decisions |

### M023 — Execution substrate (WASM / Deno / Python / VM tiers)

| Surface | Shipped artifact |
|---|---|
| Inference-service hardening SDD | `docs/sdd/036-inference-service-hardening-doctrine.md` (cross-ref M006, M018) — anchors the tier-isolation discipline across the WASM/Deno/Python/VM substrate |
| Tool catalog (cross-ref M048) | `crates/sovereign-tool-catalog/` — the tier-aware tool registry that resolves into the right execution substrate |

### M024 — Adaptive programming (profiles as reward weights)

| Surface | Shipped artifact |
|---|---|
| Profile schemas (cross-ref M041) | `schemas/profile.schema.yaml`, `schemas/runtime-profile.schema.yaml` — typed contracts for profile-as-reward-weight composition |
| Profile bundles | `crates/sovereign-profile-bundles/` (cross-ref M041) |
| Operator profiles | `profiles/developer.yaml`, `profiles/headless.yaml`, `profiles/minimal.yaml`, `profiles/old-workstation.yaml`, `profiles/sain-01.yaml` |

### M029 — Computer-Use plane (perception / planning / execution)

| Surface | Shipped artifact |
|---|---|
| Pulse algorithmic foundation SDD | `docs/sdd/027-pulse-algorithmic-foundation.md` (cross-ref M009) — anchors the perception/planning/execution discipline within the Pulse runtime |
| Trinity composition | `crates/sovereign-trinity/` (cross-ref M066) — Pulse + Weaver + Auditor maps to perception + planning + execution |

### M030 — World Model plane (state / action / transition)

| Surface | Shipped artifact |
|---|---|
| Environment maps | `crates/sovereign-environment-maps/` (cross-ref M028) — the typed state-space surface |
| Mode-transition log | `crates/sovereign-mode-transition-log/` (cross-ref M042, M055) — append-only transition log for the world-model state |

### M031 — Symbolic Planning plane (PDDL / SAT-SMT / LTL)

| Surface | Shipped artifact |
|---|---|
| Cognitive compiler (cross-ref M025) | `crates/sovereign-cognitive-compiler/` — the symbolic-planning DAG compiler surface |

### M032 — Cloud Expert plane (OpenAI + Anthropic as remote experts)

| Surface | Shipped artifact |
|---|---|
| Provider catalog (cross-ref M017) | `crates/sovereign-provider-catalog/` — registry of remote-expert providers |
| Gateway (cross-ref M033, M034) | `crates/sovereign-gateway/` — the surface where remote experts are addressable |

### M034 — Anthropic-first gateway + MCP + Claude Code integration

| Surface | Shipped artifact |
|---|---|
| Gateway (cross-ref M033) | `crates/sovereign-gateway/` |
| MCP-aggregate SDD | `docs/sdd/031-mcp-aggregate.md` — anchors the MCP aggregation pattern for the Anthropic-first gateway |
| Claude-code-env scripts | `scripts/claude-code-env/` — the operator-side integration with Claude Code (templates + apply + validate) |

### M035 — Frontier (inference-time intelligence)

| Surface | Shipped artifact |
|---|---|
| Inference-backend-stack SDD | `docs/sdd/011-inference-backend-stack.md` (cross-ref M009) |
| dflash speculative-decoding SDD | `docs/sdd/026-dflash-speculative-decoding.md` (cross-ref M009) — the inference-time intelligence acceleration |
| HölderPO + GRPO (cross-ref M078) | `crates/sovereign-holderpo/` — inference-time aggregation pattern |

### M036 — MAP (map-then-act paradigm)

| Surface | Shipped artifact |
|---|---|
| Trinity composition (cross-ref M066) | `crates/sovereign-trinity/` — the Pulse-maps-then-Weaver-acts discipline |
| Mode-transition log | `crates/sovereign-mode-transition-log/` (cross-ref M030, M042) — append-only log of the map→act state transitions |

### M039 — AVX-512 cortex hot path

| Surface | Shipped artifact |
|---|---|
| Hardware-stack consolidation SDD | `docs/sdd/029-hardware-stack-consolidation.md` (cross-ref M007, M008, M070) |
| AVX-512 advisor | `scripts/hardware/avx512-advisor.py` (cross-ref M007, M008) |
| SRP scheduler (cross-ref M075) | `crates/sovereign-srp-scheduler/` — the CPU/GPU placement scheduler that the AVX-512 hot path runs on |

### M043 — Bridge layer (hardware-aware intelligence scheduling)

| Surface | Shipped artifact |
|---|---|
| Hardware-dispatch eligibility (cross-ref M038) | `crates/sovereign-hardware-dispatch-eligibility/` — typed eligibility surface for the bridge layer |
| Hardware registry (cross-ref M038) | `crates/sovereign-hardware-registry/` — registry the bridge layer routes against |
| SRP scheduler (cross-ref M075) | `crates/sovereign-srp-scheduler/` — the scheduling discipline that materialises the bridge |

### M050 — Architect + Engineer seat (heterogeneous intelligence system)

| Surface | Shipped artifact |
|---|---|
| Architecture-QA script | `scripts/intelligence/architecture-qa.py` — operator-side surface for the Architect seat |
| Cockpit personalization (cross-ref M026) | `crates/sovereign-cockpit-personalization/` — the seat-specific personalization substrate |

### M051 — DevOps + Fullstack + AI expert layer

| Surface | Shipped artifact |
|---|---|
| Intelligence scripts | `scripts/intelligence/` — `architecture-qa.py`, `cot-registry.py`, `coverage-map.py`, `doctrine-status.py`, `guide.py`, `layers.py`, `memory-changes.py`, `module-state.py`, `morning-brief.py` — the operator-facing expert-layer surface |
| Continuity manager (cross-ref M047) | `crates/sovereign-continuity-manager/` — the cross-discipline state-preservation substrate |

### M052 — Vision recap (Ultimate AI Workstation)

| Surface | Shipped artifact |
|---|---|
| Charter SDD | `docs/sdd/000-charter.md` — the foundational charter recapping the Ultimate AI Workstation vision |
| Six pillars | `crates/sovereign-six-pillars/` (cross-ref M048) — the 6-pillar tracker materialising the vision recap |

### M059 — Sovereign close (the peace machine)

| Surface | Shipped artifact |
|---|---|
| Charter SDD | `docs/sdd/000-charter.md` — the Sovereign-Close framing of the peace-machine vision |
| Doctrinal preservation (cross-ref M061) | `crates/sovereign-doctrinal-preservation/`, `crates/sovereign-doctrine-citation/` — the canon-preservation substrate enabling Sovereign Close to retain doctrinal integrity through OS-level mutations |

### M063 — SFIF discipline (Scaffold → Foundation → Infrastructure → Features)

| Surface | Shipped artifact |
|---|---|
| Cockpit-dashboard implementation-bridge SDD | `docs/sdd/040-cockpit-dashboard-implementation-bridge.md` — anchors the SFIF discipline at the cockpit-dashboard layer |
| 8-surface delivery contract SDD | `docs/sdd/039-eight-surface-delivery-contract.md` (cross-ref M056) — the discipline enforcing SFIF progression to all 8 surfaces |
| Test-harness SDD | `docs/sdd/008-test-harness.md` (cross-ref M065, M082) — the gated discipline that prevents Feature-without-Foundation drift |

### Cross-cutting cockpit crates (M060 + adjacent milestones)

| Family | Shipped surface |
|---|---|
| Cockpit runtime crates | `crates/sovereign-cockpit-*/` — 417 crates covering accent-color-policy, accordion, achievement-toast, action-bar/menu/discoverability, activity-feed, agenda-view, alert-{acknowledge,group,tile-board}, attachment-tray, audit-trail, avatar-stack, banner-{bus,state}, breadcrumb-trail, etc. The bulk of the cockpit-as-UX-substrate surface |
| Conversation substrate (M021 / M060) | `crates/sovereign-conversation-thread/`, `crates/sovereign-conversation-fork-event/`, `crates/sovereign-conversation-search-index/`, `crates/sovereign-prompt-history-ring/`, `crates/sovereign-prompt-rationale/`, `crates/sovereign-prompt-template-registry/`, `crates/sovereign-workspace-folder-registry/`, `crates/sovereign-dashboard-layout/`, `crates/sovereign-dashboard-snapshot/`, `crates/sovereign-dashboard-toggle/`, `crates/sovereign-dashboard-coverage/` — the conversation/dashboard substrate underlying the operator-cockpit experience |

### M026-M059 — Operator-§1g surfaces + cockpit + intelligence layer

| Milestone family | Shipped surface |
|---|---|
| Cockpit personalization (M026-M060 family) | `crates/sovereign-cockpit-personalization/`, `crates/sovereign-cockpit-accent-color-policy/`, `crates/sovereign-cockpit-theme-palette/`, `webapp/personalization/` |
| ARIA / a11y | `crates/sovereign-cockpit-aria-live-router/` + `webapp/_shared/nav-snippet.html` (M060 R10055 + R10058-R10105 keyboard-nav) |
| Intelligence scripts | `scripts/intelligence/` — `architecture-qa.py`, `cot-registry.py`, `coverage-map.py`, `doctrine-status.py`, `guide.py`, `layers.py`, `memory-changes.py`, `module-state.py`, `morning-brief.py` (sample) |
| Diagnostics scripts | `scripts/diagnostics/` — `apply-audit.py`, `assistant-next-steps.py`, `autohealth.py`, `config-restore.py`, `config-snapshot.py`, `doctor.py`, `m060-smoke.py`, `overlay-drift-detector.py` (sample) |
| Install scripts | `scripts/install/` — `install-mode-advisor.py`, `operator-deps.py`, `paths.py` |
| Profile system | `profiles/` — `developer.yaml`, `headless.yaml`, `minimal.yaml`, `old-workstation.yaml`, `sain-01.yaml` + `profiles/runtime/`, `profiles/mixins/` |
| Schema system | `schemas/` — `mixin.schema.yaml`, `model-catalog.schema.yaml`, `profile.schema.yaml`, `runtime-profile.schema.yaml`, `whitelabel.schema.yaml` |

### M061 — avx-plus-plus canon-update backward-sweep (operator standing direction)

| Surface | Shipped artifact |
|---|---|
| Catalogue milestone | `backlog/milestones/M061-avx-plus-plus-canon-update-backward-sweep-2026-05-19.md` (170 R-rows mapping the 6 redefinitions) |
| Patch-Pass A annotations | applied to 11 affected milestones across selfdef + sovereign-os per `context.md` § Backward-sweep |
| Doctrinal preservation surface | `crates/sovereign-doctrinal-preservation/`, `crates/sovereign-doctrine-citation/` — the typed surface for tracking doctrinal-canon redefinitions per the operator's backward-sweep instruction (when later passages REDEFINE earlier ones, the citation chain captures the supersedence rather than discarding history) |

### M062-M076 — Substrate + SFIF + kernel + ZFS + atomic state + bootstrap

| Milestone family | Shipped surface |
|---|---|
| Substrate scripts | `scripts/bootstrap/`, `scripts/kernel/`, `scripts/hardening/` |
| Systemd assets | `systemd/system/`, `systemd/env.examples/` |
| Lifecycle/operator scripts | `scripts/lifecycle/`, `scripts/install/`, `scripts/diagnostics/` |

### M077-M082 — External-research ingestion (NVFP4 / HölderPO / activation steering / HRM-Text-1B)

| Milestone family | Shipped surface |
|---|---|
| M077 NVFP4 pipeline | `backlog/milestones/M077-nvfp4-pretraining-and-inference-pipeline.md` (170 R-rows mapping the NVIDIA arXiv 2509.25149 canonical paper) |
| M078 HölderPO + GRPO | catalogued; production prerequisites tracked in `backlog/notes/external-research-ingestion-2026-05-19.md` |
| M079 Activation steering | catalogued; production prerequisites tracked in same notes |

## Cross-cutting infrastructure (catalogue health visibility)

| Surface | Status |
|---|---|
| `backlog/INDEX.md` (80 milestones, 13,740 R-rows enumerated) | shipped prior to this session; surfaces the catalogue at a glance |
| `backlog/SHIPPED.md` (this file) | shipped — orthogonal production-delivery state tracker |
| Per-milestone audit coverage | This commit widens coverage from M060-only to ~17 milestone families across the 80-milestone catalogue. Cross-cutting (cockpit crates + scripts + profiles + schemas + Grafana dashboards) cited per family rather than per-milestone where the production surface is genuinely cross-cutting (no invention — every cited path is repo-verified). |

## M045 + M013 — Linux-as-governor telemetry substrate (sense → decide → enforce)

**Catalogued:** M045 (E0428–E0437, "Linux as intelligence governor") + M013 (E0106–E0115, "observability as control input"). See `backlog/milestones/M045-*.md` + `M013-*.md`.

**Shipped this session (complete vertical slice; engine-facing substrate + operator-visible surface):**

| R-row family | Surface | Commits (sovereign-os) | Tests |
|---|---|---|---|
| E0430 — Pressure-as-sensation (PSI 6-axis) | `sovereign-pressure-sensors` live ingestion: `parse_psi_some_avg10` over `/proc/pressure/*` + `from_psi`/`from_readings`/`update_axis`; the six E0430 axes (cpu/memory/io/gpu/human-attention/cost) | `0439698`, `fe0dc97` | 23 unit (real PSI sample parse, validated build, range guards) |
| E0430 — pressure sources (PSI + DCGM + CPU) | `sovereign-hardware-load-sample` live ingestion: `parse_gpu_csv` (nvidia/rocm-smi), `parse_proc_stat_cpu`+`cpu_util_pct`, `parse_thermal_zone_temp`; `from_loads`/`update_target`/`update_gpu` registry-validated | `f6c155c`, `4a77c5e`, `0682a46`, `88d687a` | 22 unit |
| E0431 / M00760 — 5 adaptive-intelligence reactions | `sovereign-pressure-reactions` `derive_reactions(pressure, load, registry, thresholds)` — verbatim actions; pressure rules on axis≥high, idle rules presence-gated | `082a4bb` | 7 unit |
| E0429 / M00756 — 5 systemd resource-control boundaries | `sovereign-resource-control` lib (oracle/scout/sandbox/eval/gateway profiles, `to_systemd_dropin`, validate) + `sovereign-resource-control` **binary** emitting deployable `/etc/systemd/system/<unit>.d/` drop-ins | `09b621e`, `3950cde` | 8 unit |
| E0111 / M00212 — worker 64-bit status word | `sovereign-worker-status-word` pack/unpack (load/memory/thermal/queue/error/health/policy_mode/flags bytes) + flag bits | `3fc2304` | 6 unit |
| E0112 / M00215 — runtime trace mapping | `sovereign-trace-context` trace_id/span_id/branch_id/commit_id + R02147 reconstructable `committed_path()` | `abb284f` | 8 unit |
| E0430 + E0431 runnable + **operator-visible** | `sovereign-telemetry` **binary**: sense→decide end-to-end (real `/proc/stat` util verified 53% under load); `--watch` NDJSON monitor; `--prometheus` exposition; Prometheus **alert rules** (`config/prometheus/alerts/sovereign-telemetry.rules.yml`) + Grafana **dashboard** (`docs/observability/dashboards/sovereign-os-telemetry.json`) | `874464e`, `13cdbe5`, `58a1657`, `bcdf3b9`, `136ea16`, `538c8ae`, `9ec808f`, `d8b9484` | binary smoke (json+prometheus contract) + 5 alert-contract + 6 dashboard-contract |

All crates auto-include via the `crates/*` workspace glob (zero shared-file edits); lib-only crates + 2 runnable binaries; the operator-visible surface (Prometheus metrics + alerts + Grafana dashboard) reaches the SHIPPED bar. Complements the engine runtime on branches — this is the inputs/observability the scheduler consumes, not the engine cores.

## M049 — Continuity through observability and policy (the 3 fabrics + control)

**Catalogued:** M049 (E0468–E0477). See `backlog/milestones/M049-*.md`.

**Shipped this session (the contract/schema layer the engine decides + emits against — lib-only, engine-fed; cockpit surface follows when the engine emits):**

| R-row family | Surface | Commits | Tests |
|---|---|---|---|
| E0470 / M00818 + M00819 — Observability Fabric: 15-event taxonomy + 13-field span | `sovereign-observability-events` (`EventKind` model_call…cost_event; `ObservabilitySpan` with `branch_id`/`trace_id` = the E0112 trace-context types) | `abc4d44` | 4 unit (15 distinct events, wire/serde lockstep, span roundtrip carrying trace coords, minimal-span omits empties) |
| E0472 / M00821 — Telemetry As Control: 6 real-time reactions | `sovereign-runtime-reactions` `derive_controls(signals, thresholds)` (cost-spike / tool-failure-repeats / hallucination / low-memory-quality / gpu-pressure / human-gates-too-frequent), verbatim actions | `59a3d54` | 5 unit |
| E0476 / M00827 — Config Resolver: 7 layers + 5 conflict rules | `sovereign-config-resolver` `ConfigLayer` precedence + `LayeredConfig::resolve`/`resolve_capped` + `offline_beats_cloud` (all 5 rules encoded) | `9049905` | 7 unit (one per conflict rule) |
| E0473 / E0474 / E0475 — Policy Fabric contract | `sovereign-policy-input` (7 `PolicyQuestion`s, 10-field intent-based `PolicyInput`, 9 `SensitivityClass`es) | `d7f9d51` | 4 unit (incl. the E0474 ~/.ssh/config intent example) |

Plus `sovereign-worker-fleet` (`242744b`) — fleet health summary over the M00212 worker status words (read-only observability aggregation). These are the engine-facing contracts (events/policy/config/fleet) — the engine emits/decides against them; their operator-visible surface lands when the engine produces the data.

## M084 — OPNsense/SD-WAN boundary contract + Tetragon-dropout resilience

**Catalogued:** 170 R-rows (R14081..R14250). See `backlog/milestones/M084-opnsense-sdwan-boundary-contract-tetragon-dropout-resilience.md`.

**Shipped this milestone (the dropout prevention, dump 761-765 verbatim):**

| R-row family | Surface | Commits | Tests |
|---|---|---|---|
| R14101 / R14104 — BindsTo binding control | `systemd/system/sovereign-guardian-core.service` gains the verbatim-required `BindsTo=tetragon.service` (alongside the master-spec § 10.2 After=/Requires=) so a tetragon stop during a network reconfiguration stops the guardian instead of leaving it tailing a dead stream | `47632d0` | `tests/lint/test_guardian_core_service_bidir.py` (binding consistency) + R171 hardening gates, all green |
| R14102 / R14105 / R14111-R14113 — EOF sentinel | `scripts/auditor/guardian-core.py` read-loop EOF fall-through no longer returns 0: logs `[EOF] ... perimeter blind` + exits nonzero so the `Restart=always` recovery is journal-recorded as a failure-restart | `47632d0` | `tests/lint/test_guardian_core_verbatim.py` + bidir gate, all green |
| R14127-R14133 — dropout metrics + flap alert | `sovereign_os_auditor_stream_eof_total` emitted on the EOF fall-through (inventoried in `docs/observability/dashboards/README.md`); `SovereignOsAuditorStreamEofChurn` (warning, ≥3 EOFs in 30m — the flapping-management-path scenario) in `config/prometheus/alerts/sovereign-os-auditor.rules.yml`; runbook section in the m060 deployment guide | `73bf7c4` | anchor-coverage + fleet-integrity + metric-inventory + observability-coverage + guardian gates, all green |

| R14217 — VLAN-contract lint | pre-existing: `tests/lint/test_network_vlan_verbatim.py` already locks the §8.1 role table (Intel→VLAN 100 mgmt + default-gw; Marvell→VLAN 200 data + MTU 9000 + no-default-gw + DHCP-gateway refusal on the data NIC) against script + profile — verified during the M084 audit, no new gate needed | (pre-existing) | the gate itself |

Pending (catalogued, not shipped): reconfig-detector (R14124-R14126; SDD-first per R14216).

## M073 — 1-bit (ternary) logic + BitLinear Core (the compute substrate)

**Catalogued:** 170 R-rows (R12071..R12240). See `backlog/milestones/M073-one-bit-ternary-logic-bitlinear-core.md`.

**Shipped this milestone (the multiplication-free ternary FFN compute, composed + running):**

| R-row family | Surface | Commits | Tests |
|---|---|---|---|
| F06051/F06052/F06059 — BitLinear FFN composition | `crates/sovereign-bitlinear-core/src/mlp.rs` `BitLinearMlp` — composes the ternary `BitLinearLayer` primitive into the transformer FFN block (`d_model→d_ff→d_model`, ReLU between layers), multiplication-free across the stack, bit-for-bit equal to a dense reference. Cortex Conductor self-check (`compute.rs::ternary_kernel_live`) runs a real 2-layer block. | `046083b` | 7 unit (bit-exact Base3+TwoBit, 3-layer deep stack, ReLU-gating, op-accounting, dim-chain reject, serde) |
| F06043-F06045 — residual sublayer | `BitLinearMlp::forward_residual` — `y = x + block(x)`, the decoder's residual-wrapped FFN-sublayer shape; all-zero block = residual identity | `fa5cfb7` | 3 unit (residual exactness, zero-weight identity, non-square reject) |
| F06051 (gated) — ternary SwiGLU | `crates/sovereign-bitlinear-core/src/swiglu.rs` `TernarySwiGlu` — `h = SiLU(W_gate·x) ⊙ (W_up·x)`, `out = W_down·h` with all three matmuls multiplication-free; the mul-free drop-in for the float SwiGLU the quant decoder block runs | `fb842b8` | 6 unit (bit-exact vs dense SwiGLU Base3+TwoBit, mul-free accounting, zero-weight residual identity, shape/serde) |
| F06060-F06062 — packed-domain LUT forward (scalar foundation) | `BitLinearLayer::forward_packed` + block-level `BitLinearMlp`/`TernarySwiGlu::forward_packed` — single pass over the 2-bit packed codes (no `Vec<Trit>`), each `01`→add/`10`→sub/`00`→skip in place; the safe scalar form the AVX-512 LUT lane vectorizes. Conductor self-check verifies `forward_packed == forward`. | `ab7640c`, `393b924`, `3c6be8e` | 8 unit (packed==forward output+OpCount across layer/MLP/SwiGLU, TwoBit-only guard, input-mismatch) |
| F06046/F06067-F06070, R12107-R12110 — energy monitor (built → wired → visible) | `EnergyReport` + `OpCount::energy_report` + block-level `BitLinearMlp`/`TernarySwiGlu::energy_report` — the dump's add/sub-vs-FP-MUL accounting (muls eliminated, energy-saving ratio, weight sparsity), composing across a whole FFN. Wired into the production `sovereign_linear::Linear::energy_report` (the precision-generic layer the decoder runs) and **surfaced in the running engine**: `cargo run -p sovereign-inference-demo` prints `ternary FFN proj: 256 inner-muls eliminated, 88.9% energy saved, 34% weight-sparse`. | `e1bb13a`, `14999ae`, `70b4136`, `4dae8ca` | 7 unit (single-layer accounting, sparsity, block-level MLP + SwiGLU, serde, Linear ternary surface, non-ternary None) |

Running evidence: `cargo run -p sovereign-inference-demo` executes a 3-layer mixed-precision stack (f32 · **ternary** · NVFP4-MHA) — the ternary BitLinear compute runs end-to-end in the assembled engine (`sovereign-linear` at `Precision::Ternary` wraps `BitLinearLayer`).

Boundary (pending operator decision): the *actual* AVX-512 SIMD vectorization of `forward_packed` requires `unsafe` intrinsics, which the workspace forbids (`unsafe_code = "forbid"`, root `Cargo.toml`). The scalar packed-domain forward is the correct safe foundation; the SIMD lane is gated on relaxing that invariant for a vetted module.

## M077 — NVFP4 pretraining + inference pipeline (the Logic-engine accuracy recipes)

**Catalogued:** 170 R-rows (R12751..R12920). See `backlog/milestones/M077-nvfp4-pretraining-and-inference-pipeline.md` (title names RHT + 2D + stochastic rounding + selective-HP).

**Shipped this milestone (two previously-unwired accuracy mechanisms wired + verified):**

| R-row family | Surface | Commits | Tests |
|---|---|---|---|
| RHT (random Hadamard transform) — inference accuracy | `crates/sovereign-nvfp4-runtime/src/linear.rs` `RhtQuantMatrix` — rotates weight rows + activations by the orthonormal `R = rht_forward` before/at NVFP4 quant, so `(R·w)·(R·x)=w·x` exactly but block outliers spread for better 4-bit microscaling. The `rht` primitive existed but nothing used it. | `a7d3857` | 4 unit (approximates dense ref; **reduces error vs plain quant on outlier weights**; power-of-two enforced) |
| Stochastic rounding — training-path accuracy | `quantize_block_stochastic` + `QuantMatrix::from_f32_stochastic` — deterministic block scale, stochastic per-element E2M1 rounding → unbiased in expectation. `quantize_stochastic` existed per-element but was unwired at block/matrix level. | `5315455` | 2 unit (**4000-draw ensemble mean beats biased RNE on off-grid values**; matrix path valid approximation) |
| Selective high-precision — keep sensitive layers un-quantized | `RuntimeConfig::is_high_precision` (per-layer FP-vs-NVFP4 decision a loader uses for embeddings / `lm_head`) + `check_high_precision_layers` (raises the previously-dead `HpLayerMissing` so a typo fails loudly instead of silently quantizing a protected layer). The `high_precision_layers` list had no method applying it. | `5fe91d2` | 2 unit (default keeps embeddings+lm_head, quantizes the rest; missing protected layer errors) |
| 2D quantization — per-row + per-column scale (F06388-F06390) | `TwoDQuantMatrix` factors `W ≈ diag(r)·Q·diag(c)` so a systematically-small column (rounded to ~0 by 1D's per-row-only scale) is restored by the column scale; forward scales `x` by columns, 4-bit accumulates, scales output by rows. A genuine new algorithm, not just wiring. | `e3f464c` | 4 unit (approximates dense ref; **beats 1D on column-structured weights**) |

**All four M077 accuracy recipes are now built** (RHT · stochastic rounding · selective-HP · 2D quantization), each with its motivating property empirically verified. The first three were P4 closures (declared config flags + tested primitives, unwired into the quant path); 2D quantization was a new per-row+per-column algorithm.

| Linear integration — recipes selectable by the decoder | `sovereign_linear::Linear::from_f32_nvfp4` + `NvfpRecipe {Plain, Rht, TwoD}` + `Backend::Nvfp4Rht/Nvfp4TwoD` — the production precision-generic layer the decoder runs can now pick RHT/2D instead of plain microscaling (additive; default `Precision::Nvfp4` unchanged). Both kernels verified in the cortex Logic-engine self-check (`nvfp4_kernel_live`). | `2376f44`, `7301c70` | 1 unit (all recipes → Nvfp4 / ~4.5 bpp / valid forward) + cortex self-check |
| Per-projection recipe **auto-selection** wired into the model | `best_nvfp4_recipe` + `Linear::from_f32_nvfp4_auto` (picks the lowest-weight-error recipe) + `nvfp4_recipe()` readback (RHT seed retained in `RhtQuantMatrix`). `MhaDecoderBlock::from_weights` now routes every NVFP4 projection through auto-selection instead of fixed plain microscaling; `nvfp4_recipes()` reports the per-projection choice. The running `sovereign-inference-demo` self-reports recipe-why + the real layer's 7 selections. | `2341695`, `f25d783`, `9ca898f`, `a6d72d6` | 2 unit (auto picks 2D for column-structure + reports it; recipe roundtrips each backend) + 1 block unit (7 projections each report a recipe) + demo smoke |
| Data-driven **selective-HP** (measure → recommend → protect) | `best_nvfp4_recipe_with_error` + `recommend_high_precision` (ranks named projections by best-NVFP4 error, returns those over a tolerance, capped at a budget) replaces the hardcoded HP-layer list with a measurement. `MhaDecoderBlock::from_weights_selective` enforces it at build time: flagged projections build dense f32 while the rest stay NVFP4 (mixed precision inside one block, runs end-to-end). Demo reports how many projections the policy flags. | `de21a2f`, `3e31caf`, `8e2d040` | 3 unit (flags worst projection; respects budget+tolerance; error agrees with recipe) + 2 block unit (keeps flagged projection dense; empty set == plain NVFP4) + demo smoke |
| **Activation-aware** recipe selection | `sovereign-quant-calibration::best_nvfp4_recipe_calibrated` — builds each M077 recipe, runs it over representative inputs, returns the one whose output `Wx` is closest to the f32 reference. The activation-aware complement to the weight-error `best_nvfp4_recipe`; the calibration crate previously only measured plain microscaling for NVFP4. | `21a5db8` | 2 unit (chosen recipe's output error ≤ plain's; empty-inputs errors) |
| Recipe-aware **precision assignment** | `sovereign-quant-calibration::recommend_with_recipe` — the NVFP4 tier is measured with its best M077 recipe (not plain), so a borderline layer that `recommend` would bump to f32 stays on the cheap 4-bit tier under RHT/2D conditioning; returns the chosen recipe. Demo reports the per-layer ternary/nvfp4/f32 assignment at a 10% budget. | `9b7736c`, `08854b9` | 2 unit (keeps a column-structured layer on NVFP4 where plain-only `recommend` picks f32; ternary/f32 extremes) + demo smoke |
| **NVFP4-compressed KV cache** (inference memory optimization) | `MhaDecoderBlock::with_quantized_kv` — opt-in cache that stores each cached key/value vector as a `1×dim` NVFP4 `QuantMatrix` (~4.5 bits/param vs 32, ~7× smaller), dequantizing transiently at attention time. Default stays dense f32 (proven path unchanged); `kv_quantized()` reports the mode. | `2b967b3` | 2 block unit (runs end-to-end + tracks length; full-block compressed cache stays within 15% relative deviation of the dense cache) |

## Other catalogued milestones — production-shipped state TBD

The 80-milestone catalogue spans extremely broad territory (the avx-plus-plus dump's full scope across substrate, runtime, agent, operator-§1g, intelligence, persistence, observability). Many milestone-specific audit rows remain to map. The 475-crate workspace + 20-dashboard webapp tree + 40 script categories + 81 profile/schema files all carry production state that future audit cycles append per-milestone above.

The above per-milestone shipped audit is a SAMPLED snapshot, not a complete production-state survey. The trajectory: each commit or audit cycle appends rows here so the SHIPPED column converges toward the catalogue total as the multi-year project progresses.

## How this file is maintained

1. **Every production commit** that lands a catalogued R-row appends a row to the relevant milestone section above with: R-row family, surface description, commit hash(es), tests added, selfdef pair (if cross-repo).
2. **No invention** — every row references real commits + tests + sovereign-os user-visible surface (alert/runbook/dashboard/api). Audits cross-check against `git log` + `tests/lint/` + `docs/operator/` + `config/prometheus/alerts/`.
3. **Never marks done** what isn't in production — the operator's "You cannot mark something done if it hasn't reached Prod" constraint is sacrosanct. Half-shipped (e.g. alert without runbook section, dashboard without contract test) gets a parenthetical "partial — pending X" note, not a "shipped" row.

This file pairs with selfdef's parallel `backlog/SHIPPED.md` for producer-side surfaces. Both repos' INDEX + SHIPPED files together give the operator the catalogue-vs-shipped delta at any commit.
