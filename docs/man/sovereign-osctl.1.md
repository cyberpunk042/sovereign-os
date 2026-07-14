% SOVEREIGN-OSCTL(1) sovereign-os 0.3.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl - lifecycle management CLI for sovereign-os

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

**sovereign-osctl** {**help** [*command-or-topic*] | **commands** [**--json**] | **completion** {**bash** | **zsh** | **fish**} | **version**}

# DESCRIPTION

**sovereign-osctl** is the single operator entry point for inspecting,
configuring, auditing, maintaining, and decommissioning an installed
sovereign-os system. It operates both from a source checkout and from an
installed library tree.

The active OS profile is read from
`/etc/sovereign-os/active-profile` and falls back to `sain-01`.
Commands that mutate state retain their command-specific confirmation,
privilege, and dry-run gates. Bare **sovereign-osctl help** is a discovery
summary; **sovereign-osctl help** *command-or-topic* opens the owning topic
page. **sovereign-osctl commands** is the complete registry-backed inventory.
Use the command-specific help implemented by delegated tools where available.

# PRIMARY COMMAND FAMILIES

**status** [**--json**], **overview**, **doctor**
:   Inspect system state and run profile-conditioned health checks.

**assistant**, **init**, **wizard**, **next-steps**
:   Run onboarding, first-login, and guided operator flows.

**profiles**, **whitelabel**, **hooks**, **env**
:   Inspect and customize profiles, branding, lifecycle hooks, and
    `SOVEREIGN_OS_*` configuration.

**models**, **model-serve**, **inference**, **gateway**, **router**
:   Operate model catalogs, serving processes, inference tiers, the
    provider-inversion gateway, and routing.

**frontend**, **openclaw**, **open-computer**, **jobs**, **plane**
:   Operate the desktop/agent layer, background jobs, and the sovereign
    compute plane.

**trinity**, **weaver**, **auditor**, **selfdef**, **perimeter**
:   Inspect and manage Pulse, Weaver, Auditor, selfdef, and the Tetragon
    security perimeter.

**audit**, **diagnose**, **health**, **alerts**, **journal**, **history**
:   Run audit and diagnostic surfaces and inspect operational findings.

**maintenance**, **snapshot**, **config-snapshot**, **config-restore**
:   Run recurrent maintenance and configuration recovery workflows.

**install image** [**--plan**] *image* **--to** *device*
:   Plan or write a built image. The write path refuses the running root
    device and requires the explicit destructive confirmation gate.

**decommission --plan**
:   Preview every decommission phase without changing state.

**decommission start**
:   Begin the interactive, confirmation-gated decommission flow.

**doc-coverage**, **surface-map**, **ux-design-audit**,
**anti-minimization-audit**, **architecture-qa**, **coverage**
:   Inspect the project's governance and operator-surface contracts.

**commands**, **help**, **completion**, **version**
:   Discover the complete command surface, route to owning manuals, emit
    Bash/Zsh/Fish completion, and inspect the installed CLI version.

# MANUAL SUITE

The main page explains the lifecycle and safety model. Detailed syntax,
workflows, ownership, and examples are divided by operator concern:

**sovereign-osctl-models**(1)
:   Models, inference, routing, serving, evaluation, adaptation, and science.

**sovereign-osctl-agents**(1)
:   Frontends, agent runtimes, background jobs, compute-plane placement,
    state fabric, sessions, approvals, and rollback.

**sovereign-osctl-hardware**(1)
:   CPU, GPU, memory, storage, network, PCIe, thermals, power, and BIOS.

**sovereign-osctl-security**(1)
:   Perimeter, selfdef, Secure Boot, authentication, permissions, hardening,
    firewall, trust, and audit.

**sovereign-osctl-operations**(1)
:   Status, diagnostics, observability, maintenance, recovery, and daily use.

**sovereign-osctl-governance**(1)
:   Architecture, doctrine, compliance, UX, documentation, and surface audits.

**sovereign-osctl-install**(1)
:   Bootstrap, profiles, initialization, customization, image installation,
    configuration snapshots, and decommissioning.

# COMPLETE TOP-LEVEL COMMAND INDEX

This index is pinned by a lint contract to the real top-level dispatcher.
For subcommands and options, consult the owning topic page. The live
**sovereign-osctl commands** output is generated from the same ownership
registry. Bare **sovereign-osctl help** remains a concise summary.

**status**,  **overview**,  **doctor**,  **assistant**,  **profiles**,  **whitelabel**

**perimeter**,  **selfdef**,  **openclaw**,  **open-computer**,  **models**,  **audit**

**hooks**,  **maintenance**,  **decommission**,  **install**,  **secure-boot**,  **bootstrap**

**trinity**,  **init**,  **wizard**,  **env**,  **inference**,  **router**

**metrics**,  **alerts**,  **journal**,  **history**,  **thermals**,  **gpu-watch**

**science**,  **gateway**,  **permission**,  **jobs**,  **plane**,  **model-serve**

**network**,  **cpu-mode**,  **gpu-mode**,  **dspark**,  **gpu-remediate**,  **nvidia-mps**

**hugepages**,  **thp-mode**,  **irq-affinity**,  **cpu-isolation**,  **nvidia-persistence**,  **workload-knobs**

**memory-profile**,  **bios-info**,  **diagnose**,  **operator-deps**,  **operator-rules**,  **next-steps**

**wasm-aot**,  **zmm-ternary**,  **ram-advisor**,  **service-deps**,  **net-perf**,  **reverse-proxy**

**severity**,  **avx512-advisor**,  **gpu-card-advisor**,  **pcie-policy**,  **memory-pressure**,  **dns-advisor**

**services-advisor**,  **power-shutdown**,  **power-status**,  **virt-info**,  **fs**,  **raid**

