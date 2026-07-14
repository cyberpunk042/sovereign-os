% SOVEREIGN-OSCTL-HARDWARE(1) sovereign-os 0.2.0 | sovereign-os Operator Manual
% cyberpunk042 and sovereign-os contributors
% 2026-07-14

# NAME

sovereign-osctl-hardware - hardware, power, storage, and network

# SYNOPSIS

**sovereign-osctl** *command* [*subcommand*] [*options*]

# DESCRIPTION

Read-only inventory and advisors plus gated controls for CPU, GPU, memory, PCIe, storage, thermals, power, BIOS, and networking.

This page owns 55 top-level commands. Ownership is defined in
`docs/man/sovereign-osctl-command-topics.json` and checked against the
real dispatcher. **sovereign-osctl help** remains authoritative for the
exact syntax shipped by the installed version.

# SAFETY MODEL

Treat set, apply, remediate, shutdown, restore, and mode-changing subcommands as privileged mutations. Capture status and configuration snapshots first; firmware recommendations are advisory until applied outside sovereign-osctl.

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

    sovereign-osctl inventory --json
    sovereign-osctl thermals
    sovereign-osctl gpu-watch
    sovereign-osctl power-status
    sovereign-osctl network status

# COMMAND REFERENCE

## thermals

**sovereign-osctl thermals [--json|--probe]**
:   Per-sensor thermal status (R175; reads R172 cached .prom or re-probes live)

Run `sovereign-osctl help` for the complete version-matched grammar.

## gpu-watch

**sovereign-osctl gpu-watch [--policy PATH] [--json] [--emit-metrics]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## network

**sovereign-osctl network status [--json] [--component NAME]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## cpu-mode

**sovereign-osctl cpu-mode show [--json]**
:   Current per-CPU governor + matched mode.

**sovereign-osctl cpu-mode list [--json]**
:   Enumerate the 4 named modes

**sovereign-osctl cpu-mode set <mode>**
:   R221 (SDD-026 Z-4): switch CPU governor

**sovereign-osctl cpu-mode auto [--apply] [--aggressive] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## gpu-mode

**sovereign-osctl gpu-mode show [--json]**
:   R236 (SDD-026 Z-5): per-GPU power limit

**sovereign-osctl gpu-mode list [--json]**
:   R236: enumerate the 4 named GPU modes.

**sovereign-osctl gpu-mode set <mode>**
:   R236: write per-GPU power limit via

**sovereign-osctl gpu-mode auto [--apply] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## dspark

**sovereign-osctl dspark [arguments]**
:   R236 (SDD-026 Z-5 extension): GPU hotswap modes. conservative / balanced / sustained / peak — targets derived from operator-set safe_limit_watts in gpu-policy.toml. Operator-named "Same for the GPU I guess" + R230 auto pattern.

Run `sovereign-osctl help` for the complete version-matched grammar.

## gpu-remediate

**sovereign-osctl gpu-remediate [--apply] [--policy P] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## nvidia-mps

**sovereign-osctl nvidia-mps [arguments]**
:   R249 (SDD-026 Z-5 closure): auto-apply R219 fix commands. Operator-named "warn deviance from perfection" loop closure.

Run `sovereign-osctl help` for the complete version-matched grammar.

## hugepages

**sovereign-osctl hugepages [arguments]**
:   R551 (E11.M14): NVIDIA MPS controller. Shares each non-MIG GPU across concurrent inference processes (pulse / logic-engine / oracle-core + ad-hoc) without time-slicer context switches. Operator §1g: "Multi mode AI, multiple mode for the AI loadout".

Run `sovereign-osctl help` for the complete version-matched grammar.

## thp-mode

**sovereign-osctl thp-mode [arguments]**
:   R552 (E11.M15): HugePages sizer. Reserves 2MiB (or 1GiB) huge pages for inference engines (llama.cpp / vllm / bitnet) to reduce TLB pressure. Operator §1g: AVX-512 + 256GB RAM + ZMM ternary models — all benefit from huge-page-backed buffers.

