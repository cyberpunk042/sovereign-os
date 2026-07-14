% SOVEREIGN-OSCTL-INSTALL(1) sovereign-os 0.2.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-install - installation, profiles, customization, and decommission

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

Bootstrap, profile selection, initialization, hooks, whitelabeling, image installation, deployment paths, configuration snapshots, and decommissioning.

This page owns 19 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. **sovereign-osctl help** remains authoritative for the
exact syntax shipped by the installed version.

# SAFETY MODEL

Image writes and decommissioning are destructive. Always run the plan form, verify the target fingerprint, keep the running root out of scope, and supply the dedicated confirmation only after reviewing the plan.

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

    sovereign-osctl profiles validate
    sovereign-osctl init
    sovereign-osctl install image --plan build/sain-01/output/sain-01.raw --to /dev/nvme1n1
    sovereign-osctl decommission --plan
    sovereign-osctl config-snapshot

# COMMAND REFERENCE

## profiles

**sovereign-osctl profiles list**
:   List declared profiles

**sovereign-osctl profiles show <id>**
:   Print profile YAML (raw, no mixin resolution)

**sovereign-osctl profiles show-effective <id> Print profile with mixins + parent resolved**
:   See the live help for behavior and options.

**sovereign-osctl profiles compare <a> <b>**
:   Unified diff of two profiles' EFFECTIVE (resolved) state

**sovereign-osctl profiles fork <base> <new>**
:   Scaffold a new profile from <base> with id <new> (validates immediately)

**sovereign-osctl profiles active**
:   Show active profile id

**sovereign-osctl profiles switch <id>**
:   Swap active profile (flags items requiring rebuild)

**sovereign-osctl profiles validate**
:   Schema-validate all profiles (raw + resolved)

**sovereign-osctl profiles generate-runtime <os-profile> <strategy> [--out <path>]**
:   See the live help for behavior and options.

**sovereign-osctl profiles create-orchestration <id> [--intent <i>] [--conductor <m>]**
:   See the live help for behavior and options.

**sovereign-osctl profiles flex show [--json]**
:   R224 (SDD-026 Z-3): print active profile +

**sovereign-osctl profiles flex set <key> <value> [--json]**
:   See the live help for behavior and options.

**sovereign-osctl profiles flex reset [--json] R224: clear every delta — revert to YAML**
:   See the live help for behavior and options.

**sovereign-osctl profiles flex history [--json]**
:   See the live help for behavior and options.

**sovereign-osctl profiles flex export [--output PATH] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl profiles flex import <bundle> [--mode replace|merge] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## whitelabel

**sovereign-osctl whitelabel show**
:   Show active whitelabel branding

**sovereign-osctl whitelabel apply <id>**
:   Re-render whitelabel surfaces on the running system

**sovereign-osctl whitelabel list**
:   List declared whitelabels

**sovereign-osctl whitelabel diff <id>**
:   Unified diff: active whitelabel → <id>

Run `sovereign-osctl help` for the complete version-matched grammar.

## hooks

**sovereign-osctl hooks list [<profile>]**
:   List hooks declared in a profile (default: active)

**sovereign-osctl hooks add <stage> <script-path> [--id <id>] [--mandatory] [--profile <id>]**
:   See the live help for behavior and options.

**sovereign-osctl hooks remove <id> [--profile <id>]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## decommission

**sovereign-osctl decommission start**
:   Begin decommission flow (interactive; confirms)

**sovereign-osctl decommission --plan**
:   Preview ALL 3 decommission phases (paths, sizes, commands); writes nothing

Run `sovereign-osctl help` for the complete version-matched grammar.

## install

**sovereign-osctl install image <img> --to <dev>**
:   Safely dd a built image to a target device

**sovereign-osctl install image --plan <img> --to <dev>**
:   Show fingerprint + plan, do nothing

Run `sovereign-osctl help` for the complete version-matched grammar.

## bootstrap

**sovereign-osctl bootstrap [arguments]**
:   || exit keeps doctor's nonzero exit (FAIL report) without firing the lib's ERR trap — a failing health report is a finding, not a crash (spurious "command failed: 'return 1'" on first installed run 2026-06-12).

