% SOVEREIGN-OSCTL-AGENTS(1) sovereign-os 0.3.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-agents - agent runtimes and compute plane

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

Desktop selection, OpenClaw, open-computer, background jobs, compute-plane placement, state fabric, sessions, approvals, and recovery.

This page owns 18 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. The synopsis and descriptions are grounded in the
command handler or delegated-script contract at this build revision.
The top-level help is a discovery summary, not an exhaustive grammar.

# SAFETY MODEL

Hosted-provider keys are runtime secrets and must never be baked into an image. Backend switches, agent enablement, job cancellation, state writes, and rollback can mutate runtime state.

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

    sovereign-osctl frontend status --json
    sovereign-osctl openclaw backend show
    sovereign-osctl open-computer doctor
    sovereign-osctl jobs --json list
    sovereign-osctl weaver list --json

# COMMAND REFERENCE

## goal

**sovereign-osctl goal set "\<text\>" [--plan step ...]**
:   SDD-719: lock one durable, operator-verbatim goal (status active) the agent pursues on its own. State: /etc/sovereign-os/agent-state.json.

**sovereign-osctl goal show [--json]**
:   Show the current goal, status, iteration count, plan, and last progress.

**sovereign-osctl goal pause | resume | done | abandon**
:   Stop / restart the loop pursuing the goal (stays locked) / close it done / close it abandoned.

**sovereign-osctl goal progress "\<line\>"**
:   Append a progress note (the loop writes these each iteration; never rewrites the goal text).

**sovereign-osctl goal run [--max-iters 50] [--no-progress 3] [--model NAME] [--port 8083]**
:   Loop-until-goal (goal-driver.py, the SDD-718 self-loop tier): iterate toward the active goal via the gateway agentic endpoint until done ([[GOAL_DONE]]) / max-iters / no-progress. Gated on an active goal.

## openclaw

**sovereign-osctl openclaw status**
:   SDD-705 OpenClaw gateway daemon: installed · enabled · active · config

**sovereign-osctl openclaw on | off**
:   Enable+start / stop+disable the OpenClaw daemon (installed-off; root)

**sovereign-osctl openclaw install**
:   Run the first-boot installer now (Node + npm + preconfig → local endpoint; root)

**sovereign-osctl openclaw backend {local|anthropic|show} [--key K]**
:   See the handler for behavior and options.

**sovereign-osctl openclaw logs [N] | doctor**
:   Tail the gateway journal / check node+openclaw+config health

## open-computer

**sovereign-osctl open-computer status**
:   SDD-706 open-computer QEMU AI-sandbox: installed · active · /dev/kvm · UI port

**sovereign-osctl open-computer on | off**
:   Enable+start / stop+disable the sandbox VM (installed-off; root)

**sovereign-osctl open-computer install**
:   Run the first-boot installer now (QEMU/KVM + Node + build + ~3GB base image; root)

**sovereign-osctl open-computer backend {local|anthropic|show} [--key K]**
:   See the handler for behavior and options.

**sovereign-osctl open-computer url | logs | doctor**
:   Print the UI URL / tail the journal / check qemu+kvm+node+base health

## jobs

**sovereign-osctl jobs [--json] list**
:   Background Tasks runtime (jobs-api :8142) — the long-running work the box runs OFF the request path: a background CoAT deliberation, a model eval, a secondary-model load, a GPU job, or a job mirrored from the RTX-4090 VM. list / status <id> are read-only; submit / cancel are the ACTIONS the cockpit routes through control-exec-api. Rendered live in the Code Console's Background Tasks pane.

**sovereign-osctl jobs [--json] status <id>**
:   Additional supported form.

**sovereign-osctl jobs [--json] submit deliberation --problem "…" [--rung coat]**
:   Additional supported form.

**sovereign-osctl jobs [--json] submit eval -- python3 scripts/models/eval.py …**
:   Additional supported form.

**sovereign-osctl jobs [--json] cancel <id>**
:   Additional supported form.

## plane

