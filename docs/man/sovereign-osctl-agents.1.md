% SOVEREIGN-OSCTL-AGENTS(1) sovereign-os 0.2.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-agents - agent runtimes and compute plane

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

Desktop selection, OpenClaw, open-computer, background jobs, compute-plane placement, state fabric, sessions, approvals, and recovery.

This page owns 24 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. **sovereign-osctl help** remains authoritative for the
exact syntax shipped by the installed version.

# SAFETY MODEL

Hosted-provider keys are runtime secrets and must never be baked into an image. Backend switches, agent enablement, job cancellation, state writes, and rollback can mutate runtime state.

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

    sovereign-osctl frontend status --json
    sovereign-osctl openclaw backend show
    sovereign-osctl open-computer doctor
    sovereign-osctl jobs --json list
    sovereign-osctl weaver list --json

# COMMAND REFERENCE

## openclaw

**sovereign-osctl openclaw status**
:   SDD-705 OpenClaw gateway daemon: installed · enabled · active · config

**sovereign-osctl openclaw on | off**
:   Enable+start / stop+disable the OpenClaw daemon (installed-off; root)

**sovereign-osctl openclaw install**
:   Run the first-boot installer now (Node + npm + preconfig → local endpoint; root)

**sovereign-osctl openclaw backend {local|anthropic|show} [--key K]**
:   See the live help for behavior and options.

**sovereign-osctl openclaw logs [N] | doctor**
:   Tail the gateway journal / check node+openclaw+config health

Run `sovereign-osctl help` for the complete version-matched grammar.

## open-computer

**sovereign-osctl open-computer status**
:   SDD-706 open-computer QEMU AI-sandbox: installed · active · /dev/kvm · UI port

**sovereign-osctl open-computer on | off**
:   Enable+start / stop+disable the sandbox VM (installed-off; root)

**sovereign-osctl open-computer install**
:   Run the first-boot installer now (QEMU/KVM + Node + build + ~3GB base image; root)

**sovereign-osctl open-computer backend {local|anthropic|show} [--key K]**
:   See the live help for behavior and options.

**sovereign-osctl open-computer url | logs | doctor**
:   Print the UI URL / tail the journal / check qemu+kvm+node+base health

Run `sovereign-osctl help` for the complete version-matched grammar.

## jobs

**sovereign-osctl jobs [arguments]**
:   Plan Mode / User Approval — the Auto-mode safety classifier (docs/standing-directives/2026-07-11-plan-mode-user-approval.md). Classify a command as destructive / routine / unknown and decide allow / block / confirm under a permission mode (manual/auto/bypass). Enforced live in control-exec-api; this is the CLI + library face. permission [--mode manual|auto|bypass] <command…>

Run `sovereign-osctl help` for the complete version-matched grammar.

## plane

**sovereign-osctl plane [arguments]**
:   Background Tasks runtime (jobs-api :8142) — the long-running work the box runs OFF the request path: a background CoAT deliberation, a model eval, a secondary-model load, a GPU job, or a job mirrored from the RTX-4090 VM. list / status <id> are read-only; submit / cancel are the ACTIONS the cockpit routes through control-exec-api. Rendered live in the Code Console's Background Tasks pane. jobs [--json] list jobs [--json] status <id> jobs [--json] submit deliberation --problem "…" [--rung coat...

Run `sovereign-osctl help` for the complete version-matched grammar.

## rounds

**sovereign-osctl rounds [arguments]**
:   R322 (E2.M18): unified state snapshot — runs all read-only advisors in parallel + emits one consolidated JSON document. Operator-pull "what's the COMPLETE state of this host right now?"

Run `sovereign-osctl help` for the complete version-matched grammar.

## cot

**sovereign-osctl cot [arguments]**
:   R321 (E9.M9): operator-pull rounds catalog — meta-navigation over the now-300+ round codebase. Parses mandate.md, exposes list / show / by-epic / recent verbs. Operator-named (§1.0 meta-navigation for perpetual E9.M3 intake loop).

Run `sovereign-osctl help` for the complete version-matched grammar.

## guide

