% SOVEREIGN-OSCTL-GOVERNANCE(1) sovereign-os 0.2.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-governance - governance, documentation, and surface contracts

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

Architecture questions, doctrine, documentation coverage, UX, anti-minimization, surface maps, compliance, dashboards, and cross-module health.

This page owns 16 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. **sovereign-osctl help** remains authoritative for the
exact syntax shipped by the installed version.

# SAFETY MODEL

Scanners and reports are generally read-only. Snapshot/apply actions alter governance history; treat waivers as explicit reviewed exceptions rather than a way to hide gaps.

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

    sovereign-osctl architecture-qa
    sovereign-osctl doc-coverage gaps --json
    sovereign-osctl surface-map coverage --json
    sovereign-osctl anti-minimization-audit report --json
    sovereign-osctl compliance status --json

# COMMAND REFERENCE

## operator-rules

**sovereign-osctl operator-rules status|apply|capture|compat [--dry-run] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## apply-audit

**sovereign-osctl apply-audit [arguments]**
:   R329 (E2.M22): next-action advisor — composes R322 state snapshot + emits ranked operator-pull recommendations of most-impactful verb to run next. "What should I do now?" decision support.

Run `sovereign-osctl help` for the complete version-matched grammar.

## quarterly-review

**sovereign-osctl quarterly-review [sub]**
:   R377: composed coverage + doctrine +

Run `sovereign-osctl help` for the complete version-matched grammar.

## doctrine-status

**sovereign-osctl doctrine-status [sub]**
:   R376: SDD-037 8-lint family health at

Run `sovereign-osctl help` for the complete version-matched grammar.

## verbatim-render

**sovereign-osctl verbatim-render [sub]**
:   R369: consolidated render of all 9

Run `sovereign-osctl help` for the complete version-matched grammar.

## coverage

**sovereign-osctl coverage [sub]**
:   R365: 32 operator-stated demand axes

Run `sovereign-osctl help` for the complete version-matched grammar.

## architecture-qa

