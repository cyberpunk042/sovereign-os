% SOVEREIGN-OSCTL-INSTALL(1) sovereign-os 0.3.0 | sovereign-os Operator Manual
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
real dispatcher. The synopsis and descriptions are grounded in the
command handler or delegated-script contract at this build revision.
The top-level help is a discovery summary, not an exhaustive grammar.

# SAFETY MODEL

Image writes and decommissioning are destructive. Always run the plan form, verify the target fingerprint, keep the running root out of scope, and supply the dedicated confirmation only after reviewing the plan.

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
:   See the handler for behavior and options.

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
:   See the handler for behavior and options.

**sovereign-osctl profiles create-orchestration <id> [--intent <i>] [--conductor <m>]**
:   See the handler for behavior and options.

**sovereign-osctl profiles flex show [--json]**
:   R224 (SDD-026 Z-3): print active profile +

**sovereign-osctl profiles flex set <key> <value> [--json]**
:   See the handler for behavior and options.

**sovereign-osctl profiles flex reset [--json] R224: clear every delta — revert to YAML**
:   See the handler for behavior and options.

**sovereign-osctl profiles flex history [--json]**
:   See the handler for behavior and options.

**sovereign-osctl profiles flex export [--output PATH] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl profiles flex import <bundle> [--mode replace|merge] [--json]**
:   See the handler for behavior and options.

## whitelabel

**sovereign-osctl whitelabel show**
:   Show active whitelabel branding

**sovereign-osctl whitelabel apply <id>**
:   Re-render whitelabel surfaces on the running system

**sovereign-osctl whitelabel list**
:   List declared whitelabels

**sovereign-osctl whitelabel diff <id>**
:   Unified diff: active whitelabel → <id>

## hooks

**sovereign-osctl hooks list [<profile>]**
:   List hooks declared in a profile (default: active)

**sovereign-osctl hooks add <stage> <script-path> [--id <id>] [--mandatory] [--profile <id>]**
:   See the handler for behavior and options.

**sovereign-osctl hooks remove <id> [--profile <id>]**
:   See the handler for behavior and options.

## decommission

**sovereign-osctl decommission {--plan|plan}**
:   Preview all three destructive phases, targets, sizes, and commands. Writes nothing and requires no destructive environment gate.

**sovereign-osctl decommission start**
:   Begin phase 1 interactively: confirm, then securely wipe the state fabric at `tank/context`.

**sovereign-osctl decommission pool**
:   Run phase 2 and destroy the configured ZFS pool. Requires `SOVEREIGN_OS_CONFIRM_DESTROY=YES` and the hook's confirmation gates.

**sovereign-osctl decommission wipe**
:   Run phase 3 against block devices declared in `SOVEREIGN_OS_WIPE_DEVICES`. Uses `blkdiscard` for SSDs or `shred` otherwise and requires the destructive confirmation gate.

## install

**sovereign-osctl install image <img> --to <dev>**
:   Safely dd a built image to a target device

**sovereign-osctl install image --plan <img> --to <dev>**
:   Show fingerprint + plan, do nothing

## bootstrap

**sovereign-osctl bootstrap [arguments]**
:   Inspect and operate the master-spec bootstrap surface. Use the command's own help/status path before applying a bootstrap action.

## init

**sovereign-osctl init [--non-interactive]**
:   Interactive setup wizard covering six decisions: profile, substrate, Secure Boot, encryption, whitelabel, and agent layer

## wizard

**sovereign-osctl wizard [arguments]**
:   Run the guided operator wizard surface. It is distinct from `init`, which writes the six-decision build configuration.

## operator-deps

**sovereign-osctl operator-deps list|plan|apply [--confirm] [--confirm-curl-shell] [--json]**
:   See the handler for behavior and options.

## service-deps

**sovereign-osctl service-deps graph|drain|dot [--unit ...|--prefix P] [--json]**
:   See the handler for behavior and options.

## install-paths

**sovereign-osctl install-paths show [--feature F] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl install-paths grey-out [--json]**
:   See the handler for behavior and options.

**sovereign-osctl install-paths choose <feat> --layer L [--json]**
:   See the handler for behavior and options.

## network-install-advisor

**sovereign-osctl network-install-advisor {list|show|coexist|recommend}**
:   R297 (E2.M11): operator-pull network install-layer advisor — DNS / Cloudflared / Tailscale / Traefik with docker-vs-system install matrix + per-layer pros/cons + recommended defaults. Operator-named (§1b verbatim): "the DNS, the Cloudflared ? the tailscale, Traefik, non docker vs docker install ? when possible ? container level vs system level".

## operator-posture

**sovereign-osctl operator-posture {status|advisory}**
:   R300 (E1.M25): holistic operator-posture rollup. Synthesizes R292 (oc-headroom) + R294 (psu-oc) + R296 (thermal-oc-budget) + R298 (storage-health) + R299 (bios-directives) into ONE worst-axis verdict. Operator-named (§1b verbatim).

## install-mode

**sovereign-osctl install-mode {list|show|recommend}**
:   R310 (E2.M16): container-vs-system install-mode advisor. Per-installable component, advises system vs container based on isolation_need + dependency_footprint + ipc_requirement + root_required + gpu_passthrough + kernel_module. Emits operator-readable tradeoff matrix. Operator-named (§1b verbatim: "non docker vs docker install ? when possible ? container level vs system level").

## config-snapshot-diff

**sovereign-osctl config-snapshot-diff {diff}**
:   R335 (E2.M26): config-snapshot-diff verb. Given two R332 snapshots, emits per-overlay drift (added / removed / changed + per-key dotted-path diff). Sibling to R334 runtime diff.

## snapshot-diff

**sovereign-osctl snapshot-diff {diff}**
:   R334 (E2.M25): snapshot-diff verb. Given two R322 state snapshots, emits per-probe diff (rc/verdict changes, new/ resolved attention items). Pre/post-change auditing.

## config-restore

**sovereign-osctl config-restore {verify|apply}**
:   R333 (E2.M24): config-restore companion to R332. Reads R332 snapshot JSON + verifies sha256s + replays overlays back to disk under triple-gate. Records to R327 audit log.

## config-snapshot

**sovereign-osctl config-snapshot {capture|audit}**
:   R332 (E2.M23): config-snapshot for backup/migration. Captures complete operator-customized state into ONE portable JSON: overlays + audit + windows + inventory + helper-library manifest. Distinct from R322 state-snapshot (runtime-state).

## overlay-drift

**sovereign-osctl overlay-drift {list|show|audit}**
:   R325 (E2.M21): operator-overlay drift detector. Scans /etc/sovereign-os/*.toml + reports which knobs the operator has overridden vs shipped defaults. Operator-pull "what have I customized on this host?" — companion to R283 overlay doctrine + R322 state snapshot.

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