**sovereign-osctl guide [arguments]**
:   R309 (E2.M15): integrated-intelligence CoT registry — named CoT routines that compose multiple sovereign-os verbs into single decision flows (oc-go-no-go / health-triage / psu-budget / storage-cleanup / pre-shutdown / boot-troubleshoot). Sovereign-os counterpart to selfdef SD-R98 @selfdef_macro. Operator-named (§1b verbatim).

Run `sovereign-osctl help` for the complete version-matched grammar.

## morning-brief

**sovereign-osctl morning-brief [arguments]**
:   R353 (E5.M18): fills the "build" verb in the §1b 9-verb AI tools pipeline (download/fine-tune/parameters/BUILD/run/use/train/ adapt/eval). Plans merge/quantize/export of a deployable model artifact from {base + adapter + recipe}. Hardware-aware via the same declared-GPUs pattern as R350 adapt.

Run `sovereign-osctl help` for the complete version-matched grammar.

## state-fabric

**sovereign-osctl state-fabric [sub]**
:   R358 (§7.1+§7.2): file-state matrix +

Run `sovereign-osctl help` for the complete version-matched grammar.

## repl

**sovereign-osctl repl [sub]**
:   R366: 4-level (Python/System/GPU/LLM)

Run `sovereign-osctl help` for the complete version-matched grammar.

## search

**sovereign-osctl search [arguments]**
:   R366 (E2.M21 close): operator-pull multi-level REPL. Operator-named (hook drop 2026-05-17): "Python, System and GPU and LLM and multiple level and REPL". 4 modes with per-mode preambles + reference commands; exec for one-shot non-interactive + shell for operator-runnable interactive.

Run `sovereign-osctl help` for the complete version-matched grammar.

## layers

**sovereign-osctl layers [sub]**
:   R382: operator-verbatim 11-layer

Run `sovereign-osctl help` for the complete version-matched grammar.

## lifecycle

**sovereign-osctl lifecycle [arguments]**
:   R287 (E1.M19): "Hardware-exploit-to-the-max research loop" — operator-pull "what's worth investigating right now" across the AVX-512/Zen5 fast-path stack (bitnet.cpp, Wasmtime znver5, transformers, vllm, DFlash, etc). Read-only; no network calls. Operator-named (§1b mandate): "research mode verb that surfaces upstream changes".

Run `sovereign-osctl help` for the complete version-matched grammar.

## workflow

**sovereign-osctl workflow [arguments]**
:   R290 (E5.M6): end-to-end fine-tune lifecycle — threads R244 fine-tune + R232 eval + R182 selfdef registry into ONE operator-pull workflow. Operator-named (§1b mandate): "End-to-end fine-tune lifecycle (operator triggers training → eval → register)". Read-only; emits the next pending command for the operator to run.

Run `sovereign-osctl help` for the complete version-matched grammar.

## sessions

**sovereign-osctl sessions [arguments]**
:   M060 D-10 (R10106-R10108): eval-history aggregation — reads the Eval-Value fabric's eval-run log, aggregates per-task pass/fail + per-model trend + benchmark-suite progress (M078 HölderPO + M080 HRM targets) + adapter-promotion candidates (from the D-11 adapter core). Enforces the M079 WB/BB disaggregation invariant (white-box benchmarks NEVER averaged with black-box). Read-only; the sovereign-evals-api daemon serves the D-10 cockpit dashboard from this same core. Verbs: summary / suites / ca...

Run `sovereign-osctl help` for the complete version-matched grammar.

## approvals

