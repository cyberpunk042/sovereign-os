% SOVEREIGN-OSCTL-SECURITY(1) sovereign-os 0.2.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-security - security, identity, perimeter, and audit

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

Tetragon perimeter, selfdef, Secure Boot, permission classification, authentication tiers, hardening, network edge, peace-machine checks, and security mirrors.

This page owns 18 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. **sovereign-osctl help** remains authoritative for the
exact syntax shipped by the installed version.

# SAFETY MODEL

Key generation, policy reloads, tier changes, firewall changes, quarantine, trust, and grant operations affect the security boundary. Inspect status, plans, diffs, and current policy before applying.

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

    sovereign-osctl perimeter verify
    sovereign-osctl selfdef status
    sovereign-osctl secure-boot status
    sovereign-osctl audit drift --json
    sovereign-osctl permission --mode auto 'systemctl restart sovereign-gatewayd'

# COMMAND REFERENCE

## perimeter

**sovereign-osctl perimeter status**
:   Tetragon perimeter status

**sovereign-osctl perimeter verify**
:   Run perimeter integrity audit

**sovereign-osctl perimeter reload**
:   Reload Tetragon TracingPolicies

Run `sovereign-osctl help` for the complete version-matched grammar.

## selfdef

**sovereign-osctl selfdef status**
:   selfdef (IPS) on/off dashboard: checkout · units · mirror

**sovereign-osctl selfdef on | off**
:   Enable+start / stop+disable all selfdef units (root)

**sovereign-osctl selfdef start|stop|restart**
:   Runtime lifecycle without changing enablement (root)

**sovereign-osctl selfdef logs [N]**
:   Tail the selfdef guardian journal

**sovereign-osctl selfdef sync**
:   Refresh the selfdef checkout (freshness/gated update, SDD-001)

**sovereign-osctl selfdef doctor**
:   Run selfdef's own doctor (or freshness sync)

**sovereign-osctl selfdef install-units**
:   Wire selfdef's shipped systemd units into /etc/systemd/system (root)

Run `sovereign-osctl help` for the complete version-matched grammar.

## audit

**sovereign-osctl audit friction**
:   Runtime friction-audit (lspci/lscpu/IOMMU)

**sovereign-osctl audit perimeter**
:   Perimeter integrity (Tetragon policy)

**sovereign-osctl audit storage**
:   ZFS pool + dataset health

**sovereign-osctl audit provenance [--deep] [<path>]**
:   Inspect build-provenance.json + cross-check sha256sums.txt (+ recompute SHA256 on disk with --deep)

**sovereign-osctl audit drift [--json]**
:   Compare deployed hardening drop-ins vs config/server + config/workstation sources

**sovereign-osctl audit customization [--json] Did my profile/whitelabel/hostname customization actually land?**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## secure-boot

**sovereign-osctl secure-boot gen-keys --out <dir>**
:   Generate PK/KEK/db key triple (SDD-015 'signed' posture).

**sovereign-osctl secure-boot status**
:   Inspect current PK/KEK/db enrollment + MOK state

Run `sovereign-osctl help` for the complete version-matched grammar.

## permission

**sovereign-osctl permission [--mode manual|auto|bypass] <command…>**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## hardening-base

**sovereign-osctl hardening-base [arguments]**
:   R307 (E1.M31): CPU hotswap mode detection — per-CPU current governor / EPP / driver state + available transitions + swap-hint operator-runnable command. Complements R221/R230 (E1.M10 cpu-mode + auto-recommender) with the detect side. Operator-named (§1b verbatim).

Run `sovereign-osctl help` for the complete version-matched grammar.

## auth-tier

**sovereign-osctl auth-tier list-tiers**
:   R450 (E11.M7): operator §1g 6-tier