**health**,  **insights**,  **install-paths**,  **kernel**,  **services**,  **events**

**notify**,  **dashboard**,  **mcp-aggregate**,  **storage-health**,  **network-install-advisor**,  **kernel-cmdline**

**memory-pressure-damper**,  **gpu-wattage**,  **battery-ladder**,  **pcie-lane-detect**,  **operator-posture**,  **network-stack**

**heat-oc-throttle**,  **inventory**,  **wattage-heat-trend**,  **xmp-oc-room**,  **apc-profile**,  **psu-oc-mode**

**board-advisor**,  **model-params**,  **install-mode**,  **workload-mode**,  **fan-advisor**,  **config-snapshot-diff**

**snapshot-diff**,  **config-restore**,  **config-snapshot**,  **self-test**,  **next-action**,  **apply-audit**

**overlay-drift**,  **fleet-aggregate**,  **maintenance-window**,  **snapshot**,  **rounds**,  **cot**

**guide**,  **model-adapt**,  **module-state**,  **model-build**,  **morning-brief**,  **network-topology**

**state-fabric**,  **ccd-pinning**,  **repl**,  **search**,  **layers**,  **quarterly-review**

**doctrine-status**,  **verbatim-render**,  **coverage**,  **architecture-qa**,  **autohealth**,  **cpu-hotswap**

**hardening-base**,  **bios-directives**,  **thermal-oc-budget**,  **gpu-possibility**,  **psu-oc**,  **power-profiles**

**oc-headroom**,  **research-loop**,  **lifecycle**,  **workflow**,  **auth-tier**,  **hardware-pressure**

**model-health**,  **traces**,  **costs**,  **cost-policy**,  **adapters**,  **evals**

**sessions**,  **approvals**,  **rollback**,  **memory-changes**,  **grants-mirror**,  **quarantine-mirror**

**trust-mirror**,  **sandbox-mirror**,  **profile-mirror**,  **capability-mirror**,  **audit-mirror**,  **rules-mirror**

**tui-mirror**,  **cli-mirror**,  **m060-health**,  **super-model**,  **peace-machine**,  **peace-check**

**dashboards**,  **frontend**,  **compliance**,  **ux-design-audit**,  **anti-minimization-audit**,  **doc-coverage**

**surface-map**,  **weaver**,  **auditor**,  **master-dashboard**,  **edge-firewall**,  **network-edge**

**global-history**,  **bashrc**,  **ms022-doctor**,  **m060-doctor**

**commands**,  **completion**,  **help**,  **version**

# ENVIRONMENT

**SOVEREIGN_OS_LIB**
:   Override the library directory. The selected directory must contain
    `lib/common.sh`.

**SOVEREIGN_OS_PROFILE**
:   Override the active OS profile for the current invocation.

**SOVEREIGN_OS_NONINTERACTIVE**
:   Disable interactive prompting where supported. Individual destructive
    operations may still require their dedicated confirmation gate.

**SOVEREIGN_OS_ASSUME_YES**
:   Set to `1` for commands that explicitly support non-interactive
    confirmation. It does not replace destructive-operation gates.

**SOVEREIGN_OS_CONFIRM_DESTROY**
:   Must be set to `YES` where a destructive install or decommission
    operation explicitly requires it.

**SOVEREIGN_OS_LOG_LEVEL**
:   Logging threshold: `debug`, `info`, `warn`, or `error`.

**SOVEREIGN_OS_METRICS_DIR**
:   Prometheus textfile collector directory.

**SOVEREIGN_OS_METRICS_DISABLE**
:   Set to `1` to suppress Layer B metric emission.

All supported variables and their consumers are discoverable through
**sovereign-osctl env list**.

# FILES

**/etc/sovereign-os/active-profile**
:   Installed active-profile selector.

**/etc/sovereign-os/active-whitelabel**
:   Installed whitelabel selector.

**/usr/local/lib/sovereign-os**
:   Default installed library tree.

**/usr/lib/sovereign-os**
:   Legacy library location.

**/opt/sovereign-os**
:   Alternate vendor tree used by installed services.

**.sovereign-os/init-state.yaml**
:   Setup-wizard state in a repository or operator working directory.

**/var/lib/sovereign-os/**
:   Per-machine runtime state.

**/mnt/vault/models/**
:   Model catalog on ZFS-tiered profiles.

# EXAMPLES

Inspect system state in machine-readable form:

    sovereign-osctl status --json
    sovereign-osctl doctor

Inspect the effective primary profile:

    sovereign-osctl profiles show-effective sain-01

Inspect model placement options:

    sovereign-osctl models suggest --runtime-profile high-concurrency --json

Verify build provenance deeply:

    sovereign-osctl audit provenance --deep       build/sain-01/output/build-provenance.json

Plan image installation without writing:

    sovereign-osctl install image --plan       build/sain-01/output/sain-01.raw --to /dev/nvme1n1

# EXIT STATUS

Zero indicates success. Non-zero indicates invalid input, a failed check,
an unavailable dependency, a refused safety gate, or an operational
failure. Some audit and coverage commands use status 2 to report findings
or gaps.

# SEE ALSO

**sovereign-osctl-models**(1), **sovereign-osctl-agents**(1),
**sovereign-osctl-hardware**(1), **sovereign-osctl-security**(1),
**sovereign-osctl-operations**(1), **sovereign-osctl-governance**(1),
**sovereign-osctl-install**(1), **systemctl**(1), **journalctl**(1),
**podman**(1), **zpool**(8), **zfs**(8)

Project guides: `docs/src/ops/manage.md` and
`docs/src/operator-journey.md`.

# REPORTING BUGS

GitHub: <https://github.com/cyberpunk042/sovereign-os/issues>

# LICENSE

AGPL-3.0-or-later
