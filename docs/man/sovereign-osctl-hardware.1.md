% SOVEREIGN-OSCTL-HARDWARE(1) sovereign-os 0.3.0 | sovereign-os Operator Manual
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
real dispatcher. The synopsis and descriptions are grounded in the
command handler or delegated-script contract at this build revision.
The top-level help is a discovery summary, not an exhaustive grammar.

# SAFETY MODEL

Treat set, apply, remediate, shutdown, restore, and mode-changing subcommands as privileged mutations. Capture status and configuration snapshots first; firmware recommendations are advisory until applied outside sovereign-osctl.

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

    sovereign-osctl inventory --json
    sovereign-osctl thermals
    sovereign-osctl gpu-watch
    sovereign-osctl power-status
    sovereign-osctl network status

# COMMAND REFERENCE

## thermals

**sovereign-osctl thermals [--json|--probe]**
:   Per-sensor thermal status (R175; reads R172 cached .prom or re-probes live)

## gpu-watch

**sovereign-osctl gpu-watch [--policy PATH] [--json] [--emit-metrics]**
:   See the handler for behavior and options.

## network

**sovereign-osctl network status [--json] [--component NAME]**
:   See the handler for behavior and options.

## cpu-mode

**sovereign-osctl cpu-mode show [--json]**
:   Current per-CPU governor + matched mode.

**sovereign-osctl cpu-mode list [--json]**
:   Enumerate the 4 named modes

**sovereign-osctl cpu-mode set <mode>**
:   R221 (SDD-026 Z-4): switch CPU governor

**sovereign-osctl cpu-mode auto [--apply] [--aggressive] [--json]**
:   See the handler for behavior and options.

## avx-mode

**sovereign-osctl avx-mode show [--json]**
:   The active AVX execution mode + whether its kernels are real or scaffold.

**sovereign-osctl avx-mode list**
:   The master modes — custom / builtin / hybrid / off.

**sovereign-osctl avx-mode inventory [--json]**
:   The full mode inventory — the M008 bit-cheats + cpu-dispatch paths + precision tiers.

**sovereign-osctl avx-mode set <mode>**
:   SDD-600: pick how the box uses AVX-512. Custom = the M002/M007/M008 bit-machine (policy becomes bits, token-by-token routing); BuiltIn-Features = stock AVX-512 math; Hybrid = both; Off = scalar. Custom/Hybrid kernels are scaffold today — the switch is recorded and gates them downstream.

## gpu-mode

**sovereign-osctl gpu-mode show [--json]**
:   R236 (SDD-026 Z-5): per-GPU power limit

**sovereign-osctl gpu-mode list [--json]**
:   R236: enumerate the 4 named GPU modes.

**sovereign-osctl gpu-mode set <mode>**
:   R236: write per-GPU power limit via

**sovereign-osctl gpu-mode auto [--apply] [--json]**
:   See the handler for behavior and options.

## dspark

**sovereign-osctl dspark [arguments]**
:   DSpark speculative decoding on/off — the DFlash (M083) successor (DeepSeek 2026-06-27), lossless speculative decoding. Opt-in but ON BY DEFAULT for now. status is read-only; enable/disable persist /etc/sovereign-os/dspark.toml, which the dspark-wrap.sh gate + the D-21 lm-orchestration features API both read. Verbs: status [--json] / enable / disable.

## gpu-remediate

**sovereign-osctl gpu-remediate [--apply] [--policy P] [--json]**
:   See the handler for behavior and options.

## nvidia-mps

**sovereign-osctl nvidia-mps [arguments]**
:   R551 (E11.M14): NVIDIA MPS controller. Shares each non-MIG GPU across concurrent inference processes (pulse / logic-engine / oracle-core + ad-hoc) without time-slicer context switches. Operator §1g: "Multi mode AI, multiple mode for the AI loadout".

## hugepages

**sovereign-osctl hugepages [arguments]**
:   R552 (E11.M15): HugePages sizer. Reserves 2MiB (or 1GiB) huge pages for inference engines (llama.cpp / vllm / bitnet) to reduce TLB pressure. Operator §1g: AVX-512 + 256GB RAM + ZMM ternary models — all benefit from huge-page-backed buffers.

## thp-mode

**sovereign-osctl thp-mode [arguments]**
:   R553 (E11.M16): Transparent HugePage controller. Orthogonal to R552 — THP is the opportunistic path; reserved hugepages are the static path. inference policy = madvise+defer (no compaction stalls). Operator §1g: predictable inference latency.

## irq-affinity