**sovereign-osctl plane**
:   The Sovereign Compute Plane (via jobs-api :8142) — the box's devices with LIVE free VRAM + the outstanding claims (model residents + running GPU jobs), placed by the M075 SRP doctrine. Read-only. A GPU job is placed on a device that fits, or waits, so it never OOMs the box.

## cot

**sovereign-osctl cot {list|show|run}**
:   R309 (E2.M15): integrated-intelligence CoT registry — named CoT routines that compose multiple sovereign-os verbs into single decision flows (oc-go-no-go / health-triage / psu-budget / storage-cleanup / pre-shutdown / boot-troubleshoot). Sovereign-os counterpart to selfdef SD-R98 @selfdef_macro. Operator-named (§1b verbatim).

## guide

**sovereign-osctl guide {list|topics|show|walkthrough}**
:   R349 (E10.M1): AI-as-guide topic catalog — operator-pull "guide me into the kernel / hardware / gpu / psu / ups / memory / workload-mode / inference / network". Each topic carries layers + verbs + thresholds + BIOS/HW caveats. Operator-named (§1b verbatim: "only a guide into the experience, into the field, into the kernel, into the hardware, into the OS, into the modules…").

## state-fabric

**sovereign-osctl state-fabric [sub]**
:   R358 (§7.1+§7.2): file-state matrix +

## repl

**sovereign-osctl repl [sub]**
:   R366: 4-level (Python/System/GPU/LLM)

## sessions

**sovereign-osctl sessions {active|summary|steps|hibernate|resume|kill|hibernate-all|save-state|restore|start|stop|list|reap}**
:   M060 D-01 (R10059-R10062): active-session registry — reads the M057 lifecycle engine's published session registry (/run/sovereign-os/sessions.json) and projects each task session onto its M057 12-step lifecycle position + profile envelope + SRP agent (M075) + ETA + branch count. Read-only; the sovereign-sessions-api daemon serves the D-01 cockpit dashboard from this same core. READ verbs (active / summary / steps) → session-registry.py (never mutates). WRITE verbs (hibernate / resume / kill / hibernate-all, SDD-053) → session-decide.py: transition a session's M057 state + record a durable, audited decision. Decisions are --confirm + operator-key + type-to-confirm gated (via the cockpit exec daemon) and DRY-RUN by default; the real M047 CRIU+ZFS effect is the M057 en...

## approvals

**sovereign-osctl approvals {pending|gates|key|approve|deny|defer|request}**
:   M060 D-06 (R10088-R10092): operator approval-queue + stage-gate core. READ verbs (pending / gates / key) → approval-queue.py (never mutates, never reads key material). WRITE verbs (approve / deny / defer / request, SDD-048) → approval-decide.py: transition the M065 SG1-SG5 gate + record a durable, audited decision. Decisions are --confirm + operator-key + type-to-confirm gated (via the cockpit exec daemon) and DRY-RUN by default; MS003 signing is deferred to selfdef (signature "unsigned-pending-MS003"). The sovereign-approvals-api daemon stays read-only (405) — the ONLY write path is control-exec-api → approvals approve|deny|defer.

## rollback

**sovereign-osctl rollback [arguments]**
:   M060 D-08 (R10097-R10101): ZFS-snapshot + commit-history rollback-points — joins the ZFS snapshot inventory (M068, zfs list -t snapshot) to the MS041 commit history (git log) + a dry-run rollback preview (R10099, the zfs rollback plan + git commits that would be reverted, READ-ONLY). rollback-apply (R10100) is gated behind --confirm + MS003 signature. The sovereign-rollback-api daemon serves the D-08 cockpit dashboard from this same core. Verbs: snapshot / preview --to <id> / commits (+ --json).

## memory-changes

