% SOVEREIGN-OSCTL-OPERATIONS(1) sovereign-os 0.3.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-operations - operations, observability, and recovery

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

System status, diagnostics, maintenance, metrics, alerts, journals, histories, snapshots, notifications, dashboards, and daily operator workflows.

This page owns 39 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. The synopsis and descriptions are grounded in the
command handler or delegated-script contract at this build revision.
The top-level help is a discovery summary, not an exhaustive grammar.

# SAFETY MODEL

Most inspection verbs are read-only. Maintenance, snapshot, restore, notification, service, and remediation verbs may require root or explicit apply gates. Preserve command output when escalating an incident.

Read-only discovery should precede mutation. JSON output, when offered,
is the stable surface for automation; human output is intended for direct
operator use.

# COMMON WORKFLOW

1. Confirm the installed revision with **sovereign-osctl version**.
2. Inspect the relevant **status**, **show**, **list**, **info**, **plan**,
   or **doctor** surface.
3. Save machine-readable output when `--json` is available.
4. Review profile, device, backend, policy, and target selection.
5. Apply the smallest scoped mutation, then re-run health/status.

# EXAMPLES

    sovereign-osctl status --json
    sovereign-osctl doctor
    sovereign-osctl alerts --json
    sovereign-osctl journal errors
    sovereign-osctl maintenance list
    sovereign-osctl commands --json
    sovereign-osctl help thermals
    sovereign-osctl completion zsh > ~/.zfunc/_sovereign-osctl

# COMMAND REFERENCE

## status

**sovereign-osctl status [--json]**
:   System state overview (--json for fleet aggregation)

## overview

**sovereign-osctl overview [--json]**
:   Show a consolidated snapshot of pipeline phases, bootstrap verification, Trinity state, model residency, active profile and whitelabel, kernel, and Tetragon perimeter.

## doctor

**sovereign-osctl doctor**
:   Sanity checks across the system

## assistant

**sovereign-osctl assistant [<sub>]**
:   First-login assistant: full | status | reset | list

## commands

**sovereign-osctl commands [--json]**
:   List every registry-owned top-level command, grouped by manual topic. Use
    `--json` for a stable machine-readable inventory or `--format words` for
    completion integrations.

## completion

**sovereign-osctl completion {bash|zsh|fish}**
:   Emit shell completion generated from the same command-topic registry used
    by **commands** and contextual **help**. The installed completion files are
    generated from this interface during `make install`.

## maintenance

**sovereign-osctl maintenance list**
:   List on-demand maintenance subverbs

**sovereign-osctl maintenance scrub**
:   Trigger ZFS scrub now

**sovereign-osctl maintenance arc-status**
:   Show ZFS ARC stats

