% SOVEREIGN-OSCTL-OPERATIONS(1) sovereign-os 0.2.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-operations - operations, observability, and recovery

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

System status, diagnostics, maintenance, metrics, alerts, journals, histories, snapshots, notifications, dashboards, and daily operator workflows.

This page owns 35 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. **sovereign-osctl help** remains authoritative for the
exact syntax shipped by the installed version.

# SAFETY MODEL

Most inspection verbs are read-only. Maintenance, snapshot, restore, notification, service, and remediation verbs may require root or explicit apply gates. Preserve command output when escalating an incident.

Read-only discovery should precede mutation. JSON output, when offered,
is the stable surface for automation; human output is intended for direct
operator use.

# COMMON WORKFLOW

1. Inspect the relevant **status**, **show**, **list**, **info**, **plan**,
   or **doctor** surface.
2. Save machine-readable output when `--json` is available.
3. Review profile, device, backend, policy, and target selection.
4. Apply the smallest scoped mutation.
5. Re-run health/status and inspect alerts or journal output.

# EXAMPLES

    sovereign-osctl status --json
    sovereign-osctl doctor
    sovereign-osctl alerts --json
    sovereign-osctl journal errors
    sovereign-osctl maintenance list

# COMMAND REFERENCE

## status

**sovereign-osctl status [--json]**
:   System state overview (--json for fleet aggregation)

Run `sovereign-osctl help` for the complete version-matched grammar.

## overview

**sovereign-osctl overview [--json]**
:   Show a consolidated single-screen snapshot of pipeline phases, bootstrap verification, Trinity state, model residency, active profile and whitelabel, kernel, and Tetragon perimeter. Use `--json` for fleet aggregation.

Run `sovereign-osctl help` for the complete version-matched grammar.

## doctor

**sovereign-osctl doctor**
:   Sanity checks across the system

Run `sovereign-osctl help` for the complete version-matched grammar.

## assistant

**sovereign-osctl assistant [<sub>]**
:   First-login assistant: full | status | reset | list

Run `sovereign-osctl help` for the complete version-matched grammar.

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

Run `sovereign-osctl help` for the complete version-matched grammar.

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

Run `sovereign-osctl help` for the complete version-matched grammar.

## env

**sovereign-osctl env list [--filter <regex>]**
:   List every SOVEREIGN_OS_* env var with its default

**sovereign-osctl env show <NAME>**
:   Detail one env var (default · all consumers · currently-set value)

Run `sovereign-osctl help` for the complete version-matched grammar.

## metrics

**sovereign-osctl metrics list**
:   List all sovereign_os_*.prom files in the textfile collector dir

**sovereign-osctl metrics show <basename>**
:   Pretty-print a single .prom file (resolves trailing .prom)

**sovereign-osctl metrics tail [N]**
:   Tail the N most-recently-updated .prom files (default: 5)

**sovereign-osctl metrics health**
:   Sanity-check the textfile collector dir (presence, age, format)

Run `sovereign-osctl help` for the complete version-matched grammar.

## alerts

**sovereign-osctl alerts [--json]**
:   Derive operator alerts from .prom files (no Alertmanager needed)

Run `sovereign-osctl help` for the complete version-matched grammar.

## journal

**sovereign-osctl journal list [--all-dirs]**
:   List Layer A JSONL log files (size + first/last event)

**sovereign-osctl journal show <file> [--all-dirs]**
:   Pretty-print one JSONL log file as a table

**sovereign-osctl journal tail [--all-dirs] [N]**
:   Tail the N most recent log files (default: 3)

**sovereign-osctl journal errors [--all-dirs]**
:   Show every error/warn entry across all log files

Run `sovereign-osctl help` for the complete version-matched grammar.

## history

**sovereign-osctl history list**
:   Per-run summary derived from JSONL files (profile · steps · result · duration)

**sovereign-osctl history show <run-id>**
:   Drill into one run (step-by-step pass/fail)

Run `sovereign-osctl help` for the complete version-matched grammar.

