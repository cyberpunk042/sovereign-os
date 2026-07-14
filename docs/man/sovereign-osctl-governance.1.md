% SOVEREIGN-OSCTL-GOVERNANCE(1) sovereign-os 0.3.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-governance - governance, documentation, and surface contracts

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

Architecture questions, doctrine, documentation coverage, UX, anti-minimization, surface maps, compliance, dashboards, and cross-module health.

This page owns 18 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. The synopsis and descriptions are grounded in the
command handler or delegated-script contract at this build revision.
The top-level help is a discovery summary, not an exhaustive grammar.

# SAFETY MODEL

Scanners and reports are generally read-only. Snapshot/apply actions alter governance history; treat waivers as explicit reviewed exceptions rather than a way to hide gaps.

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

    sovereign-osctl architecture-qa
    sovereign-osctl doc-coverage gaps --json
    sovereign-osctl surface-map coverage --json
    sovereign-osctl anti-minimization-audit report --json
    sovereign-osctl compliance status --json

# COMMAND REFERENCE

## operator-rules

**sovereign-osctl operator-rules status|apply|capture|compat [--dry-run] [--json]**
:   See the handler for behavior and options.

## apply-audit

**sovereign-osctl apply-audit {list|tail|by-verb|audit}**
:   R327 (E9.M11): central apply-audit log query CLI. Reads /var/lib/sovereign-os/apply-audit.jsonl appended by every mutating verb. Operator-pull "who mutated what when?"

## rounds

**sovereign-osctl rounds {list|show|by-epic|recent}**
:   R321 (E9.M9): operator-pull rounds catalog — meta-navigation over the now-300+ round codebase. Parses mandate.md, exposes list / show / by-epic / recent verbs. Operator-named (§1.0 meta-navigation for perpetual E9.M3 intake loop).

## search

**sovereign-osctl search [arguments]**
:   R386 (E10.M30): unified operator-pull search across all 3 verbatim-catalog taxonomies (architecture-qa + coverage-map + layers). One verb queries all catalogs at once + ranks results.

## layers

**sovereign-osctl layers [sub]**
:   R382: operator-verbatim 11-layer

## quarterly-review

**sovereign-osctl quarterly-review [sub]**
:   R377: composed coverage + doctrine +

## doctrine-status

**sovereign-osctl doctrine-status [sub]**
:   R376: SDD-037 8-lint family health at

## verbatim-render

**sovereign-osctl verbatim-render [sub]**
:   R369: consolidated render of all 9

## coverage

**sovereign-osctl coverage [sub]**
:   R365: 32 operator-stated demand axes

## architecture-qa

**sovereign-osctl architecture-qa [sub]**
:   R355+ verbatim catalog (27 concepts +

## dashboards

**sovereign-osctl dashboards [arguments]**
:   M060 R10038 + R10129-R10132: operator dashboard on/off toggles — "everything can be turned on and off". Lists every cockpit dashboard + its enabled bit, toggles them on/off (persisted to /etc/sovereign-os/ dashboards.toml, R10130), emitting an M049 trace + OCSF 5001 Configuration Change (R10132) into the D-05 span log on each change. enable/disable are the operator (MS003-signed) path (R10131); web surfaces never mutate. Verbs: list / status <slug> / enable <slug> / disable <slug> [--rationale].

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

## anti-minimization-audit

**sovereign-osctl anti-minimization-audit patterns**
:   R456 (E11.M11): operator §1g standing

**sovereign-osctl anti-minimization-audit scan**
:   Scan repo for matches (all 8 or one

**sovereign-osctl anti-minimization-audit module <n>**
:   Per-module audit: surface gaps +

**sovereign-osctl anti-minimization-audit cross-module Modules short on BOTH surface AND doc**
:   See the handler for behavior and options.

**sovereign-osctl anti-minimization-audit report**
:   One-screen summary: total matches per

**sovereign-osctl anti-minimization-audit waivers**
:   R474: list active 'anti-min-waiver:'

**sovereign-osctl anti-minimization-audit selfdef**
:   R466 cross-repo: scan /etc/selfdef/

**sovereign-osctl anti-minimization-audit watch**
:   R522 (E5++): refresh-loop TUI surface

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