**sovereign-osctl approvals [arguments]**
:   SDD-058 (M057): the session-process producer — start -- <cmd> spawns an operator task command under a systemd-run --scope + registers it with a real pid (the CRIU save-state target); stop archives the scope; list shows the registered sessions. reap (SDD-065) is the reaper janitor — archives active sessions whose tracked process is already dead (a state-reconciliation, safe bookkeeping; runs from the sovereign-session- reaper.timer). start also creates a per-session ZFS child dataset (tank/age...

Run `sovereign-osctl help` for the complete version-matched grammar.

## rollback

**sovereign-osctl rollback [arguments]**
:   M060 D-06 (R10088-R10092): operator approval-queue + stage-gate core. READ verbs (pending / gates / key) → approval-queue.py (never mutates, never reads key material). WRITE verbs (approve / deny / defer / request, SDD-048) → approval-decide.py: transition the M065 SG1-SG5 gate + record a durable, audited decision. Decisions are --confirm + operator-key + type-to-confirm gated (via the cockpit exec daemon) and DRY-RUN by default; MS003 signing is deferred to selfdef (signature "unsigned-pendi...

Run `sovereign-osctl help` for the complete version-matched grammar.

## memory-changes

**sovereign-osctl memory-changes [arguments]**
:   M060 D-08 (R10097-R10101): ZFS-snapshot + commit-history rollback-points — joins the ZFS snapshot inventory (M068, zfs list -t snapshot) to the MS041 commit history (git log) + a dry-run rollback preview (R10099, the zfs rollback plan + git commits that would be reverted, READ-ONLY). rollback-apply (R10100) is gated behind --confirm + MS003 signature. The sovereign-rollback-api daemon serves the D-08 cockpit dashboard from this same core. Verbs: snapshot / preview --to <id> / commits (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## sandbox-mirror

**sovereign-osctl sandbox-mirror [arguments]**
:   M060 D-18 (R10123): READ-ONLY consumer of the selfdef tool trust-score mirror (MS007 typed-mirror crate selfdef-trust-score-mirror). Projects selfdef MS042 per-tool trust scores (declaration-fidelity over time, 0-1000 scale, 4 bands + score history) for the D-18 cockpit dashboard. sovereign-os NEVER mutates IPS state; score reset is selfdefctl + MS003 only. Verbs: snapshot / bands (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## profile-mirror

**sovereign-osctl profile-mirror [arguments]**
:   M060 D-15 (R10118-R10119): READ-ONLY consumer of the selfdef sandbox mirror (MS007 typed-mirror crate selfdef-sandbox-mirror). Projects selfdef MS032 sandbox-tiers + MS036 tool-sandboxes allocation state (4 tiers + 8-level isolation ladder + TTL + CRIU checkpoint) for the D-15 cockpit dashboard. sovereign-os NEVER mutates IPS state; checkpoint/release are selfdefctl + MS003 only. Verbs: snapshot / summaries (+ --json).

Run `sovereign-osctl help` for the complete version-matched grammar.

## tui-mirror

**sovereign-osctl tui-mirror {snapshot|panels} [--json]**
:   Read the selfdef TUI-layout mirror and project its canonical rules, grants, quarantine, and authority quadrants. This surface is read-only; panel actions expose copyable `selfdefctl` commands rather than mutating state.

Run `sovereign-osctl help` for the complete version-matched grammar.

## cli-mirror

**sovereign-osctl cli-mirror [arguments]**
:   MS043 R10141 + F05081 + R10298: READ-ONLY consumer of the selfdef TUI layout mirror (MS007 typed-mirror crate selfdef-tui-mirror). Projects the canonical 4-panel layout (rules / grants / quarantine / authority across TL/TR/BL/BR quadrants) the selfdefd mirror-export loop publishes every 30s. Used by sovereign-os minimal-web mirroring (R10170 "same 4-panel layout as TUI"). Doctrine surface "A dashboard should not show vanity graphs" preserved verbatim per R10298. No panel keybinding is mutatin...

Run `sovereign-osctl help` for the complete version-matched grammar.

## frontend

**sovereign-osctl frontend status [--json]**
:   SDD-704 boot-frontend selector: what's installed / default / active

**sovereign-osctl frontend list [--json]**
:   The frontends (gnome · dashboards-kiosk · open-computer-kiosk · none) + staged/active

**sovereign-osctl frontend set <value> [--url U]**
:   Switch the boot frontend live, no reflash (root):

Run `sovereign-osctl help` for the complete version-matched grammar.

## weaver

**sovereign-osctl weaver status**
:   Brief Weaver panel (podman / vfio /

**sovereign-osctl weaver list**
:   4 state-fabric files (IDENTITY / SOUL /

**sovereign-osctl weaver state-files**
:   R535: master spec § 7.1 4-state catalog

**sovereign-osctl weaver read <name>**
:   Read /mnt/vault/context/<name>.md

**sovereign-osctl weaver write <name>**
:   Atomic-state write (master spec § 21.1

**sovereign-osctl weaver watch**
:   R534 (E5++): refresh-loop TUI surface

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