## diagnose

**sovereign-osctl diagnose run [--severity S] [--limit N] [--all] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl diagnose probes [--json]**
:   R266: list available sub-probes.

Run `sovereign-osctl help` for the complete version-matched grammar.

## next-steps

**sovereign-osctl next-steps next|packs|apply-pack [--severity S] [--limit N] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## severity

**sovereign-osctl severity evaluate [--escalate-after-seconds N] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl severity state [--json]**
:   R273: dump current escalation state.

**sovereign-osctl severity reset [--confirm]**
:   R273: clear state file (operator-confirm).

Run `sovereign-osctl help` for the complete version-matched grammar.

## health

**sovereign-osctl health scan [--json] [--probe NAME]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## insights

**sovereign-osctl insights [--threshold-bytes N] [--root D] [--limit N] [--all] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## kernel

**sovereign-osctl kernel list [--json]**
:   R239 (SDD-026 Z-14): enumerate kernel-

**sovereign-osctl kernel show [--preset P] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl kernel apply <preset> [--dry-run] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl kernel cmdline-hints <preset> [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## services

**sovereign-osctl services list [--prefix P] [--state S] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl services failures [--json]**
:   R240: only units in failed state. rc=1

**sovereign-osctl services timers [--json]**
:   R240: next/last fire times via

**sovereign-osctl services shipped [--json]**
:   R240: catalog of units this repo

Run `sovereign-osctl help` for the complete version-matched grammar.

## events

**sovereign-osctl events timeline [--source S] [--since ISO] [--limit N] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl events summary [--json]**
:   R246: per-source counts + last-event

Run `sovereign-osctl help` for the complete version-matched grammar.

## notify

**sovereign-osctl notify dispatch [--from-file P] [--dry-run] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl notify test --channel C [--severity S]**
:   See the live help for behavior and options.

**sovereign-osctl notify list-channels [--json]**
:   See the live help for behavior and options.

**sovereign-osctl notify state [--json]**
:   R228: dump the dedup state file.

**sovereign-osctl notify send --message M [--severity S] [--title T]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## dashboard

**sovereign-osctl dashboard serve [--bind HOST:PORT] [--once]**
:   See the live help for behavior and options.

**sovereign-osctl dashboard render**
:   R225: render the dashboard HTML to

**sovereign-osctl dashboard grid [--json] [--watch] [--interval SEC]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## mcp-aggregate

**sovereign-osctl mcp-aggregate manifest [--upstream-selfdef H:P] [--config P] [--json|--human]**
:   See the live help for behavior and options.

**sovereign-osctl mcp-aggregate probe-upstream H:P [--timeout SECS] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## self-test

**sovereign-osctl self-test [arguments]**
:   R332 (E2.M23): config-snapshot for backup/migration. Captures complete operator-customized state into ONE portable JSON: overlays + audit + windows + inventory + helper-library manifest. Distinct from R322 state-snapshot (runtime-state).

Run `sovereign-osctl help` for the complete version-matched grammar.

## next-action

**sovereign-osctl next-action [arguments]**
:   R331 (E9.M14): operator-pull self-test verb. Runs L1 lint suites + unit tests + curated L3 sample + emits health summary. "Is sovereign-os itself working correctly on this host?"

Run `sovereign-osctl help` for the complete version-matched grammar.

## fleet-aggregate

**sovereign-osctl fleet-aggregate [arguments]**
:   R325 (E2.M21): operator-overlay drift detector. Scans /etc/sovereign-os/*.toml + reports which knobs the operator has overridden vs shipped defaults. Operator-pull "what have I customized on this host?" — companion to R283 overlay doctrine + R322 state snapshot.

Run `sovereign-osctl help` for the complete version-matched grammar.

## maintenance-window

**sovereign-osctl maintenance-window [arguments]**
:   R324 (E2.M20): fleet snapshot aggregator. Ingests R322 unified state snapshots from multiple hosts; emits cross-host rollup (per-axis verdict distribution, host-level summary, outlier detection). Operator-pull "how is my whole fleet doing?"

Run `sovereign-osctl help` for the complete version-matched grammar.

## snapshot

**sovereign-osctl snapshot [arguments]**
:   R323 (E2.M19): maintenance-window scheduler. Operator declares named time windows; other advisors / autohealth / heat-oc- throttle query can-run-now <window> before acting. Operator-named (§1b verbatim: "schedule/planifest/graceful on all levels, orderly").

Run `sovereign-osctl help` for the complete version-matched grammar.

## module-state

**sovereign-osctl module-state [arguments]**
:   R350 (E5.M17): task → (base, method, target GPU) recommender. Operator-named §1b verbatim: "download, fine-tune, parameters, build, run, use and train and adapt and use and eval and etc." ADAPT sits upstream of R244 fine-tune + R232 eval; consults R317 catalog GPU VRAM via R348 inventory_consult helper.

Run `sovereign-osctl help` for the complete version-matched grammar.

## network-topology

**sovereign-osctl network-topology [sub]**
:   R359 (§8+§8.1): operator-verbatim ASCII

Run `sovereign-osctl help` for the complete version-matched grammar.

## autohealth

**sovereign-osctl autohealth [arguments]**
:   R355 (E10.M3) + R357 (E10.M4): operator-pull SAIN-01 master spec §13 Architectural Q&A Matrix + §14 Critical Edge Cases & Operational Gotchas + §15-16 1-Bit Paradigm & Hardware Fusion concepts + §19 dual-CCD doctrine + Trinity Genesis (Block 6 Modules 1/2/3) — verbatim operator-stated content surfaced as discoverable verbs.

Run `sovereign-osctl help` for the complete version-matched grammar.

## research-loop

**sovereign-osctl research-loop status [--config P] [--json|--human]**
:   See the live help for behavior and options.

**sovereign-osctl research-loop topics [--config P] [--json|--human]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## traces

**sovereign-osctl traces [arguments]**
:   M060 D-03 (R10069-R10074): unified model-health core — joins the model catalog (models/catalog.yaml) to the SRP hardware topology (M075 Conductor/Logic/Oracle), overlays live GPU telemetry (nvidia-smi) + optional inference-fabric runtime state (loaded models, KV cache, p50/p95/p99 latency). Read-only; the sovereign-model-health-api daemon serves the D-03 cockpit dashboard from this same core. Verbs: status / catalog / gpus (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## bashrc

**sovereign-osctl bashrc install**
:   R447 (E11.M6): install operator-discoverable

**sovereign-osctl bashrc uninstall**
:   Remove the sovereign-os bashrc block

**sovereign-osctl bashrc status**
:   Report install state (installed | absent)

**sovereign-osctl bashrc dump**
:   Print the block to stdout (pipe to

Run `sovereign-osctl help` for the complete version-matched grammar.

## ms022-doctor

**sovereign-osctl ms022-doctor [arguments]**
:   R447 (E11.M6): operator-discoverable bashrc integration — autocompletes + aliases + helper menu. Operator §1g verbatim: "the bashrc we can offer to configure it too and we can add our autocompletes and aliases and manual / helps and menus". Idempotent + reversible (sentinel-bounded block).

Run `sovereign-osctl help` for the complete version-matched grammar.

## m060-doctor

**sovereign-osctl m060-doctor [arguments]**
:   MS022 SSE subscriber-quota chain triage — probes the 4 consumer- side surfaces (proxy daemon, master-dashboard banner, systemd unit) against the selfdef-side producer state (selfdef commit 77b4499 6 gauges). Read-only (R10212 + R10115). Stdlib-only Python; no deps. Exit codes: 0=GREEN / 1=YELLOW / 2=RED. Flags: --strict requires state=ok everywhere; --json for machine-readable triage. See scripts/diagnostics/ms022-doctor.py --help for the full flag surface.

Run `sovereign-osctl help` for the complete version-matched grammar.

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
