% SOVEREIGN-OSCTL-SECURITY(1) sovereign-os 0.3.0 | sovereign-os Operator Manual
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
real dispatcher. The synopsis and descriptions are grounded in the
command handler or delegated-script contract at this build revision.
The top-level help is a discovery summary, not an exhaustive grammar.

# SAFETY MODEL

Key generation, policy reloads, tier changes, firewall changes, quarantine, trust, and grant operations affect the security boundary. Inspect status, plans, diffs, and current policy before applying.

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

## ms003

**sovereign-osctl ms003 status**
:   MS003 signing state + trust-anchor summary (F-2026-034)

**sovereign-osctl ms003 gen-key**
:   Mint the operator ed25519 signing key

**sovereign-osctl ms003 pubkey**
:   Print this node's public trust anchor

**sovereign-osctl ms003 anchor-add** *pubkey-b64url* | **--from-key**
:   Install a trust anchor used for verification

**sovereign-osctl ms003 anchor-list**
:   List installed trust anchors

**sovereign-osctl ms003 verify** [**--strict**] [*root*]
:   Verify ledger signatures under *root* (default /var/lib/sovereign-os); exit 2 on tamper/unknown-signer, 3 with --strict when unsigned records are present

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
:   See the handler for behavior and options.

## secure-boot

**sovereign-osctl secure-boot gen-keys --out <dir>**
:   Generate PK/KEK/db key triple (SDD-015 'signed' posture).

**sovereign-osctl secure-boot status**
:   Inspect current PK/KEK/db enrollment + MOK state

## permission

**sovereign-osctl permission [--mode manual|auto|bypass] <command…>**
:   See the handler for behavior and options.

## hardening-base

**sovereign-osctl hardening-base {list|show|check}**
:   R306 (E2.M13): Debian 13 base-system hardening catalog — 12 OS-level items (sysctl hardening + AppArmor + unattended- upgrades + auditd + fail2ban + sshd config). Per-item runtime probe + recommended value + operator-readable rationale. Complements R299 (BIOS layer) + R171 (systemd unit layer).

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

## grants-mirror

**sovereign-osctl grants-mirror [arguments]**
:   M060 D-13 (R10114-R10115): READ-ONLY consumer of the selfdef grants mirror (MS007 typed-mirror crate selfdef-grants-mirror) — projects selfdef's MS037/MS038/MS035/MS034/MS032 grant state (filesystem/network/ capability/communication/sandbox) for the D-13 cockpit dashboard. sovereign-os NEVER mutates IPS state; grant ops are selfdefctl + MS003 on the IPS side only. Verbs: snapshot / summaries (+ --json).

## quarantine-mirror

**sovereign-osctl quarantine-mirror [arguments]**
:   M060 D-17 (R10121-R10122): READ-ONLY consumer of the selfdef tool- quarantine mirror (MS007 typed-mirror crate selfdef-quarantine-mirror). Projects selfdef MS042 declaration-vs-observed quarantine archive (4 severities + per-field mismatches + block/quarantine/trace) for the D-17 cockpit dashboard. sovereign-os NEVER mutates IPS state; trace/release/ forfeit are selfdefctl + MS003 only. Verbs: snapshot / summaries (+ --json).

## trust-mirror

**sovereign-osctl trust-mirror [arguments]**
:   M060 D-18 (R10123): READ-ONLY consumer of the selfdef tool trust-score mirror (MS007 typed-mirror crate selfdef-trust-score-mirror). Projects selfdef MS042 per-tool trust scores (declaration-fidelity over time, 0-1000 scale, 4 bands + score history) for the D-18 cockpit dashboard. sovereign-os NEVER mutates IPS state; score reset is selfdefctl + MS003 only. Verbs: snapshot / bands (+ --json).

## capability-mirror

**sovereign-osctl capability-mirror [arguments]**
:   M060 D-14 (R10116-R10117): READ-ONLY consumer of the selfdef capability- token mirror (MS007 typed-mirror crate selfdef-capability-mirror). Projects selfdef MS035 64-bit capability_word tokens + MS039 Ring 0..4 + L0..L6 authority + F04146 parent-child inheritance for the D-14 cockpit dashboard. sovereign-os NEVER mutates IPS state; token issue/revoke are selfdefctl + MS003 only. Verbs: snapshot / summaries (+ --json).

## audit-mirror

**sovereign-osctl audit-mirror [arguments]**
:   M060 D-16 (R10120): READ-ONLY consumer of the selfdef audit-chain mirror (MS007 typed-mirror crate selfdef-audit-mirror). Projects selfdef MS016 SHA-256-chained, MS049 13-field-spanned, MS026 OCSF-categorized, MS003 verify-only audit chain for the D-16 cockpit dashboard. Chain is APPEND- ONLY by MS016 R03567 doctrine — the operator has NO mutation surface; verify / show / export are selfdefctl + MS003 only. Verbs: snapshot / integrity (+ --json).

## rules-mirror

**sovereign-osctl rules-mirror [arguments]**
:   M060 D-12 (MS024 + MS038 + MS039): READ-ONLY consumer of the selfdef nftables rules mirror (MS007 typed-mirror crate selfdef-rules-mirror). Projects the daemon's Ring 0..4 nftables rule projection for the D-12 networking dashboards (edge-firewall + network-edge). Rule installation lives in selfdefctl + nft at the IPS layer (operator MS003 only) — this dispatch only OBSERVES the live state. Verbs: snapshot / summaries (+ --json).

## peace-machine

**sovereign-osctl peace-machine [arguments]**
:   M060 D-20 (R10126-R10128): peace-machine health — sovereign-os-native (M059 sovereign close). Surfaces the 5 peace-machine properties (powerful/ disciplined/reversible/flexible/sovereign, dump 18338-18341) + the live verdict read from the sovereign-os-peace-check validator (R09980-R09982). Read-only; the sovereign-peace-machine-api daemon serves the D-20 cockpit dashboard from this same core. Verbs: snapshot / properties (+ --json).

## peace-check

**sovereign-osctl peace-check [arguments]**
:   SDD-132: thin wrapper so the D-20 "re-run" control can execute via the exec-rail (change_cli must start with sovereign-osctl). Execs the standalone validator binary /usr/bin/sovereign-os-peace-check (R09980-R09982). Read-only: the validator computes the 5-property verdict + publishes it; nothing mutates host state. Verbs/flags pass through (the control models the one-shot --json).

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