**sovereign-osctl irq-affinity [arguments]**
:   R554 (E11.M17): IRQ affinity controller. Moves all non-locked hardware-interrupt vectors onto a housekeeping CPU set so the inference cores (pulse / logic-engine / oracle-core) aren't preempted by NIC RX, NVMe completion, USB poll, etc. Operator §1g: peak-inference / sustained-burst latency hygiene.

## cpu-isolation

**sovereign-osctl cpu-isolation [arguments]**
:   R557 (E11.M20): CPU isolation cmdline emitter. Coordinated isolcpus/nohz_full/rcu_nocbs trifecta — actually removes the inference cores from the scheduler, the periodic tick, and RCU callback processing. Stronger than R554 IRQ pinning alone. Never edits GRUB (operator sovereignty boundary); emits a fragment file the operator merges on their own terms.

## nvidia-persistence

**sovereign-osctl nvidia-persistence [arguments]**
:   R556 (E11.M19): NVIDIA persistence mode controller. Without persistence ON, the driver tears down GPU state every time the last CUDA context exits → next first-prompt pays ~2s reinit latency. Operator §1g: zero first-prompt thermal spike + inference-ready warmup.

## workload-knobs

**sovereign-osctl workload-knobs [arguments]**
:   R555 (E11.M18): atomic orchestrator of the R551-R554 inference-latency primitives (MPS / hugepages / THP / IRQ). Reads R338 active workload mode, maps it to a bundle preset, and fans out to each underlying controller in one verb so the operator never has to remember four commands per mode switch.

## memory-profile

**sovereign-osctl memory-profile status [--json]**
:   See the handler for behavior and options.

**sovereign-osctl memory-profile advisory [--json]**
:   See the handler for behavior and options.

## bios-info

**sovereign-osctl bios-info show [--json]**
:   R251 (SDD-026 Z-17): BIOS + baseboard