**sovereign-osctl maintenance log-rotate**
:   Rotate ~/.sovereign-os/log/*.jsonl now

**sovereign-osctl maintenance snapshot**
:   Take tank/context ZFS snapshot now

**sovereign-osctl maintenance security-check**
:   Scan for pending security updates now

**sovereign-osctl maintenance models-sync**
:   Verify resident model catalog now

**sovereign-osctl maintenance perimeter-check**
:   Verify Tetragon perimeter policy now

**sovereign-osctl maintenance alerts-check**
:   Derive alerts + emit meta-counters now

## trinity

**sovereign-osctl trinity status**
:   Master spec § 17 — Pulse · Weaver · Auditor at a glance

**sovereign-osctl trinity pulse**
:   Vector Core layer (AVX-512 · bitnet.cpp · CCD0)

**sovereign-osctl trinity weaver**
:   Sandboxed Fabric layer (Podman · VFIO · state fabric · CCD1 0-9)

**sovereign-osctl trinity auditor**
:   Immutable Gatekeeper layer (Tetragon · Guardian · always-on)

**sovereign-osctl trinity watch**
:   R513 refresh-loop TUI (Pulse · Weaver · Auditor at a glance)

**sovereign-osctl trinity profile list**
:   List runtime profiles (master spec § 18)

**sovereign-osctl trinity profile show <id>**
:   Detail a runtime profile (allocations · GPU state · power · observability)

**sovereign-osctl trinity profile active**
:   Show the currently-active runtime profile

**sovereign-osctl trinity profile switch <id>**
:   Switch to a different runtime profile

## env

**sovereign-osctl env list [--filter <regex>]**
:   List every SOVEREIGN_OS_* env var with its default

**sovereign-osctl env show <NAME>**
:   Detail one env var (default · all consumers · currently-set value)

## metrics

**sovereign-osctl metrics list**
:   List all sovereign_os_*.prom files in the textfile collector dir

**sovereign-osctl metrics show <basename>**
:   Pretty-print a single .prom file (resolves trailing .prom)

**sovereign-osctl metrics tail [N]**
:   Tail the N most-recently-updated .prom files (default: 5)

**sovereign-osctl metrics health**
:   Sanity-check the textfile collector dir (presence, age, format)

## alerts

**sovereign-osctl alerts [--json]**
:   Derive operator alerts from .prom files (no Alertmanager needed)

## journal

**sovereign-osctl journal list [--all-dirs]**
:   List Layer A JSONL log files (size + first/last event)

**sovereign-osctl journal show <file> [--all-dirs]**
:   Pretty-print one JSONL log file as a table

**sovereign-osctl journal tail [--all-dirs] [N]**
:   Tail the N most recent log files (default: 3)

**sovereign-osctl journal errors [--all-dirs]**
:   Show every error/warn entry across all log files

## history

**sovereign-osctl history list**
:   Per-run summary derived from JSONL files (profile · steps · result · duration)

**sovereign-osctl history show <run-id>**
:   Drill into one run (step-by-step pass/fail)

## diagnose

**sovereign-osctl diagnose run [--severity S] [--limit N] [--all] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl diagnose probes [--json]**
:   R266: list available sub-probes.

## next-steps

**sovereign-osctl next-steps next|packs|apply-pack [--severity S] [--limit N] [--json]**
:   See the handler for behavior and options.

## severity

**sovereign-osctl severity evaluate [--escalate-after-seconds N] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl severity state [--json]**
:   R273: dump current escalation state.

**sovereign-osctl severity reset [--confirm]**
:   R273: clear state file (operator-confirm).

## health

**sovereign-osctl health scan [--json] [--probe NAME]**
:   See the handler for behavior and options.

## insights

**sovereign-osctl insights [--threshold-bytes N] [--root D] [--limit N] [--all] [--json]**
:   See the handler for behavior and options.

## kernel

**sovereign-osctl kernel list [--json]**
:   R239 (SDD-026 Z-14): enumerate kernel-

**sovereign-osctl kernel show [--preset P] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl kernel apply <preset> [--dry-run] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl kernel cmdline-hints <preset> [--json]**
:   See the handler for behavior and options.

## services

**sovereign-osctl services list [--prefix P] [--state S] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl services failures [--json]**
:   R240: only units in failed state. rc=1

**sovereign-osctl services timers [--json]**
:   R240: next/last fire times via

**sovereign-osctl services shipped [--json]**
:   R240: catalog of units this repo

## events

**sovereign-osctl events timeline [--source S] [--since ISO] [--limit N] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl events summary [--json]**
:   R246: per-source counts + last-event

## notify

**sovereign-osctl notify dispatch [--from-file P] [--dry-run] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl notify test --channel C [--severity S]**
:   See the handler for behavior and options.

**sovereign-osctl notify list-channels [--json]**
:   See the handler for behavior and options.

**sovereign-osctl notify state [--json]**
:   R228: dump the dedup state file.

**sovereign-osctl notify send --message M [--severity S] [--title T]**
:   See the handler for behavior and options.

## dashboard

**sovereign-osctl dashboard serve [--bind HOST:PORT] [--once]**
:   See the handler for behavior and options.

**sovereign-osctl dashboard render**
:   R225: render the dashboard HTML to

**sovereign-osctl dashboard grid [--json] [--watch] [--interval SEC]**
:   See the handler for behavior and options.

## mcp-aggregate

**sovereign-osctl mcp-aggregate manifest [--upstream-selfdef H:P] [--config P] [--json|--human]**
:   See the handler for behavior and options.

**sovereign-osctl mcp-aggregate probe-upstream H:P [--timeout SECS] [--json]**
:   See the handler for behavior and options.

## self-test

**sovereign-osctl self-test {run|list}**
:   R331 (E9.M14): operator-pull self-test verb. Runs L1 lint suites + unit tests + curated L3 sample + emits health summary. "Is sovereign-os itself working correctly on this host?"

## next-action

**sovereign-osctl next-action {list|top}**
:   R329 (E2.M22): next-action advisor — composes R322 state snapshot + emits ranked operator-pull recommendations of most-impactful verb to run next. "What should I do now?" decision support.

## fleet-aggregate

**sovereign-osctl fleet-aggregate {aggregate|by-axis|outliers}**
:   R324 (E2.M20): fleet snapshot aggregator. Ingests R322 unified state snapshots from multiple hosts; emits cross-host rollup (per-axis verdict distribution, host-level summary, outlier detection). Operator-pull "how is my whole fleet doing?"

## maintenance-window

**sovereign-osctl maintenance-window {list|show|can-run-now|active}**
:   R323 (E2.M19): maintenance-window scheduler. Operator declares named time windows; other advisors / autohealth / heat-oc- throttle query can-run-now <window> before acting. Operator-named (§1b verbatim: "schedule/planifest/graceful on all levels, orderly").

## snapshot

**sovereign-osctl snapshot {snapshot|audit}**
:   R322 (E2.M18): unified state snapshot — runs all read-only advisors in parallel + emits one consolidated JSON document. Operator-pull "what's the COMPLETE state of this host right now?"

## module-state

**sovereign-osctl module-state {list|show|recommend}**
:   R351 (E2.M34): "what have I installed but not yet configured?" Operator-named §1b verbatim: "installs, non-configured, modules or features and how configure them". 16-module default catalog; per-module verdict (fully-configured / installed-not-configured / running-without-overlay / config-only-no-runtime / shipped-but- untouched) + the verb to close each gap.

## morning-brief

**sovereign-osctl morning-brief {rollup}**
:   R352 (E10.M2): meta-rollup composing R329 next-action + R351 module-state + R308 autohealth + R349 guide-suggestion into a single operator-readable "what should I look at first this morning?" report. NEVER-raise on missing sub-probes.

## network-topology

**sovereign-osctl network-topology [sub]**
:   R359 (§8+§8.1): operator-verbatim ASCII

## autohealth

**sovereign-osctl autohealth {tick|status|history|advisory}**
:   R308 (E2.M14): doctor / autohealth periodic synthesizer. Composes R226 (health-scan) + R296 (thermal-oc) + R298 (storage-health) + R300 (operator-posture) + R304 (memory- pressure-damper) into ONE tick that persists state + emits notify-dispatch commands when severity crosses threshold. Operator-named (§1b verbatim: "autohealth and doctor, notification and messaging").

## research-loop

**sovereign-osctl research-loop status [--config P] [--json|--human]**
:   See the handler for behavior and options.

**sovereign-osctl research-loop topics [--config P] [--json|--human]**
:   See the handler for behavior and options.

## traces

**sovereign-osctl traces [arguments]**
:   M060 D-05 (R10083-R10087): M049 13-field span store + query core — reads the observability fabric's append-only span log (/var/log/sovereign-os/spans.jsonl), filters by time window / text / severity / OCSF class (MS026 16-event taxonomy), assembles per-trace span trees. Read-only; the sovereign-traces-api daemon serves the D-05 cockpit dashboard from this same core. Verbs: spans / trace <id> / summary (+ --json, --window, --q, --severity, --ocsf-class).

## m060-health

**sovereign-osctl m060-health [arguments]**
:   M060 chain health observability — proxies the selfdef daemon's GET /v1/m060/health endpoint reporting publish-freshness of all 10 mirror artifacts (offline/degraded/stale/online plus this script's own "unreachable" when the daemon is down). Used by the D-00 master-dashboard's chain-health banner, the MCP tool selfdef-m060-health, and ops/smoke scripts. Read-only. Verbs: probe / state (+ --json).

## bashrc

**sovereign-osctl bashrc install**
:   R447 (E11.M6): install operator-discoverable

**sovereign-osctl bashrc uninstall**
:   Remove the sovereign-os bashrc block

**sovereign-osctl bashrc status**
:   Report install state (installed | absent)

**sovereign-osctl bashrc dump**
:   Print the block to stdout (pipe to

## ms022-doctor

**sovereign-osctl ms022-doctor [arguments]**
:   MS022 SSE subscriber-quota chain triage — probes the 4 consumer- side surfaces (proxy daemon, master-dashboard banner, systemd unit) against the selfdef-side producer state (selfdef commit 77b4499 6 gauges). Read-only (R10212 + R10115). Stdlib-only Python; no deps. Exit codes: 0=GREEN / 1=YELLOW / 2=RED. Flags: --strict requires state=ok everywhere; --json for machine-readable triage. See scripts/diagnostics/ms022-doctor.py --help for the full flag surface.

## m060-doctor

**sovereign-osctl m060-doctor [arguments]**
:   M060 cross-repo mirror chain smoke check — pings each /api/d-NN/snapshot endpoint through the sovereign-os master-dashboard proxy AND probes the selfdef-side doctor textfile observers (selfdef-cli-mirror-doctor.timer + selfdef-m060-doctor.timer, selfdef commits e9ab056 + ce58154) via node_exporter's /metrics so one operator command verifies the full producer→consumer→observer chain end-to-end. Read-only (web-is-read- only doctrine MS043 R10212 + R10115). Stdlib-only Python; no deps. See scripts/diagnostics/m060-smoke.py --help for flags (--base-url, --node-exporter-url, --strict, --skip-doctor-observers, --json). NEW: cross-vertical observability triage. Probes ALL 6 verticals shipped to date (M060 chain-health, MS022 SSE quota, four-watchdog IPS spine, selfdef-modul...

# FILES

**/etc/sovereign-os/**
:   Installed configuration and active selections.

**/var/lib/sovereign-os/**
:   Per-machine runtime state.

**~/.sovereign-os/**
:   Per-operator state and logs where supported.

# EXIT STATUS

Zero indicates success. Non-zero indicates invalid input, failed checks,
missing dependencies, refused gates, or operational failure. Audit and
coverage surfaces may use status 2 for findings.

# SEE ALSO

**sovereign-osctl**(1), **sovereign-osctl-models**(1),
**sovereign-osctl-agents**(1), **sovereign-osctl-hardware**(1),
**sovereign-osctl-security**(1), **sovereign-osctl-operations**(1),
**sovereign-osctl-governance**(1), **sovereign-osctl-install**(1)

# REPORTING BUGS

GitHub: <https://github.com/cyberpunk042/sovereign-os/issues>

# LICENSE

AGPL-3.0-or-later