Run `sovereign-osctl help` for the complete version-matched grammar.

## init

**sovereign-osctl init [--non-interactive]**
:   Interactive setup wizard — walk through 5 decisions

Run `sovereign-osctl help` for the complete version-matched grammar.

## wizard

**sovereign-osctl wizard [arguments]**
:   || exit keeps doctor's nonzero exit (FAIL report) without firing the lib's ERR trap — a failing health report is a finding, not a crash (spurious "command failed: 'return 1'" on first installed run 2026-06-12).

Run `sovereign-osctl help` for the complete version-matched grammar.

## operator-deps

**sovereign-osctl operator-deps list|plan|apply [--confirm] [--confirm-curl-shell] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## service-deps

**sovereign-osctl service-deps graph|drain|dot [--unit ...|--prefix P] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## install-paths

**sovereign-osctl install-paths show [--feature F] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl install-paths grey-out [--json]**
:   See the live help for behavior and options.

**sovereign-osctl install-paths choose <feat> --layer L [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## network-install-advisor

**sovereign-osctl network-install-advisor [arguments]**
:   R298 (E2.M12): unified storage health rollup. Composes logrotate posture + /proc/mdstat RAID + df partition free space + journal SystemMaxUse= into ONE operator-pull verdict (healthy / watch / degraded). Operator-named (§1b verbatim): "logs, log rotate, system usage, partitions and global and such. insights".

Run `sovereign-osctl help` for the complete version-matched grammar.

## operator-posture

**sovereign-osctl operator-posture [arguments]**
:   R301 (E1.M26): actual lspci -vv parse of per-device PCIe LnkCap vs LnkSta. Complements R270 pcie-policy advisory with concrete runtime measurement. Operator-named (§1b verbatim): "pci lane splits and whatever like virtualization or what we find relevant via search online and such".

Run `sovereign-osctl help` for the complete version-matched grammar.

## install-mode

**sovereign-osctl install-mode [arguments]**
:   R311 (E5.M7 closure): LLM-runtime parametrization advisor. Per-parameter catalog with hardware-aware recommended values (context_size / n_gpu_layers / cache_type_k+v / batch_size / parallel / mlock / mmap / flash_attn / rope_freq_base / temperature / top_p). Operator-named (§1b verbatim: "Model variants + quantizations + advanced features parametrization").

Run `sovereign-osctl help` for the complete version-matched grammar.

## config-snapshot-diff

**sovereign-osctl config-snapshot-diff [arguments]**
:   R337 (E1.M39): fan/cooling awareness advisor. lm-sensors fan readout + per-mode (idle/inference-ready/training/oc-burst) recommended curves + per-board BIOS-gate advice for software fan override. Operator-named §1b spec drop.

Run `sovereign-osctl help` for the complete version-matched grammar.

## snapshot-diff

**sovereign-osctl snapshot-diff [arguments]**
:   R335 (E2.M26): config-snapshot-diff verb. Given two R332 snapshots, emits per-overlay drift (added / removed / changed + per-key dotted-path diff). Sibling to R334 runtime diff.

Run `sovereign-osctl help` for the complete version-matched grammar.

## config-restore

**sovereign-osctl config-restore [arguments]**
:   R334 (E2.M25): snapshot-diff verb. Given two R322 state snapshots, emits per-probe diff (rc/verdict changes, new/ resolved attention items). Pre/post-change auditing.

Run `sovereign-osctl help` for the complete version-matched grammar.

## config-snapshot

**sovereign-osctl config-snapshot [arguments]**
:   R333 (E2.M24): config-restore companion to R332. Reads R332 snapshot JSON + verifies sha256s + replays overlays back to disk under triple-gate. Records to R327 audit log.

Run `sovereign-osctl help` for the complete version-matched grammar.

## overlay-drift

**sovereign-osctl overlay-drift [arguments]**
:   R327 (E9.M11): central apply-audit log query CLI. Reads /var/lib/sovereign-os/apply-audit.jsonl appended by every mutating verb. Operator-pull "who mutated what when?"

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