Run `sovereign-osctl help` for the complete version-matched grammar.

## irq-affinity

**sovereign-osctl irq-affinity [arguments]**
:   R553 (E11.M16): Transparent HugePage controller. Orthogonal to R552 — THP is the opportunistic path; reserved hugepages are the static path. inference policy = madvise+defer (no compaction stalls). Operator §1g: predictable inference latency.

Run `sovereign-osctl help` for the complete version-matched grammar.

## cpu-isolation

**sovereign-osctl cpu-isolation [arguments]**
:   R554 (E11.M17): IRQ affinity controller. Moves all non-locked hardware-interrupt vectors onto a housekeeping CPU set so the inference cores (pulse / logic-engine / oracle-core) aren't preempted by NIC RX, NVMe completion, USB poll, etc. Operator §1g: peak-inference / sustained-burst latency hygiene.

Run `sovereign-osctl help` for the complete version-matched grammar.

## nvidia-persistence

**sovereign-osctl nvidia-persistence [arguments]**
:   R557 (E11.M20): CPU isolation cmdline emitter. Coordinated isolcpus/nohz_full/rcu_nocbs trifecta — actually removes the inference cores from the scheduler, the periodic tick, and RCU callback processing. Stronger than R554 IRQ pinning alone. Never edits GRUB (operator sovereignty boundary); emits a fragment file the operator merges on their own terms.

Run `sovereign-osctl help` for the complete version-matched grammar.

## workload-knobs

**sovereign-osctl workload-knobs [arguments]**
:   R556 (E11.M19): NVIDIA persistence mode controller. Without persistence ON, the driver tears down GPU state every time the last CUDA context exits → next first-prompt pays ~2s reinit latency. Operator §1g: zero first-prompt thermal spike + inference-ready warmup.

Run `sovereign-osctl help` for the complete version-matched grammar.

## memory-profile

**sovereign-osctl memory-profile status [--json]**
:   See the live help for behavior and options.