**sovereign-osctl architecture-qa [sub]**
:   R355+ verbatim catalog (27 concepts +

Run `sovereign-osctl help` for the complete version-matched grammar.

## m060-health

**sovereign-osctl m060-health [arguments]**
:   MS043 R10281 + R10297: READ-ONLY consumer of the selfdef CLI schema mirror (MS007 typed-mirror crate selfdef-cli-mirror). Projects the selfdefctl clap App tree (140+ subcommands classified into 8 effect classes per MS039 authority ladder) the selfdef daemon publishes by shelling out + caching selfdefctl cli-mirror snapshot. Used by sovereign-os for IPS-operator-surface introspection, completion generation, "how do I do X" cross-links, MCP-client tool-pickers. Doctrine surface "Fullstack at th...

Run `sovereign-osctl help` for the complete version-matched grammar.

## dashboards

**sovereign-osctl dashboards [arguments]**
:   SDD-132: thin wrapper so the D-20 "re-run" control can execute via the exec-rail (change_cli must start with sovereign-osctl). Execs the standalone validator binary /usr/bin/sovereign-os-peace-check (R09980-R09982). Read-only: the validator computes the 5-property verdict + publishes it; nothing mutates host state. Verbs/flags pass through (the control models the one-shot --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## compliance

**sovereign-osctl compliance status**
:   R458: §1g/§1h compliance dashboard

**sovereign-osctl compliance module <n>**
:   Per-module rollup across 4 instruments.

**sovereign-osctl compliance worst**
:   Top-N modules by composite gap (axes

**sovereign-osctl compliance history**
:   Recent compliance snapshots from

**sovereign-osctl compliance snapshot**
:   Record current state to history journal.

**sovereign-osctl compliance watch**
:   R519 (E5++): refresh-loop TUI surface

Run `sovereign-osctl help` for the complete version-matched grammar.

## ux-design-audit

**sovereign-osctl ux-design-audit dimensions**
:   R457 (E11.M10): operator §1g

**sovereign-osctl ux-design-audit modules**
:   List tracked modules with verb counts.

**sovereign-osctl ux-design-audit audit**
:   Per-module per-dimension audit

**sovereign-osctl ux-design-audit score**
:   Numeric 0..6 score per module, sorted

**sovereign-osctl ux-design-audit report**
:   Modules below UX threshold (default 4

**sovereign-osctl ux-design-audit selfdef**
:   R464 cross-repo: scan /etc/selfdef/

**sovereign-osctl ux-design-audit watch**
:   R528 (E5++): refresh-loop TUI surface

Run `sovereign-osctl help` for the complete version-matched grammar.

## anti-minimization-audit

**sovereign-osctl anti-minimization-audit patterns**
:   R456 (E11.M11): operator §1g standing

**sovereign-osctl anti-minimization-audit scan**
:   Scan repo for matches (all 8 or one

**sovereign-osctl anti-minimization-audit module <n>**
:   Per-module audit: surface gaps +

**sovereign-osctl anti-minimization-audit cross-module Modules short on BOTH surface AND doc**
:   See the live help for behavior and options.

**sovereign-osctl anti-minimization-audit report**
:   One-screen summary: total matches per

**sovereign-osctl anti-minimization-audit waivers**
:   R474: list active 'anti-min-waiver:'

**sovereign-osctl anti-minimization-audit selfdef**
:   R466 cross-repo: scan /etc/selfdef/

**sovereign-osctl anti-minimization-audit watch**
:   R522 (E5++): refresh-loop TUI surface

Run `sovereign-osctl help` for the complete version-matched grammar.

## doc-coverage

**sovereign-osctl doc-coverage kinds**
:   R454 (E11.M1): operator §1g

**sovereign-osctl doc-coverage modules**
:   List operator-facing modules tracked

**sovereign-osctl doc-coverage scan**
:   Live grep — per-module which of the

**sovereign-osctl doc-coverage coverage**
:   Module × doc-surface matrix, sorted

**sovereign-osctl doc-coverage gaps**
:   Modules below doc-surface threshold

**sovereign-osctl doc-coverage watch**
:   R525 (E5++): refresh-loop TUI surface

Run `sovereign-osctl help` for the complete version-matched grammar.

## surface-map

**sovereign-osctl surface-map surfaces**
:   R453 (E11.M3): operator §1g 8-surface

**sovereign-osctl surface-map modules**
:   List operator-facing modules with per-

**sovereign-osctl surface-map coverage**
:   Module × surface matrix — shipped /

**sovereign-osctl surface-map gaps**
:   Modules below surface threshold

**sovereign-osctl surface-map waivers**
:   Per-module explicit waivers (which

**sovereign-osctl surface-map selfdef**
:   R462 cross-repo: scan /etc/selfdef/

**sovereign-osctl surface-map watch**
:   R531 (E5++): refresh-loop TUI surface

Run `sovereign-osctl help` for the complete version-matched grammar.

## master-dashboard

**sovereign-osctl master-dashboard list**
:   R452 (E11.M2): operator §1g reverse-proxy

**sovereign-osctl master-dashboard routes**
:   Show route table the aggregator would emit

**sovereign-osctl master-dashboard collisions**
:   Detect port/subpath collisions BEFORE render

**sovereign-osctl master-dashboard render**
:   Render reverse-proxy config to

**sovereign-osctl master-dashboard health**
:   TCP-connect probe to each upstream port;

**sovereign-osctl master-dashboard discover**
:   R460 cross-repo: scan /etc/selfdef/

**sovereign-osctl master-dashboard watch**
:   R488 (E11.M2+): refresh-loop TUI (ANSI-clear)

Run `sovereign-osctl help` for the complete version-matched grammar.

## global-history

**sovereign-osctl global-history recent**
:   R448 (E11.M5): operator §1g delta/diff

**sovereign-osctl global-history summary**
:   R448: per-source count + last event in

**sovereign-osctl global-history sources**
:   R448: enumerate known sources + status

**sovereign-osctl global-history delta <iso>**
:   R448: events since timestamp (operator

**sovereign-osctl global-history tail**
:   R481 (E11.M5+): live-tail TUI surface —

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