**sovereign-osctl auth-tier registry**
:   Per-dashboard tier registry (which

**sovereign-osctl auth-tier show <dashboard>**
:   Detail one dashboard's tier + recommended

**sovereign-osctl auth-tier matrix**
:   Upgrade matrix — current → recommended

**sovereign-osctl auth-tier set <dashboard>**
:   Triple-gated tier mutation (requires

Run `sovereign-osctl help` for the complete version-matched grammar.

## grants-mirror

**sovereign-osctl grants-mirror [arguments]**
:   SDD-069 (M028): the observation event stream — auto-feed admission from the ONE real event source, the OCSF span log (/var/log/sovereign-os/spans.jsonl). Tails it via a persisted cursor + maps each new span → a memory admission + feeds the existing admit value-gate (R04672 — not every observation becomes memory). COMPREHENSIVE mapping (session_reap→task-outcome/episodic, cockpit_action ok→ tool-worked, fail→model-mistake, *_decision→preference, save-state→high-value- reuse, gate→task-outcome,...

Run `sovereign-osctl help` for the complete version-matched grammar.

## quarantine-mirror

**sovereign-osctl quarantine-mirror [arguments]**
:   M060 D-13 (R10114-R10115): READ-ONLY consumer of the selfdef grants mirror (MS007 typed-mirror crate selfdef-grants-mirror) — projects selfdef's MS037/MS038/MS035/MS034/MS032 grant state (filesystem/network/ capability/communication/sandbox) for the D-13 cockpit dashboard. sovereign-os NEVER mutates IPS state; grant ops are selfdefctl + MS003 on the IPS side only. Verbs: snapshot / summaries (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## trust-mirror

**sovereign-osctl trust-mirror [arguments]**
:   M060 D-17 (R10121-R10122): READ-ONLY consumer of the selfdef tool- quarantine mirror (MS007 typed-mirror crate selfdef-quarantine-mirror). Projects selfdef MS042 declaration-vs-observed quarantine archive (4 severities + per-field mismatches + block/quarantine/trace) for the D-17 cockpit dashboard. sovereign-os NEVER mutates IPS state; trace/release/ forfeit are selfdefctl + MS003 only. Verbs: snapshot / summaries (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## capability-mirror

**sovereign-osctl capability-mirror [arguments]**
:   M060 D-02 (R10063-R10068): READ-ONLY consumer of the selfdef active- profile mirror (MS007 typed-mirror crate selfdef-profile-mirror). Projects selfdef MS040 six-profile authority matrix active selection + MS039 L0..L6 envelope + transition history for the D-02 cockpit dashboard. sovereign-os NEVER mutates IPS state; profile switch is sovereign profile set + MS003 only. Offline → MS040 R09535 default (Private). Verb: show (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## audit-mirror

**sovereign-osctl audit-mirror [arguments]**
:   M060 D-14 (R10116-R10117): READ-ONLY consumer of the selfdef capability- token mirror (MS007 typed-mirror crate selfdef-capability-mirror). Projects selfdef MS035 64-bit capability_word tokens + MS039 Ring 0..4 + L0..L6 authority + F04146 parent-child inheritance for the D-14 cockpit dashboard. sovereign-os NEVER mutates IPS state; token issue/revoke are selfdefctl + MS003 only. Verbs: snapshot / summaries (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## rules-mirror

**sovereign-osctl rules-mirror [arguments]**
:   M060 D-16 (R10120): READ-ONLY consumer of the selfdef audit-chain mirror (MS007 typed-mirror crate selfdef-audit-mirror). Projects selfdef MS016 SHA-256-chained, MS049 13-field-spanned, MS026 OCSF-categorized, MS003 verify-only audit chain for the D-16 cockpit dashboard. Chain is APPEND- ONLY by MS016 R03567 doctrine — the operator has NO mutation surface; verify / show / export are selfdefctl + MS003 only. Verbs: snapshot / integrity (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## peace-machine

**sovereign-osctl peace-machine [arguments]**
:   M060 D-19 (R10124-R10125): super-model manifest — sovereign-os-native version + module-version table computed LIVE from git HEAD + the milestone catalog (M001..M080 ids/titles/R-row counts) + config/super-model- manifest.toml editorial overlay (M053 11 build-phases + per-milestone family/status). Read-only; the sovereign-super-model-api daemon serves the D-19 cockpit dashboard from this same core. Verbs: snapshot / version / milestones (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## peace-check

**sovereign-osctl peace-check [arguments]**
:   M060 D-20 (R10126-R10128): peace-machine health — sovereign-os-native (M059 sovereign close). Surfaces the 5 peace-machine properties (powerful/ disciplined/reversible/flexible/sovereign, dump 18338-18341) + the live verdict read from the sovereign-os-peace-check validator (R09980-R09982). Read-only; the sovereign-peace-machine-api daemon serves the D-20 cockpit dashboard from this same core. Verbs: snapshot / properties (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## auditor

**sovereign-osctl auditor status**
:   Brief Auditor panel (tetragon /

**sovereign-osctl auditor full**
:   Full diagnostic (TETRAGON + POLICY +

**sovereign-osctl auditor last-violation**
:   Last entry of /mnt/vault/context/

**sovereign-osctl auditor history [N]**
:   tail -N (default 20) violation history.

**sovereign-osctl auditor watch**
:   R537 (E5++): refresh-loop TUI surface

Run `sovereign-osctl help` for the complete version-matched grammar.

## edge-firewall

**sovereign-osctl edge-firewall state**
:   R451 (E11.M9): operator §1g workstation-side

**sovereign-osctl edge-firewall candidates**
:   4 install-class candidates (nftables-baseline /

**sovereign-osctl edge-firewall recommend**
:   Local + upstream-aware recommendation list

**sovereign-osctl edge-firewall install-plan**
:   Dry-run install: apt packages + systemd units +

**sovereign-osctl edge-firewall install**
:   Triple-gated install (requires --apply +

**sovereign-osctl edge-firewall wizard**
:   R482 (E11.M9+): install-wizard TUI surface —

Run `sovereign-osctl help` for the complete version-matched grammar.

## network-edge

**sovereign-osctl network-edge detect**
:   R449 (E11.M8): operator §1g edge-network

**sovereign-osctl network-edge opnsense status**
:   OPNsense reachability + API tier

**sovereign-osctl network-edge opnsense capabilities**
:   What integration features unlock

**sovereign-osctl network-edge opnsense watch**
:   R483 (E11.M8+): OPNsense status TUI — live-

**sovereign-osctl network-edge interfaces**
:   Per-interface state (MAC/IP/MTU/link)

**sovereign-osctl network-edge nat-chain**
:   NAT layers visible from workstation

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