**sovereign-osctl memory-profile advisory [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## bios-info

**sovereign-osctl bios-info show [--json]**
:   R251 (SDD-026 Z-17): BIOS + baseboard

**sovereign-osctl bios-info memory [--json]**
:   R251: DIMM-only detail (slot, channel,

**sovereign-osctl bios-info advisories [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## ram-advisor

**sovereign-osctl ram-advisor status|budget|advisory [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## net-perf

**sovereign-osctl net-perf probe|record|drift [--targets ...] [--threshold-pct N] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## reverse-proxy

**sovereign-osctl reverse-proxy status|traefik|caddy|nginx|advisory [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## avx512-advisor

**sovereign-osctl avx512-advisor probe|workloads|advisory [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## gpu-card-advisor

**sovereign-osctl gpu-card-advisor detect|advisories|dual-card [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## pcie-policy

**sovereign-osctl pcie-policy status|share [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## memory-pressure

**sovereign-osctl memory-pressure status|psi|oom-events [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## dns-advisor

**sovereign-osctl dns-advisor status|providers|latency [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## services-advisor

**sovereign-osctl services-advisor cloudflared|tailscale|traefik|show [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## power-shutdown

**sovereign-osctl power-shutdown list [--json] R262 (SDD-029 R262): show the graceful-**
:   See the live help for behavior and options.

**sovereign-osctl power-shutdown plan [--manifest P] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl power-shutdown apply [--manifest P] [--confirm] [--dry-run] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## power-status

**sovereign-osctl power-status psu [--json]**
:   R252 (SDD-026 Z-18): operator-declared

**sovereign-osctl power-status ups [--json]**
:   R252: live UPS state via NUT upsc

**sovereign-osctl power-status budget [--json] R252: PSU rated W vs estimated load**
:   See the live help for behavior and options.

**sovereign-osctl power-status advisories [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## virt-info

**sovereign-osctl virt-info show [--json]**
:   R255 (SDD-026 Z-19): virtualization +

**sovereign-osctl virt-info cpu [--json]**
:   R255: CPU virt flags (vmx/svm + EPT/NPT).

**sovereign-osctl virt-info kvm [--json]**
:   R255: KVM kernel module + /dev/kvm +

**sovereign-osctl virt-info iommu [--json]**
:   R255: IOMMU sysfs + kernel cmdline

**sovereign-osctl virt-info pci [--json]**
:   R255: per-device PCIe LnkSta width +

**sovereign-osctl virt-info runtimes [--json]**
:   R255: docker / podman / containerd /

Run `sovereign-osctl help` for the complete version-matched grammar.

## fs

**sovereign-osctl fs usage [--threshold-pct N] [--json]**
:   See the live help for behavior and options.

**sovereign-osctl fs log-audit [--threshold-bytes N] [--root D] [--max-rows N] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## raid

**sovereign-osctl raid status [--json]**
:   R223 (SDD-026 Z-9): compact per-md-array

**sovereign-osctl raid detail [<name>|--all] [--json]**
:   See the live help for behavior and options.

Run `sovereign-osctl help` for the complete version-matched grammar.

## storage-health

**sovereign-osctl storage-health [arguments]**
:   R286 (E7.M5 / closes Q-019 referenced in SDD-002): cross-repo MCP-tool aggregator. Emits a unified manifest of MCP tools exposed by sovereign-os (local read-only verbs) PLUS, when --upstream-selfdef <host>:<port> is given, the selfdef MCP TCP transport (SD-R94) is proxied. Operator-named (§1b mandate): "Cross-repo MCP-tool aggregator (sovereign-os surfaces selfdef tools too)".

Run `sovereign-osctl help` for the complete version-matched grammar.

## kernel-cmdline

**sovereign-osctl kernel-cmdline [arguments]**
:   R297 (E2.M11): operator-pull network install-layer advisor — DNS / Cloudflared / Tailscale / Traefik with docker-vs-system install matrix + per-layer pros/cons + recommended defaults. Operator-named (§1b verbatim): "the DNS, the Cloudflared ? the tailscale, Traefik, non docker vs docker install ? when possible ? container level vs system level".

Run `sovereign-osctl help` for the complete version-matched grammar.

## memory-pressure-damper

**sovereign-osctl memory-pressure-damper [arguments]**
:   R305 (E1.M30): kernel cmdline parameter advisor — parse /proc/cmdline + diff against operator-pinned AI-workload recommended set (iommu=pt, amd_iommu=on, thp=madvise, etc.). Complements R239 kernel/tuning.py (which emits sysctl presets) with the loaded-cmdline-vs-recommended diff layer.

Run `sovereign-osctl help` for the complete version-matched grammar.

## gpu-wattage

**sovereign-osctl gpu-wattage [arguments]**
:   R304 (E1.M29): memory-pressure → OC-profile dampening advisor. Composes R269 + R292 to emit "dampen by N steps" recommendation when memory pressure spikes.

Run `sovereign-osctl help` for the complete version-matched grammar.

## battery-ladder

**sovereign-osctl battery-ladder [arguments]**
:   R303 (E1.M28): GPU per-card per-mode wattage catalog. RTX 3090 + RTX PRO 6000 idle/typical/peak/oc-peak watts + dual-card budget projection vs PSU rated. Operator-named (§1b verbatim).

Run `sovereign-osctl help` for the complete version-matched grammar.

## pcie-lane-detect

**sovereign-osctl pcie-lane-detect [arguments]**
:   R302 (E1.M27): UPS battery escalation ladder — multi-threshold cascade beyond R293's single-profile registry: pre-alert at rem ≥ 30, warn-watch 20-30, drain-infer 10-20, drain-all 5-10, hard-shutdown < 5. Operator-named (§1b verbatim).

Run `sovereign-osctl help` for the complete version-matched grammar.

## network-stack

**sovereign-osctl network-stack [arguments]**
:   R300 (E1.M25): holistic operator-posture rollup. Synthesizes R292 (oc-headroom) + R294 (psu-oc) + R296 (thermal-oc-budget) + R298 (storage-health) + R299 (bios-directives) into ONE worst-axis verdict. Operator-named (§1b verbatim).

Run `sovereign-osctl help` for the complete version-matched grammar.

## heat-oc-throttle

**sovereign-osctl heat-oc-throttle [arguments]**
:   R319 (E3.M7): network runtime-stack advisor. Per-service runtime probe + troubleshoot guide beyond install-mode (R310). 5 default services across 4 axes (tailscale/cloudflared/traefik/systemd-resolved/suricata). Operator-named (§1b verbatim: "networks and in and out, the DNS, the Cloudflared ? the tailscale, Traefik").

Run `sovereign-osctl help` for the complete version-matched grammar.

## inventory

**sovereign-osctl inventory [arguments]**
:   R318 (E1.M38): heat-tied OC auto-throttle with triple-gate. Composes R296 + R304 + R315 → min-recommended gpu_oc_multiplier. apply mutates only when --apply + --confirm-throttle + SOVEREIGN_OS_CONFIRM_DESTROY=YES all present. Operator-named (preserves NEVER-AUTO-MUTATES doctrine via explicit gate).

Run `sovereign-osctl help` for the complete version-matched grammar.

## wattage-heat-trend

**sovereign-osctl wattage-heat-trend [arguments]**
:   R317 (E1.M37): hardware-inventory catalog — single source of truth for operator's EXACT hardware (CPU/GPU/PSU/UPS/RAM/NVMe/ board). Defaults from operator's verbatim spec drop; overlay support for swapping any slot. Other advisors compose against this catalog. Operator-named (§1b spec drop verbatim).

Run `sovereign-osctl help` for the complete version-matched grammar.

## xmp-oc-room

**sovereign-osctl xmp-oc-room [arguments]**
:   R316 (E1.M36): real-time wattage+heat trend watcher. Periodic-sample daemon: wattage + GPU/CPU temp tuples to JSONL + rolling-window trend intelligence. Operator-named (§1b verbatim: "real time tracking and intelligence around it").

Run `sovereign-osctl help` for the complete version-matched grammar.

## apc-profile

**sovereign-osctl apc-profile [arguments]**
:   R315 (E1.M35): XMP/OC profile room estimator under dual-GPU sustained load. Composes PSU rated W + estimated XMP/EXPO extra + CPU OC extra + dual-GPU sustained → budget-left + safe-(xmp, cpu_oc, gpu_oc)-combination matrix. Operator-named (§1b verbatim).

Run `sovereign-osctl help` for the complete version-matched grammar.

## psu-oc-mode

**sovereign-osctl psu-oc-mode [arguments]**
:   Operator command in the hardware surface. Inspect the live help and status/plan forms before use.

Run `sovereign-osctl help` for the complete version-matched grammar.

## board-advisor

**sovereign-osctl board-advisor [arguments]**
:   R313 (E1.M33): be Quiet! Dark Power Pro 13 1600W OC-mode orchestration — operator's exact PSU has a physical OC switch the OS can't detect; operator declares state via overlay + script returns safe-ceiling recommendation for R292/R294 OC composition. Operator-named (§1b verbatim).

Run `sovereign-osctl help` for the complete version-matched grammar.

## workload-mode

**sovereign-osctl workload-mode [arguments]**
:   R310 (E2.M16): container-vs-system install-mode advisor. Per-installable component, advises system vs container based on isolation_need + dependency_footprint + ipc_requirement + root_required + gpu_passthrough + kernel_module. Emits operator-readable tradeoff matrix. Operator-named (§1b verbatim: "non docker vs docker install ? when possible ? container level vs system level").

Run `sovereign-osctl help` for the complete version-matched grammar.

## fan-advisor

**sovereign-osctl fan-advisor [arguments]**
:   R338 (E2.M27): workload-mode coordinator. Single source of truth for current operator workload mode (idle/inference-ready/ training/oc-burst). set mutates under triple-gate via R328 safe_apply helper. affected-advisors lists downstream surfaces.

Run `sovereign-osctl help` for the complete version-matched grammar.

## ccd-pinning

**sovereign-osctl ccd-pinning [sub]**
:   R356 (§19.2): operator-verbatim CCD

Run `sovereign-osctl help` for the complete version-matched grammar.

## cpu-hotswap

**sovereign-osctl cpu-hotswap [arguments]**
:   Operator command in the hardware surface. Inspect the live help and status/plan forms before use.

Run `sovereign-osctl help` for the complete version-matched grammar.

## bios-directives

**sovereign-osctl bios-directives [arguments]**
:   R306 (E2.M13): Debian 13 base-system hardening catalog — 12 OS-level items (sysctl hardening + AppArmor + unattended- upgrades + auditd + fail2ban + sshd config). Per-item runtime probe + recommended value + operator-readable rationale. Complements R299 (BIOS layer) + R171 (systemd unit layer).

Run `sovereign-osctl help` for the complete version-matched grammar.

## thermal-oc-budget

**sovereign-osctl thermal-oc-budget [arguments]**
:   R299 (E1.M24): ASUS X870E-CREATOR WIFI BIOS directives catalog — 12 specific settings (EXPO, SVM, IOMMU, ReBAR, Above 4G, PCIe Gen5, AVX-512, Fast Boot, CSM, etc) with per-setting rationale + runtime probe surface where possible. Operator-named (§1b verbatim).

Run `sovereign-osctl help` for the complete version-matched grammar.

## gpu-possibility

**sovereign-osctl gpu-possibility [arguments]**
:   R296 (E2.M10): heat budget tied to OC profile — composes R172 thermal-watch + R292 oc-headroom + R294 psu-oc into ONE combined "is your OC posture thermally + electrically safe?" verdict. Operator-named (§1b verbatim, on heat tracking under OC posture).

Run `sovereign-osctl help` for the complete version-matched grammar.

## psu-oc

**sovereign-osctl psu-oc [arguments]**
:   R295 (E1.M23): operator-pull GPU possibility catalog — established vs non-established per-card capabilities for the operator's RTX 3090 + RTX PRO 6000 dual rig. Operator-named (§1b verbatim): "RTX 3090 details and possibilities established and non-established, same for the RTX Pro 6000 and the CPU and AVX512".

Run `sovereign-osctl help` for the complete version-matched grammar.

## power-profiles

**sovereign-osctl power-profiles [arguments]**
:   R294 (E1.M22): PSU OC-mode orchestration — be Quiet! Dark Power Pro 13 1600W + operator-declared OC-mode state + wattage-budget shift. Operator-named (§1b verbatim): "My PSU even have an overclock mode which might be important".

Run `sovereign-osctl help` for the complete version-matched grammar.

## oc-headroom

**sovereign-osctl oc-headroom [arguments]**
:   R293 (E1.M21): operator-pull power-management default-profile registry — composes R252/R253/R262/R265/R292 into named profiles (battery-threshold-graceful-shutdown, scheduled-graceful-poweroff, ac-loss-graceful-suspend, thermal-budget-throttle, psu-headroom-warn). Operator-named (§1b verbatim): "the PSU/APC integration with the power mangement and the scheduled shutdown when battery reach a certain point as one default profile."

Run `sovereign-osctl help` for the complete version-matched grammar.

## hardware-pressure

**sovereign-osctl hardware-pressure [arguments]**
:   R450 (E11.M7): operator §1g 6-tier auth ladder (no-auth → basic → advanced → social → enterprise → network-level). Per-dashboard tier registry + upgrade matrix + triple-gated set.

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
