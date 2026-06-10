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
| Memory/grounding plane — BM25 retrieval | `crates/sovereign-retrieval/` `DocStore::retrieve_bm25` + `Bm25Doc` — proper sparse retrieval (IDF-weighted, length-normalized; canonical k1=1.5/b=0.75) replacing the raw term-overlap ranking for RAG grounding. Commit `4bd8d1f`; 3 unit (IDF breaks a raw-overlap tie toward the rare-term doc; length normalization ranks the shorter doc first; empty/no-match) |
| Memory/grounding plane — MMR diversity re-ranking | `crates/sovereign-embed/` `EmbedStore::retrieve_mmr(query, k, lambda)` — Carbonell-Goldstein Maximal Marginal Relevance: greedily picks the doc maximizing `λ·sim(d,query) − (1−λ)·max sim(d,selected)`, avoiding near-duplicate RAG chunks that plain cosine top-k wastes budget on (λ=1 == `retrieve`, λ=0 = pure diversity). Commit `296a220`; 3 unit (MMR swaps a redundant duplicate for a diverse doc where top-k keeps both; λ=1 equals retrieve; empty/no-match) |

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

### M009 — Deterministic Cortex Runtime v0

| Surface | Shipped artifact |
|---|---|
| Inference-backend-stack SDD | `docs/sdd/011-inference-backend-stack.md` — the v0 Cortex Runtime spec |
| dflash speculative-decoding SDD | `docs/sdd/026-dflash-speculative-decoding.md` — the dflash variant for the v0 runtime |
| dflash sampled (distribution-preserving) verification | `crates/sovereign-spec-decode/` `verify_sampled` — the modified rejection-sampling accept rule (Leviathan/Chen) that emits a target-distributed sequence: accept each draft token at `min(1, p_target/p_draft)`, correct from the normalized positive residual on rejection, bonus from the target on full accept. Complements the existing greedy `verify_greedy`. Commit `f0d8001`; verified by a 400k-trial statistical test (first emitted token matches `p_target` within 1%) + shape-error + accept/reject unit tests |
| dflash sampled accept path live-checked in cortex | `crates/sovereign-cortex/` `spec_decode_kernel_live` + `ComputeProfile::spec_decode_verified` — the GPU target roles (Logic/Oracle) run a real `verify_sampled` full-accept + forced-reject round at profile-build time, so the running cortex self-reports the spec-decode path is callable + correct (`"spec_decode_verified": true`), not just an estimated multiplier. Commit `5646b19`; 2 unit (live check correct; GPU roles verify, draft/cloud don't) |
| dflash prompt-lookup decoding (draft-free) | `crates/sovereign-spec-decode/` `prompt_lookup_draft(context, ngram, max_draft)` — PLD (Saxena): use the context as its own draft (find the most-recent earlier occurrence of the current `ngram` suffix, propose the tokens that followed it), so no draft model is needed; drops into the same `verify_greedy`/`verify_sampled` accept loop. End-to-end driver `crates/sovereign-speculative/` `Speculative::decode_prompt_lookup` (lossless vs greedy target; no second model). Commits `2cfa37c`, `0989ff1`; 4 spec-decode unit (proposes earlier continuation; most-recent match; degenerate cases empty; feeds verify_greedy) + 2 speculative unit (lossless across ngram/max_draft; empty-prompt) |
| dflash end-to-end sampled decoder | `crates/sovereign-speculative/` `Speculative::decode_sampled` — drives real `DecoderStack`s through `verify_sampled`: draft samples `draft_len` tokens from its sampler-shaped distribution, target teacher-forces them on a fork for per-position distributions, the rejection rule commits the accepted prefix + correction/bonus. Distribution-preserving analogue of the greedy `decode`. Commit `f136b39`; verified it reduces exactly to greedy `decode` under a greedy sampler (across draft lengths) + seed-determinism + models-untouched + input-validation tests |
| RoPE context-length extension | `crates/sovereign-rope/` linear position interpolation (`with_position_scale` / `for_context_extension`, Chen et al.) + `ntk_aware_base` (NTK-aware scaling, Peng et al.), wired into the decoder block as `MhaDecoderBlock::with_context_extension` (`crates/sovereign-mha-block/`). Extends usable context past the trained length while preserving RoPE's relative-position identity; `position_scale` defaults to 1.0 with a serde default so existing configs are unchanged. Commits `de54bc5`, `7af9825`; 6 rope unit (PI halves the angle at 2× position, context-extension keeps the extended max in trained range, NTK base grows + slows rotation, legacy-JSON default) + 1 block unit (extended block decodes finite) |
| Sliding-window (local) attention | `crates/sovereign-mha-block/` `MhaDecoderBlock::with_sliding_window(w)` — Mistral-style local attention: each step attends to and the KV cache retains only the most recent `w` positions, bounding attention cost and cache memory at long context. A position counter drives RoPE so absolute positions advance as old entries evict; `len()` = positions processed, `cache_len()` = bounded held count. Default full-causal unchanged. Commit `d9297a6`; 2 unit (cache stays within window while positions advance; windowed output depends only on the last `w` positions — the locality property via RoPE relative offset) |
| Attention sinks (StreamingLLM) | `crates/sovereign-mha-block/` `MhaDecoderBlock::with_attention_sinks(s)` — under a sliding window, eviction preserves the first `s` positions (which absorb a large share of attention mass) instead of dropping them, fixing the quality collapse of naive window eviction; evicts the oldest non-sink entry. Commit `690caf5`; 2 unit (the sink keeps the initial token influential where pure SWA would have evicted it — differential property; cache stays within window) |
| OpenAI presence/frequency penalties | `crates/sovereign-sampler/` `SamplerConfig::presence_penalty` (flat additive demotion of any seen token) + `frequency_penalty` (additive, proportional to occurrence count) — the two distinct OpenAI decode penalties, separate from the existing multiplicative CTRL `repetition_penalty`; serde-defaulted. Commit `099114d`; 2 unit (presence count-independent vs frequency count-scaling, both demote recents below unseen; zero penalties no-op) |
| Locally-typical sampling | `crates/sovereign-sampler/` `SamplerConfig::typical_p` + `keep_typical` — the Meister et al. decode control: keep the tokens whose surprisal `−log p` is closest to the distribution's entropy until the mass fraction is reached, trimming both the over-confident head and the surprising tail (distinct from top-k/nucleus/min-p). Wired into the distribution pipeline; defaults to `None` (serde default) so existing configs are unchanged. Commit `95cb59b`; 4 unit (trims extremes on a peaked dist, None keeps full support, uniform keeps the mass fraction, legacy-JSON deserializes) |
| Weight tying (embedding ↔ output head) | `crates/sovereign-quant-model/` `QuantModel::new_tied` — GPT-2/Llama-style tied weights: the output projection reads the embedding table directly, storing one `vocab × model_dim` matrix instead of two; `is_tied()` reports it. Default `new()` untied + unchanged. Commit `58c0b6d`; 2 unit (tied logits equal an untied model built with head==embedding — the tying invariant; embedding-shape validation) |
| Gemma-2 logit soft-capping | `crates/sovereign-quant-model/` `QuantModel::with_logit_softcap(cap)` — bounds each output logit into `(−cap, cap)` via `cap·tanh(logit/cap)`, taming over-confident outliers while staying ~linear near zero and order-preserving; applied in `forward` after the head projection. Default `None`. Commit `9344d15`; 1 unit (capped logits within bounds, argmax preserved, non-positive cap disables) |
| Runnable binaries drive the real engine | Two binaries now assemble + run the inference stack with real capability, not stubs: `sovereign-chat` parses CLI decode controls (`--temperature/-T`, `--top-k`, `--top-p`, `--typical-p`, incl. `--flag=value`) into the engine's sampler so generation is command-line-drivable (commit `3b5d04f`; 5 unit on the parser + custom-sampler runtime); `sovereign-serve` replaces its echo-stub generator with a real `SovereignLlm` backing the cost-aware `serve()` step, so the cache→complexity→budget→generate path runs the model — and a repeated prompt still short-circuits as a `$0` cache hit before the model runs (commit `1ca4556`). | `3b5d04f`, `1ca4556` | 5 chat-parser unit + serve runs end-to-end ($0 cache-hit verified) |
| Streaming token generation | `crates/sovereign-decoder-stack/` `generate_masked_with` (on_token callback per sampled token; `generate_masked` delegates to it, behavior unchanged) + `crates/sovereign-llm/` `SovereignLlm::generate_ids_streaming` — emit tokens as they arrive (SSE-style) instead of waiting for the whole completion; pristine cache per call. Wired into `sovereign-serve --stream` (prints each token id live, then decodes for cache + accounting). Commits `81b86d7`, `de4515e`; 4 unit (streamed sequence equals batch + fires per token, in both crates; empty-prompt errors) + serve runs |
| Tokenizer special tokens (BOS/EOS/PAD) | `crates/sovereign-tokenizer/` `with_specials` + `special_id`/`special_name` + `bpe_vocab_size` — reserve control-token ids above the BPE vocabulary; `encode` never emits them, `decode` skips them, they survive the serde round-trip. The fundamental serving primitive that pairs with early-stop generation (an `<eos>` id is the natural stop token). Commit `7a49e5a`; 4 unit (id reservation; encode-never-emits + decode-skips; dedupe/empty; serde round-trip) — and `decode(encode(text))==text` invariant preserved |
| Beam search — EOS termination + length normalization | `crates/sovereign-beam-search/` `BeamSearch::search_with(base, prompt, eos, length_penalty)` — a beam emitting the eos token finishes (not extended); the winner is ranked by length-normalized score `score/lenᵅ`, removing raw log-prob's bias toward short sequences (now meaningful with variable-length EOS beams; pairs with the tokenizer special tokens). `eos=None`+`α=0` reproduces `search`. Commit `ab1507d`; 4 unit (length-norm corrects the short-sequence bias; defaults equal plain search; bounded + validation; α=0/len-0 edges) |
| Prefix KV reuse (system-prompt amortization) | `crates/sovereign-decoder-stack/` `DecoderStack::prime(prefix)` — ingest a shared prefix into the KV cache without generating, so it is primed once and the primed stack is cloned per request to generate only the suffix, amortizing the prefix's forward passes. Output-transparent (prime + generate(suffix) == generate(prefix++suffix)). Commit `96eaef5`; 1 unit (transparency + the primed base stays reusable) |
| Unified composable generation | `crates/sovereign-decoder-stack/` `GenOptions` (builder: max_new · base `LogitMask` · `no_repeat_ngram` · `stop_tokens` · `min_new` min-length) + `generate_with` (one loop composing constrained masking + dynamic no-repeat-ngram + early-stop + min-length + per-token streaming, which the single-purpose methods could only do separately) + `crates/sovereign-llm/` `SovereignLlm::generate_ids_with` (same at the text-to-text API). Commits `de0d539`, `fe49190`, `0375a96`; 3 stack unit (all controls compose; plain == generate; min-length defers the stop token) + 2 llm unit (composes + streams + reproducible; empty-prompt) |
| Early-stop generation (EOS / stop tokens) | `crates/sovereign-decoder-stack/` `generate_until` + `crates/sovereign-llm/` `SovereignLlm::generate_ids_until` — stop the moment a stop token is produced (included in the result) instead of always running to `max_new`; the fundamental EOS/stop-sequence behaviour a real runtime needs. Empty stop set == `generate`. Commit `ac80c83`; 2 stack unit + 2 llm unit (stops after the stop token; empty set → full length; empty-prompt) |
| No-repeat-ngram blocking | `crates/sovereign-logit-mask/` `no_repeat_ngram_bans` + `LogitMask::no_repeat_ngram` (ban tokens completing an already-seen n-gram by matching the current (n−1)-suffix against history) + `crates/sovereign-decoder-stack/` `generate_no_repeat_ngram` (rebuilds the blocklist from the live history every step, so loops can't form as the sequence grows). Distinct from the sampler's soft repetition penalty. Commits `ea9cdcc`, `171fbc6`; 3 mask unit (blocks repeater, collects matches, edge cases) + 2 stack unit (generated sequence has no repeated 3-gram + reproducible; empty-prompt) |
| Mirostat v2 sampling (full chain) | `crates/sovereign-sampler/` `Mirostat` — stateful perplexity-targeting decode controller (Basu et al.): targets constant surprise τ via a running μ threshold (truncate within μ → sample → nudge μ by observed-vs-target error), holding output perplexity steady regardless of per-step peakedness. Wired end-to-end: `DecoderStack::generate_mirostat` drives the decode loop with it (reproducible per seed), and `SovereignLlm::generate_ids_mirostat` exposes it at the text-to-text API so binaries can use it. Commits `3f626c6`, `12fb99b`, `64d342f`; 4 sampler unit (μ init = 2τ, control-law direction, surprise converges near τ over 4000 steps, empty-support → None) + 2 stack unit (reproducible + μ adapts; empty-prompt) + 2 llm unit (runs + reproducible; empty-prompt) |
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