**sovereign-osctl bios-info memory [--json]**
:   R251: DIMM-only detail (slot, channel,

**sovereign-osctl bios-info advisories [--json]**
:   See the handler for behavior and options.

## ram-advisor

**sovereign-osctl ram-advisor status|budget|advisory [--json]**
:   See the handler for behavior and options.

## net-perf

**sovereign-osctl net-perf probe|record|drift [--targets ...] [--threshold-pct N] [--json]**
:   See the handler for behavior and options.

## reverse-proxy

**sovereign-osctl reverse-proxy status|traefik|caddy|nginx|advisory [--json]**
:   See the handler for behavior and options.

## avx512-advisor

**sovereign-osctl avx512-advisor probe|workloads|advisory [--json]**
:   See the handler for behavior and options.

## gpu-card-advisor

**sovereign-osctl gpu-card-advisor detect|advisories|dual-card [--json]**
:   See the handler for behavior and options.

## pcie-policy

**sovereign-osctl pcie-policy status|share [--json]**
:   See the handler for behavior and options.

## memory-pressure

**sovereign-osctl memory-pressure status|psi|oom-events [--json]**
:   See the handler for behavior and options.

## dns-advisor

**sovereign-osctl dns-advisor status|providers|latency [--json]**
:   See the handler for behavior and options.

## services-advisor

**sovereign-osctl services-advisor cloudflared|tailscale|traefik|show [--json]**
:   See the handler for behavior and options.

## power-shutdown

**sovereign-osctl power-shutdown list [--json] R262 (SDD-029 R262): show the graceful-**
:   See the handler for behavior and options.

**sovereign-osctl power-shutdown plan [--manifest P] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl power-shutdown apply [--manifest P] [--confirm] [--dry-run] [--json]**
:   See the handler for behavior and options.

## power-status

**sovereign-osctl power-status psu [--json]**
:   R252 (SDD-026 Z-18): operator-declared

**sovereign-osctl power-status ups [--json]**
:   R252: live UPS state via NUT upsc

**sovereign-osctl power-status budget [--json] R252: PSU rated W vs estimated load**
:   See the handler for behavior and options.

**sovereign-osctl power-status advisories [--json]**
:   See the handler for behavior and options.

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

## fs

**sovereign-osctl fs usage [--threshold-pct N] [--json]**
:   See the handler for behavior and options.

**sovereign-osctl fs log-audit [--threshold-bytes N] [--root D] [--max-rows N] [--json]**
:   See the handler for behavior and options.

## raid

**sovereign-osctl raid status [--json]**
:   R223 (SDD-026 Z-9): compact per-md-array

**sovereign-osctl raid detail [<name>|--all] [--json]**
:   See the handler for behavior and options.

## storage-health

**sovereign-osctl storage-health {status|advisory|inputs}**
:   R298 (E2.M12): unified storage health rollup. Composes logrotate posture + /proc/mdstat RAID + df partition free space + journal SystemMaxUse= into ONE operator-pull verdict (healthy / watch / degraded). Operator-named (§1b verbatim): "logs, log rotate, system usage, partitions and global and such. insights".

## kernel-cmdline

**sovereign-osctl kernel-cmdline {status|diff|apply-hint}**
:   R305 (E1.M30): kernel cmdline parameter advisor — parse /proc/cmdline + diff against operator-pinned AI-workload recommended set (iommu=pt, amd_iommu=on, thp=madvise, etc.). Complements R239 kernel/tuning.py (which emits sysctl presets) with the loaded-cmdline-vs-recommended diff layer.

## memory-pressure-damper

**sovereign-osctl memory-pressure-damper {status|advisory}**
:   R304 (E1.M29): memory-pressure → OC-profile dampening advisor. Composes R269 + R292 to emit "dampen by N steps" recommendation when memory pressure spikes.

## gpu-wattage

**sovereign-osctl gpu-wattage {list|show|budget}**
:   Catalog idle, typical, peak, and OC-peak wattage for each GPU declared by the active operator overlay, then project the combined GPU budget against the configured PSU rating.

## battery-ladder

**sovereign-osctl battery-ladder {list|show|simulate}**
:   R302 (E1.M27): UPS battery escalation ladder — multi-threshold cascade beyond R293's single-profile registry: pre-alert at rem ≥ 30, warn-watch 20-30, drain-infer 10-20, drain-all 5-10, hard-shutdown < 5. Operator-named (§1b verbatim).

## pcie-lane-detect

**sovereign-osctl pcie-lane-detect {status|gpu|degraded}**
:   R301 (E1.M26): actual lspci -vv parse of per-device PCIe LnkCap vs LnkSta. Complements R270 pcie-policy advisory with concrete runtime measurement. Operator-named (§1b verbatim): "pci lane splits and whatever like virtualization or what we find relevant via search online and such".

## network-stack

**sovereign-osctl network-stack {list|status|troubleshoot}**
:   R319 (E3.M7): network runtime-stack advisor. Per-service runtime probe + troubleshoot guide beyond install-mode (R310). 5 default services across 4 axes (tailscale/cloudflared/traefik/systemd-resolved/suricata). Operator-named (§1b verbatim: "networks and in and out, the DNS, the Cloudflared ? the tailscale, Traefik").

## heat-oc-throttle

**sovereign-osctl heat-oc-throttle {status|recommend|apply}**
:   R318 (E1.M38): heat-tied OC auto-throttle with triple-gate. Composes R296 + R304 + R315 → min-recommended gpu_oc_multiplier. apply mutates only when --apply + --confirm-throttle + SOVEREIGN_OS_CONFIRM_DESTROY=YES all present. Operator-named (preserves NEVER-AUTO-MUTATES doctrine via explicit gate).

## inventory

**sovereign-osctl inventory {list|show|audit}**
:   R317 (E1.M37): hardware-inventory catalog — single source of truth for operator's EXACT hardware (CPU/GPU/PSU/UPS/RAM/NVMe/ board). Defaults from operator's verbatim spec drop; overlay support for swapping any slot. Other advisors compose against this catalog. Operator-named (§1b spec drop verbatim).

## wattage-heat-trend

**sovereign-osctl wattage-heat-trend {tick|status|history}**
:   R316 (E1.M36): real-time wattage+heat trend watcher. Periodic-sample daemon: wattage + GPU/CPU temp tuples to JSONL + rolling-window trend intelligence. Operator-named (§1b verbatim: "real time tracking and intelligence around it").

## xmp-oc-room

**sovereign-osctl xmp-oc-room {status|budget|recommend}**
:   R315 (E1.M35): XMP/OC profile room estimator under dual-GPU sustained load. Composes PSU rated W + estimated XMP/EXPO extra + CPU OC extra + dual-GPU sustained → budget-left + safe-(xmp, cpu_oc, gpu_oc)-combination matrix. Operator-named (§1b verbatim).

## apc-profile

**sovereign-osctl apc-profile {list|show|apply-hint}**
:   R314 (E1.M34): PSU/APC default-profile orchestration — 3 curated named profiles (conservative/balanced/aggressive) that bundle battery_pct thresholds × per-threshold actions × drain ordering × notify dispatch × shutdown commit. Composes R253 graceful-shutdown + R302 battery-ladder + R262 drain. Operator-named (§1b verbatim).

## psu-oc-mode

**sovereign-osctl psu-oc-mode {status|recipe|recommend}**
:   R313 (E1.M33): be Quiet! Dark Power Pro 13 1600W OC-mode orchestration — operator's exact PSU has a physical OC switch the OS can't detect; operator declares state via overlay + script returns safe-ceiling recommendation for R292/R294 OC composition. Operator-named (§1b verbatim).

## board-advisor

**sovereign-osctl board-advisor {status|advise|slot-map}**
:   R312 (E1.M32): operator's exact board ASUS ProArt X870E-CREATOR WIFI specific tuning advisor. PCIe slot allocation + M.2 speed matrix + dual-GPU bifurcation modes + BIOS-flashback recipe + memory training timeout + known issues. Operator-named (§1b verbatim).

## workload-mode

**sovereign-osctl workload-mode {status|modes|affected-advisors|set}**
:   R338 (E2.M27): workload-mode coordinator. Single source of truth for current operator workload mode (idle/inference-ready/ training/oc-burst). set mutates under triple-gate via R328 safe_apply helper. affected-advisors lists downstream surfaces.

## fan-advisor

**sovereign-osctl fan-advisor {status|recommend|modes|bios-gate}**
:   R337 (E1.M39): fan/cooling awareness advisor. lm-sensors fan readout + per-mode (idle/inference-ready/training/oc-burst) recommended curves + per-board BIOS-gate advice for software fan override. Operator-named §1b spec drop.

## ccd-pinning

**sovereign-osctl ccd-pinning [sub]**
:   R356 (§19.2): operator-verbatim CCD

## cpu-hotswap

**sovereign-osctl cpu-hotswap {status|per-cpu|transitions|swap-hint}**
:   R307 (E1.M31): CPU hotswap mode detection — per-CPU current governor / EPP / driver state + available transitions + swap-hint operator-runnable command. Complements R221/R230 (E1.M10 cpu-mode + auto-recommender) with the detect side. Operator-named (§1b verbatim).

## bios-directives

**sovereign-osctl bios-directives {list|show|check}**
:   R299 (E1.M24): ASUS X870E-CREATOR WIFI BIOS directives catalog — 12 specific settings (EXPO, SVM, IOMMU, ReBAR, Above 4G, PCIe Gen5, AVX-512, Fast Boot, CSM, etc) with per-setting rationale + runtime probe surface where possible. Operator-named (§1b verbatim).

## thermal-oc-budget

**sovereign-osctl thermal-oc-budget {status|advisory|inputs}**
:   R296 (E2.M10): heat budget tied to OC profile — composes R172 thermal-watch + R292 oc-headroom + R294 psu-oc into ONE combined "is your OC posture thermally + electrically safe?" verdict. Operator-named (§1b verbatim, on heat tracking under OC posture).

## gpu-possibility

**sovereign-osctl gpu-possibility {list|show|gaps}**
:   Report established and unverified capabilities for each GPU declared by the active operator overlay, including CPU and AVX-512 relationships relevant to the workload.

## psu-oc

**sovereign-osctl psu-oc {state|budget|projection}**
:   R294 (E1.M22): PSU OC-mode orchestration — be Quiet! Dark Power Pro 13 1600W + operator-declared OC-mode state + wattage-budget shift. Operator-named (§1b verbatim): "My PSU even have an overclock mode which might be important".

## power-profiles

**sovereign-osctl power-profiles {list|show|simulate|active}**
:   R293 (E1.M21): operator-pull power-management default-profile registry — composes R252/R253/R262/R265/R292 into named profiles (battery-threshold-graceful-shutdown, scheduled-graceful-poweroff, ac-loss-graceful-suspend, thermal-budget-throttle, psu-headroom-warn). Operator-named (§1b verbatim): "the PSU/APC integration with the power mangement and the scheduled shutdown when battery reach a certain point as one default profile."

## oc-headroom

**sovereign-osctl oc-headroom {status|advisory|inputs}**
:   R292 (E1.M20): operator's XMP + OC headroom model. Composes memory-profile (XMP/EXPO state) + gpu-watch (per-card power_limit) + power-status (PSU rated + real-time draw) into a 100%-usage projection + real-time deviance verdict. Operator-named (§1b verbatim): "considering XMP profile and OC profile and room for each and estimated at 100% usage and then real time tracking and intelligence around it."

## hardware-pressure

**sovereign-osctl hardware-pressure [arguments]**
:   M060 D-09 (R10102-R10105): unified hardware-pressure core — Linux PSI (/proc/pressure cpu/mem/io) + dual-CCD topology (M070) + GPU (nvidia-smi) + ZFS pool/dataset latency (M068) + scheduler backpressure (M058). Read -only; the sovereign-hardware-pressure-api daemon serves the D-09 cockpit dashboard from this same core. Verbs: status / psi / zfs (+ --json).

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