**sovereign-osctl memory-changes janitor <dedup|edges|contradict|tag|extract-facts|topic|summarize|classify|advance|sweep> [id|--all] [--confirm]**
:   M060 D-07 (R10093-R10096): Memory OS graph-diff + admission core — reads the M028 Memory OS published state (per-type counts across the 8 memory types, 11-stage admission-lifecycle occupancy, graph diff, pending promote/pin/forget queue + MS039 7 trust dimensions). Read-only; the sovereign-memory-changes-api daemon serves the D-07 cockpit dashboard from this same core. READ verbs (snapshot / types / lifecycle) → memory-changes.py (never mutates). WRITE verbs (approve / reject / request, SDD-052) → memory-decide.py: sign off a pending M028 change (approve applies promote/pin; a pending forget is refused — Stage 3) + record a durable, audited decision. Decisions are --confirm + operator-key + type-to-confirm gated (via the cockpit exec daemon) and DRY-RUN by default; M...

**sovereign-osctl memory-changes navigate "<query>" [--type N] [--stage S] [--topic T] [--verb <v>] [--at <ISO-T>] [--limit K] [--no-compose]**
:   Additional supported form.

**sovereign-osctl memory-changes observe run [--confirm] [--limit N] | observe status**
:   Additional supported form.

## sandbox-mirror

**sovereign-osctl sandbox-mirror [arguments]**
:   M060 D-15 (R10118-R10119): READ-ONLY consumer of the selfdef sandbox mirror (MS007 typed-mirror crate selfdef-sandbox-mirror). Projects selfdef MS032 sandbox-tiers + MS036 tool-sandboxes allocation state (4 tiers + 8-level isolation ladder + TTL + CRIU checkpoint) for the D-15 cockpit dashboard. sovereign-os NEVER mutates IPS state; checkpoint/release are selfdefctl + MS003 only. Verbs: snapshot / summaries (+ --json).

## profile-mirror

**sovereign-osctl profile-mirror [arguments]**
:   M060 D-02 (R10063-R10068): READ-ONLY consumer of the selfdef active- profile mirror (MS007 typed-mirror crate selfdef-profile-mirror). Projects selfdef MS040 six-profile authority matrix active selection + MS039 L0..L6 envelope + transition history for the D-02 cockpit dashboard. sovereign-os NEVER mutates IPS state; profile switch is sovereign profile set + MS003 only. Offline → MS040 R09535 default (Private). Verb: show (+ --json).

## tui-mirror

**sovereign-osctl tui-mirror [arguments]**
:   MS043 R10141 + F05081 + R10298: READ-ONLY consumer of the selfdef TUI layout mirror (MS007 typed-mirror crate selfdef-tui-mirror). Projects the canonical 4-panel layout (rules / grants / quarantine / authority across TL/TR/BL/BR quadrants) the selfdefd mirror-export loop publishes every 30s. Used by sovereign-os minimal-web mirroring (R10170 "same 4-panel layout as TUI"). Doctrine surface "A dashboard should not show vanity graphs" preserved verbatim per R10298. No panel keybinding is mutating (R10212) — all panel verbs copy selfdefctl commands to clipboard. Verbs: snapshot / panels (+ --json).

## cli-mirror

**sovereign-osctl cli-mirror [arguments]**
:   MS043 R10281 + R10297: READ-ONLY consumer of the selfdef CLI schema mirror (MS007 typed-mirror crate selfdef-cli-mirror). Projects the selfdefctl clap App tree (140+ subcommands classified into 8 effect classes per MS039 authority ladder) the selfdef daemon publishes by shelling out + caching selfdefctl cli-mirror snapshot. Used by sovereign-os for IPS-operator-surface introspection, completion generation, "how do I do X" cross-links, MCP-client tool-pickers. Doctrine surface "Fullstack at the edges" preserved verbatim per R10297. Verbs: snapshot / summaries / mutating (+ --json). The mutating verb filters to subcommands that require MS003 signature — operator clipboard-copy only; sovereign-os never invokes them.

## frontend

**sovereign-osctl frontend status [--json]**
:   SDD-704 boot-frontend selector: what's installed / default / active

**sovereign-osctl frontend list [--json]**
:   The frontends (gnome · dashboards-kiosk · open-computer-kiosk · none) + staged/active

**sovereign-osctl frontend set <value> [--url U]**
:   Switch the boot frontend live, no reflash (root):

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
