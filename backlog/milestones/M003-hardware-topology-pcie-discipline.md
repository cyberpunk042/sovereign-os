# M003 — Hardware topology + PCIe lane discipline

> Parent: `backlog/milestones/INDEX.md` row M003 (dump 213–565).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 213–565.
> All entries below extracted from the dump line range. No invention.

## Epics (E0020–E0031)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0020 | AMD Ryzen 9 9900X Zen 5 — single-cycle native 512-bit AVX-512 | 215 |
| E0021 | ASUS ProArt X870E-Creator — dual PCIe 5.0 x8/x8 symmetric / IOMMU topology for VFIO | 216 |
| E0022 | RTX PRO 6000 Blackwell (96 GB GDDR7) Oracle Core — large model residence / FP16 unquantized | 217 |
| E0023 | RTX 3090 (24 GB GDDR6X) Logic Engine — VFIO-isolated sandbox / speculative decoding | 218 |
| E0024 | 256 GB DDR5 (initial 128 GB) — system context + ZFS ARC headroom | 219 |
| E0025 | 2× NVMe PCIe 5.0 in ZFS RAID-0 — 31.5 GB/s sequential target | 220 |
| E0026 | Marvell AQC113C 10GbE + Intel I226-V 2.5GbE — asymmetric VLAN (mgmt vs data) | 221 |
| E0027 | PCIe lane-sharing trap — PCIEX16(G5)_2 shares lanes with M.2_2 | 243–252 |
| E0028 | Better layout — Blackwell x8 + 3090 x8 + M.2_1 x4 + chipset NVMe x4 | 258–266 |
| E0029 | Power envelope — 600W Blackwell + 350W 3090 + 120W CPU + 80–150W board/NVMe/fans | 348–353 |
| E0030 | 1600W PSU minimum / 2000W quiet headroom | 355 |
| E0031 | CUDA bare-metal PCIe P2P incompatible with IOMMU on Linux | 597 |

## Modules (M00029–M00044) — 16 modules

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00029 | 9900X CPUID detection — Zen 5 family + AVX-512 family flag verification | 215 | E0020 |
| M00030 | Zen 5 vs Zen 4 datapath — single-cycle full-width 512-bit vs double-pumped 256-bit | 215 | E0020 |
| M00031 | ProArt X870E-Creator slot map — PCIEX16_1 / PCIEX16_2 / M.2_1 / M.2_2 / M.2_3 / M.2_4 | 216 | E0021 |
| M00032 | IOMMU group probe — verify Blackwell + 3090 in distinct groups | 216 | E0021 |
| M00033 | Blackwell Oracle resident-model policy — keep model warm, large KV unquantized | 217 | E0022 |
| M00034 | Blackwell hardware spec — 96 GB GDDR7 / 1.8 TB/s / PCIe Gen 5 / MIG / FP4 Tensor Cores / 600W | 267 | E0022 |
| M00035 | 3090 Logic Engine — VFIO-isolated sandbox / draft model / speculative decoding | 218 | E0023 |
| M00036 | 3090 hardware spec — 24 GB GDDR6X / PCIe Gen 4 / ~350W | 218 | E0023 |
| M00037 | DDR5 256 GB capacity — workstation feel; 128 GB intermediate | 219 | E0024 |
| M00038 | DDR5 4-DIMM topology — ProArt X870E-Creator board max | 331 | E0024 |
| M00039 | NVMe PCIe 5.0 x4 + x4 = 31.5 GB/s theoretical sequential | 220 | E0025 |
| M00040 | NVMe ZFS RAID-0 layout — scratch / cache / datasets / artifacts only (RAID 0 is not durability) | 343–344 | E0025 |
| M00041 | Marvell AQC113C 10GbE driver `atlantic` | 221 | E0026 |
| M00042 | Intel I226-V 2.5GbE driver `igc` | 221 | E0026 |
| M00043 | Asymmetric VLAN — 10GbE = data plane / 2.5GbE = management plane | 221 | E0026 |
| M00044 | Lane-sharing topology trap — populating M.2_2 forces Slot 1 x8 and Slot 2 x4 | 245–252 | E0027 |

## Features (F00171–F00255) — 85 features

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F00171 | Hardware probe — CPUID 9900X family detection | 215 | M00029 | capability | false |
| F00172 | Hardware probe — AVX-512 subset detection (F/BW/DQ/VL/VNNI/VPOPCNTDQ/BITALG/VBMI/VBMI2/BF16/IFMA/VP2INTERSECT/GFNI) | 215 | M00029 | capability | false |
| F00173 | Profile knob — `cpu_target_arch = znver5 \| znver4 \| x86-64-v4 \| native` | 215 | M00030 | profile | true |
| F00174 | Env var `SOVEREIGN_CPU_TARGET_ARCH` | 215 | M00030 | env_var | true |
| F00175 | CLI `sovereign-osctl hardware cpu posture` | 215 | M00029 | cli_verb | true |
| F00176 | Dashboard surface — CPU posture card (model / family / AVX-512 subsets / single-cycle 512-bit verified) | 215 | M00029 | dashboard | true |
| F00177 | API `GET /v1/hardware/cpu` — JSON capability dump | 215 | M00029 | api_endpoint | true |
| F00178 | Metric `sovereign_os_hardware_cpu_avx512_subsets` (info gauge with per-subset labels) | 215 | M00029 | observability_metric | true |
| F00179 | Test — CPUID probe stable across daemon restarts | 215 | M00029 | test | true |
| F00180 | Lifecycle hook — pre-AVX-512-kernel verify family + subset flags match | 215 | M00029 | lifecycle_hook | true |
| F00181 | Personalization — operator overrides `cpu_target_arch` per kernel | 215 | M00030 | configuration | true |
| F00182 | Hardware probe — PCIe slot map enumeration | 216 | M00031 | capability | false |
| F00183 | Hardware probe — IOMMU group enumeration | 216 | M00032 | capability | false |
| F00184 | Profile knob — `pcie_dual_gpu_symmetry_required` | 216 | M00031 | profile | true |
| F00185 | Env var `SOVEREIGN_PCIE_DUAL_GPU_SYMMETRY_REQUIRED` | 216 | M00031 | env_var | true |
| F00186 | CLI `sovereign-osctl hardware pcie list` | 216 | M00031 | cli_verb | true |
| F00187 | CLI `sovereign-osctl hardware iommu groups` | 216 | M00032 | cli_verb | true |
| F00188 | Dashboard surface — PCIe slot map with bandwidth utilization | 216 | M00031 | dashboard | true |
| F00189 | Dashboard surface — IOMMU group inspector | 216 | M00032 | dashboard | true |
| F00190 | API `GET /v1/hardware/pcie` | 216 | M00031 | api_endpoint | true |
| F00191 | API `GET /v1/hardware/iommu` | 216 | M00032 | api_endpoint | true |
| F00192 | Metric `sovereign_os_hardware_pcie_slot_width{slot}` | 216 | M00031 | observability_metric | true |
| F00193 | Metric `sovereign_os_hardware_iommu_group_count` | 216 | M00032 | observability_metric | true |
| F00194 | Test — friction-audit verifies x8/x8 GPU lane symmetry | 216 | M00031 | test | true |
| F00195 | Test — friction-audit verifies Blackwell + 3090 in distinct IOMMU groups | 216 | M00032 | test | true |
| F00196 | Lifecycle hook — first-boot abort if M.2_2 populated AND dual-GPU symmetry required | 245–252 | M00044 | lifecycle_hook | true |
| F00197 | Composite — friction-audit composite (PCIe + IOMMU + slot map) | 216 | composite: [M00031, M00032, M00044] | capability | true |
| F00198 | Blackwell oracle resident-model warm-keep | 217 | M00033 | mode | true |
| F00199 | Profile knob — `blackwell_resident_model_warm` | 217 | M00033 | profile | true |
| F00200 | Env var `SOVEREIGN_BLACKWELL_RESIDENT_MODEL_WARM` | 217 | M00033 | env_var | true |
| F00201 | CLI `sovereign-osctl hardware gpu blackwell status` | 217 | M00033 | cli_verb | true |
| F00202 | Dashboard surface — Blackwell oracle card (VRAM used / model resident / KV size / temp / power) | 217 | M00033 | dashboard | true |
| F00203 | API `GET /v1/hardware/gpu/blackwell` | 217 | M00033 | api_endpoint | true |
| F00204 | Metric `sovereign_os_gpu_blackwell_vram_used_bytes` | 267 | M00034 | observability_metric | true |
| F00205 | Metric `sovereign_os_gpu_blackwell_temperature_celsius` | 267 | M00034 | observability_metric | true |
| F00206 | Metric `sovereign_os_gpu_blackwell_power_watts` | 267 | M00034 | observability_metric | true |
| F00207 | Test — Blackwell driver loaded + nvidia-smi reports 96 GB | 267 | M00034 | test | true |
| F00208 | Test — Blackwell MIG profile selectable | 267 | M00034 | test | true |
| F00209 | Test — Blackwell FP4 Tensor Cores accessible via TensorRT | 267 | M00034 | test | true |
| F00210 | Lifecycle hook — Blackwell pre-load model warm-up | 217 | M00033 | lifecycle_hook | true |
| F00211 | Lifecycle hook — Blackwell post-evict model cool-down | 217 | M00033 | lifecycle_hook | true |
| F00212 | 3090 VFIO isolation mode | 218 | M00035 | mode | true |
| F00213 | Profile knob — `gpu_3090_vfio_enabled` | 218 | M00035 | profile | true |
| F00214 | Env var `SOVEREIGN_GPU_3090_VFIO_ENABLED` | 218 | M00035 | env_var | true |
| F00215 | CLI `sovereign-osctl hardware gpu 3090 status` | 218 | M00035 | cli_verb | true |
| F00216 | Dashboard surface — 3090 scout card (VRAM / draft tokens/sec / VFIO state / temp / power) | 218 | M00035 | dashboard | true |
| F00217 | API `GET /v1/hardware/gpu/3090` | 218 | M00035 | api_endpoint | true |
| F00218 | Metric `sovereign_os_gpu_3090_vram_used_bytes` | 218 | M00036 | observability_metric | true |
| F00219 | Metric `sovereign_os_gpu_3090_vfio_active` (0/1) | 218 | M00035 | observability_metric | true |
| F00220 | Test — 3090 bind to vfio-pci at boot | 218 | M00035 | test | true |
| F00221 | Test — 3090 unbind from vfio-pci for host use | 218 | M00035 | test | true |
| F00222 | Lifecycle hook — 3090 pre-VFIO-bind release host nvidia driver | 218 | M00035 | lifecycle_hook | true |
| F00223 | Lifecycle hook — 3090 post-VFIO-unbind reload host nvidia driver | 218 | M00035 | lifecycle_hook | true |
| F00224 | Memory capacity discovery — total RAM / per-DIMM size / channels | 219 | M00037 | capability | false |
| F00225 | Profile knob — `ram_capacity_target_gib = 128 \| 256` | 219 | M00037 | profile | true |
| F00226 | Env var `SOVEREIGN_RAM_CAPACITY_TARGET_GIB` | 219 | M00037 | env_var | true |
| F00227 | CLI `sovereign-osctl hardware memory list` | 219 | M00037 | cli_verb | true |
| F00228 | Dashboard surface — RAM utilization + per-channel layout | 219 | M00037 | dashboard | true |
| F00229 | Metric `sovereign_os_hardware_ram_total_bytes` | 219 | M00037 | observability_metric | true |
| F00230 | Metric `sovereign_os_hardware_ram_channels_used` | 331 | M00038 | observability_metric | true |
| F00231 | Test — 4-DIMM channel population verified | 331 | M00038 | test | true |
| F00232 | NVMe sequential bandwidth measurement | 220 | M00039 | capability | true |
| F00233 | Profile knob — `nvme_zfs_raid_mode = stripe \| mirror` | 220 | M00040 | profile | true |
| F00234 | Env var `SOVEREIGN_NVME_ZFS_RAID_MODE` | 220 | M00040 | env_var | true |
| F00235 | CLI `sovereign-osctl hardware nvme bench` | 220 | M00039 | cli_verb | true |
| F00236 | Dashboard surface — NVMe throughput per device | 220 | M00039 | dashboard | true |
| F00237 | API `GET /v1/hardware/nvme` | 220 | M00039 | api_endpoint | true |
| F00238 | Metric `sovereign_os_nvme_sequential_read_gibps{device}` | 220 | M00039 | observability_metric | true |
| F00239 | Metric `sovereign_os_nvme_sequential_write_gibps{device}` | 220 | M00039 | observability_metric | true |
| F00240 | Test — NVMe sequential ≥ 13 GiB/s per device on Gen 5 x4 slot | 220 | M00039 | test | true |
| F00241 | Test — ZFS pool reports RAID-0 stripe mode | 343–344 | M00040 | test | true |
| F00242 | Lifecycle hook — NVMe thermal alert on > 75°C sustained | 220 | M00039 | lifecycle_hook | true |
| F00243 | Asymmetric VLAN — 10GbE on VLAN 200 (data) | 221 | M00043 | mode | true |
| F00244 | Asymmetric VLAN — 2.5GbE on VLAN 100 (management) | 221 | M00043 | mode | true |
| F00245 | Profile knob — `network_vlan_topology = symmetric \| asymmetric` | 221 | M00043 | profile | true |
| F00246 | Env var `SOVEREIGN_NETWORK_VLAN_TOPOLOGY` | 221 | M00043 | env_var | true |
| F00247 | CLI `sovereign-osctl hardware network status` | 221 | M00041 | cli_verb | true |
| F00248 | Dashboard surface — NIC card (10GbE up/down / VLAN / MTU 9000 / 2.5GbE up/down / VLAN) | 221 | M00041 | dashboard | true |
| F00249 | API `GET /v1/hardware/network` | 221 | M00041 | api_endpoint | true |
| F00250 | Metric `sovereign_os_network_link_speed_mbps{interface}` | 221 | M00041 | observability_metric | true |
| F00251 | Metric `sovereign_os_network_vlan_id{interface}` | 221 | M00043 | observability_metric | true |
| F00252 | Test — 10GbE iperf3 ≥ 9 Gbps | 221 | M00041 | test | true |
| F00253 | Test — Marvell AQC113C ASPM stable across suspend/resume | 221 | M00041 | test | true |
| F00254 | Lifecycle hook — first-boot detect Marvell AQC113C / Intel I226-V firmware versions | 221 | M00041 | lifecycle_hook | true |
| F00255 | Composite — power envelope auditor (CPU + 2× GPU + board) ≤ PSU rating | 348–355 | composite: [M00033, M00035, M00029] | capability | true |

## Requirements (R00341–R00510) — 170 requirements

| R ID | Phrase | Dump line | Parent F | Class | Opt-in | Sub-req min |
|---|---|---|---|---|---|---|
| R00341 | CPUID detection identifies 9900X by family/model/stepping | 215 | F00171 | non-negotiable | false | 10 |
| R00342 | CPUID detection confirms Zen 5 microarchitecture flag | 215 | F00171 | non-negotiable | false | 10 |
| R00343 | AVX-512 F subset detected via CPUID leaf 7 EBX bit 16 | 215 | F00172 | non-negotiable | false | 10 |
| R00344 | AVX-512 BW subset detected via CPUID leaf 7 EBX bit 30 | 215 | F00172 | non-negotiable | false | 10 |
| R00345 | AVX-512 DQ subset detected via CPUID leaf 7 EBX bit 17 | 215 | F00172 | non-negotiable | false | 10 |
| R00346 | AVX-512 VL subset detected via CPUID leaf 7 EBX bit 31 | 215 | F00172 | non-negotiable | false | 10 |
| R00347 | AVX-512 VNNI detected via CPUID leaf 7 ECX bit 11 | 215 | F00172 | non-negotiable | false | 10 |
| R00348 | AVX-512 VPOPCNTDQ detected via CPUID leaf 7 ECX bit 14 | 215 | F00172 | non-negotiable | false | 10 |
| R00349 | AVX-512 BITALG detected via CPUID leaf 7 ECX bit 12 | 215 | F00172 | non-negotiable | false | 10 |
| R00350 | AVX-512 VBMI detected via CPUID leaf 7 ECX bit 1 | 215 | F00172 | non-negotiable | false | 10 |
| R00351 | AVX-512 VBMI2 detected via CPUID leaf 7 ECX bit 6 | 215 | F00172 | non-negotiable | false | 10 |
| R00352 | AVX-512 BF16 detected via CPUID leaf 7 EAX bit 5 | 215 | F00172 | non-negotiable | false | 10 |
| R00353 | AVX-512 IFMA detected via CPUID leaf 7 EBX bit 21 | 215 | F00172 | non-negotiable | false | 10 |
| R00354 | AVX-512 VP2INTERSECT detected via CPUID leaf 7 EDX bit 8 | 215 | F00172 | non-negotiable | false | 10 |
| R00355 | AVX-512 GFNI detected via CPUID leaf 7 ECX bit 8 | 215 | F00172 | non-negotiable | false | 10 |
| R00356 | Profile `cpu_target_arch` accepts `znver5` / `znver4` / `x86-64-v4` / `native` | 215 | F00173 | non-negotiable | true | 10 |
| R00357 | Env var `SOVEREIGN_CPU_TARGET_ARCH` accepts same enum | 215 | F00174 | non-negotiable | true | 10 |
| R00358 | CLI `sovereign-osctl hardware cpu posture` returns JSON when `--json` set | 215 | F00175 | non-negotiable | true | 10 |
| R00359 | Dashboard CPU posture card refreshes on daemon SIGHUP | 215 | F00176 | non-negotiable | true | 10 |
| R00360 | API `GET /v1/hardware/cpu` returns JSON capabilities matching `/var/lib/sovereign-os/hardware-capabilities.json` | 215 | F00177 | non-negotiable | false | 10 |
| R00361 | Metric `sovereign_os_hardware_cpu_avx512_subsets` exports one info gauge per subset | 215 | F00178 | non-negotiable | false | 10 |
| R00362 | Test — CPUID probe stable across daemon restarts and reboots | 215 | F00179 | non-negotiable | false | 10 |
| R00363 | Lifecycle hook `pre-AVX-512-kernel` aborts on missing subset | 215 | F00180 | non-negotiable | false | 10 |
| R00364 | Operator overrides `cpu_target_arch` per kernel via kernel manifest YAML | 215 | F00181 | non-negotiable | true | 10 |
| R00365 | Zen 5 single-cycle full-width 512-bit datapath confirmed by benchmark | 215 | M00030 | non-negotiable | false | 10 |
| R00366 | Zen 5 vs Zen 4 datapath difference exposed as info gauge | 215 | M00030 | non-negotiable | false | 10 |
| R00367 | ProArt X870E-Creator slot map enumerated via lspci | 216 | F00182 | non-negotiable | false | 10 |
| R00368 | PCIEX16_1 slot identified by domain:bus:device:function | 216 | M00031 | non-negotiable | false | 10 |
| R00369 | PCIEX16_2 slot identified by domain:bus:device:function | 216 | M00031 | non-negotiable | false | 10 |
| R00370 | M.2_1 slot identified | 216 | M00031 | non-negotiable | false | 10 |
| R00371 | M.2_2 slot identified | 216 | M00031 | non-negotiable | false | 10 |
| R00372 | M.2_3 slot identified | 216 | M00031 | non-negotiable | false | 10 |
| R00373 | M.2_4 slot identified | 216 | M00031 | non-negotiable | false | 10 |
| R00374 | IOMMU group enumeration via `/sys/kernel/iommu_groups/` | 216 | F00183 | non-negotiable | false | 10 |
| R00375 | Profile `pcie_dual_gpu_symmetry_required` accepts boolean | 216 | F00184 | non-negotiable | true | 10 |
| R00376 | Env var `SOVEREIGN_PCIE_DUAL_GPU_SYMMETRY_REQUIRED` accepts boolean | 216 | F00185 | non-negotiable | true | 10 |
| R00377 | CLI `sovereign-osctl hardware pcie list` returns slot map with electrical/physical widths | 216 | F00186 | non-negotiable | true | 10 |
| R00378 | CLI `sovereign-osctl hardware iommu groups` returns group → devices mapping | 216 | F00187 | non-negotiable | true | 10 |
| R00379 | Dashboard PCIe slot map shades bandwidth utilization 0–100% | 216 | F00188 | non-negotiable | true | 10 |
| R00380 | Dashboard IOMMU inspector highlights devices needing isolation | 216 | F00189 | non-negotiable | true | 10 |
| R00381 | API `/v1/hardware/pcie` returns JSON slot map | 216 | F00190 | non-negotiable | true | 10 |
| R00382 | API `/v1/hardware/iommu` returns JSON group map | 216 | F00191 | non-negotiable | true | 10 |
| R00383 | Metric `sovereign_os_hardware_pcie_slot_width` labeled by slot name | 216 | F00192 | non-negotiable | false | 10 |
| R00384 | Metric `sovereign_os_hardware_iommu_group_count` is gauge | 216 | F00193 | non-negotiable | false | 10 |
| R00385 | friction-audit verifies PCIEX16_1 = x8 electrical / PCIEX16_2 = x8 electrical | 216 | F00194 | non-negotiable | false | 10 |
| R00386 | friction-audit verifies Blackwell IOMMU group ≠ 3090 IOMMU group | 216 | F00195 | non-negotiable | false | 10 |
| R00387 | Lifecycle hook first-boot aborts if M.2_2 populated AND `dual_gpu_symmetry_required = true` | 245–252 | F00196 | non-negotiable | true | 10 |
| R00388 | Composite friction-audit requires modules M00031 + M00032 + M00044 | 216 | F00197 | non-negotiable | false | 10 |
| R00389 | Blackwell warm-keep mode opt-in via profile | 217 | F00198 | non-negotiable | true | 10 |
| R00390 | Profile `blackwell_resident_model_warm` accepts boolean | 217 | F00199 | non-negotiable | true | 10 |
| R00391 | Env var `SOVEREIGN_BLACKWELL_RESIDENT_MODEL_WARM` accepts boolean | 217 | F00200 | non-negotiable | true | 10 |
| R00392 | CLI `sovereign-osctl hardware gpu blackwell status` returns JSON | 217 | F00201 | non-negotiable | true | 10 |
| R00393 | Dashboard Blackwell card shows VRAM used / model resident name / KV size / temp / power | 217 | F00202 | non-negotiable | true | 10 |
| R00394 | API `/v1/hardware/gpu/blackwell` returns JSON | 217 | F00203 | non-negotiable | true | 10 |
| R00395 | Metric `sovereign_os_gpu_blackwell_vram_used_bytes` is Prometheus gauge | 267 | F00204 | non-negotiable | false | 10 |
| R00396 | Metric `sovereign_os_gpu_blackwell_temperature_celsius` is Prometheus gauge | 267 | F00205 | non-negotiable | false | 10 |
| R00397 | Metric `sovereign_os_gpu_blackwell_power_watts` is Prometheus gauge | 267 | F00206 | non-negotiable | false | 10 |
| R00398 | Test — Blackwell driver loaded ≥ 590.48.01 | 267 | F00207 | non-negotiable | true | 10 |
| R00399 | Test — nvidia-smi reports 96 GB VRAM on Blackwell | 267 | F00207 | non-negotiable | false | 10 |
| R00400 | Test — Blackwell MIG instance count ≤ 4 selectable | 267 | F00208 | non-negotiable | true | 10 |
| R00401 | Test — Blackwell FP4 Tensor Core inference via TensorRT-LLM | 267 | F00209 | non-negotiable | true | 10 |
| R00402 | Lifecycle hook Blackwell pre-load runs `vllm cache warm` | 217 | F00210 | non-negotiable | true | 10 |
| R00403 | Lifecycle hook Blackwell post-evict frees VRAM and emits OTel span | 217 | F00211 | non-negotiable | true | 10 |
| R00404 | 3090 VFIO isolation opt-in via profile | 218 | F00212 | non-negotiable | true | 10 |
| R00405 | Profile `gpu_3090_vfio_enabled` accepts boolean | 218 | F00213 | non-negotiable | true | 10 |
| R00406 | Env var `SOVEREIGN_GPU_3090_VFIO_ENABLED` accepts boolean | 218 | F00214 | non-negotiable | true | 10 |
| R00407 | CLI `sovereign-osctl hardware gpu 3090 status` returns JSON | 218 | F00215 | non-negotiable | true | 10 |
| R00408 | Dashboard 3090 card shows VRAM / draft tokens/sec / VFIO state / temp / power | 218 | F00216 | non-negotiable | true | 10 |
| R00409 | API `/v1/hardware/gpu/3090` returns JSON | 218 | F00217 | non-negotiable | true | 10 |
| R00410 | Metric `sovereign_os_gpu_3090_vram_used_bytes` is Prometheus gauge | 218 | F00218 | non-negotiable | false | 10 |
| R00411 | Metric `sovereign_os_gpu_3090_vfio_active` is Prometheus gauge 0/1 | 218 | F00219 | non-negotiable | false | 10 |
| R00412 | Test — 3090 binds to vfio-pci at boot when `GRUB_CMDLINE_LINUX` includes `vfio-pci.ids=10de:2204,10de:1ad8` | 218 | F00220 | non-negotiable | true | 10 |
| R00413 | Test — 3090 unbind/rebind works without reboot | 218 | F00221 | non-negotiable | true | 10 |
| R00414 | Lifecycle hook 3090 pre-VFIO-bind releases host nvidia driver via `echo` to `unbind` sysfs | 218 | F00222 | non-negotiable | true | 10 |
| R00415 | Lifecycle hook 3090 post-VFIO-unbind reloads host nvidia driver | 218 | F00223 | non-negotiable | true | 10 |
| R00416 | RAM discovery via dmidecode | 219 | F00224 | non-negotiable | false | 10 |
| R00417 | Profile `ram_capacity_target_gib` accepts 128 / 256 | 219 | F00225 | non-negotiable | true | 10 |
| R00418 | Env var `SOVEREIGN_RAM_CAPACITY_TARGET_GIB` accepts 128 / 256 | 219 | F00226 | non-negotiable | true | 10 |
| R00419 | CLI `sovereign-osctl hardware memory list` returns per-DIMM table | 219 | F00227 | non-negotiable | true | 10 |
| R00420 | Dashboard RAM card shows total / used / free / per-channel layout | 219 | F00228 | non-negotiable | true | 10 |
| R00421 | Metric `sovereign_os_hardware_ram_total_bytes` is Prometheus gauge | 219 | F00229 | non-negotiable | false | 10 |
| R00422 | Metric `sovereign_os_hardware_ram_channels_used` is Prometheus gauge 1/2/4 | 331 | F00230 | non-negotiable | false | 10 |
| R00423 | Test — friction-audit verifies 4 DIMMs populated when target = 256 GB | 331 | F00231 | non-negotiable | true | 10 |
| R00424 | NVMe sequential bandwidth measured via fio | 220 | F00232 | non-negotiable | false | 10 |
| R00425 | Profile `nvme_zfs_raid_mode` accepts `stripe` (RAID-0) / `mirror` (RAID-1) | 220 | F00233 | non-negotiable | true | 10 |
| R00426 | Env var `SOVEREIGN_NVME_ZFS_RAID_MODE` accepts same enum | 220 | F00234 | non-negotiable | true | 10 |
| R00427 | CLI `sovereign-osctl hardware nvme bench` runs fio sequential read+write | 220 | F00235 | non-negotiable | true | 10 |
| R00428 | Dashboard NVMe card shows per-device throughput live | 220 | F00236 | non-negotiable | true | 10 |
| R00429 | API `/v1/hardware/nvme` returns JSON | 220 | F00237 | non-negotiable | true | 10 |
| R00430 | Metric `sovereign_os_nvme_sequential_read_gibps` labeled by device | 220 | F00238 | non-negotiable | false | 10 |
| R00431 | Metric `sovereign_os_nvme_sequential_write_gibps` labeled by device | 220 | F00239 | non-negotiable | false | 10 |
| R00432 | Test — NVMe sequential ≥ 13 GiB/s per device on Gen 5 x4 | 220 | F00240 | non-negotiable | true | 10 |
| R00433 | Test — ZFS pool layout = stripe when `nvme_zfs_raid_mode = stripe` | 343 | F00241 | non-negotiable | false | 10 |
| R00434 | Lifecycle hook NVMe thermal alert at sustained > 75°C | 220 | F00242 | non-negotiable | true | 10 |
| R00435 | ZFS RAID-0 layout only for scratch / cache / datasets / artifacts (not durability) | 344 | M00040 | non-negotiable | false | 10 |
| R00436 | Asymmetric VLAN 10GbE on VLAN 200 with MTU 9000 | 221 | F00243 | non-negotiable | true | 10 |
| R00437 | Asymmetric VLAN 2.5GbE on VLAN 100 with MTU 1500 | 221 | F00244 | non-negotiable | true | 10 |
| R00438 | Profile `network_vlan_topology` accepts `symmetric` / `asymmetric` | 221 | F00245 | non-negotiable | true | 10 |
| R00439 | Env var `SOVEREIGN_NETWORK_VLAN_TOPOLOGY` accepts same enum | 221 | F00246 | non-negotiable | true | 10 |
| R00440 | CLI `sovereign-osctl hardware network status` returns JSON | 221 | F00247 | non-negotiable | true | 10 |
| R00441 | Dashboard NIC card shows 10GbE link / VLAN / MTU / 2.5GbE link / VLAN | 221 | F00248 | non-negotiable | true | 10 |
| R00442 | API `/v1/hardware/network` returns JSON | 221 | F00249 | non-negotiable | true | 10 |
| R00443 | Metric `sovereign_os_network_link_speed_mbps` labeled by interface | 221 | F00250 | non-negotiable | false | 10 |
| R00444 | Metric `sovereign_os_network_vlan_id` labeled by interface | 221 | F00251 | non-negotiable | false | 10 |
| R00445 | Test — 10GbE iperf3 sustained ≥ 9 Gbps | 221 | F00252 | non-negotiable | false | 10 |
| R00446 | Test — Marvell AQC113C ASPM stable across 100 suspend/resume cycles | 221 | F00253 | preferable | false | 10 |
| R00447 | Lifecycle hook first-boot logs Marvell + Intel firmware versions | 221 | F00254 | non-negotiable | false | 10 |
| R00448 | Composite power envelope auditor (600+350+120+150 ≤ PSU rating) | 348–355 | F00255 | non-negotiable | false | 10 |
| R00449 | Composite power envelope requires modules M00033 + M00035 + M00029 | 348–355 | F00255 | non-negotiable | false | 10 |
| R00450 | PSU minimum rating = 1600W | 355 | E0030 | non-negotiable | true | 10 |
| R00451 | PSU recommended rating = 2000W | 355 | E0030 | preferable | true | 10 |
| R00452 | Blackwell power budget = 600W under load | 350 | E0029 | non-negotiable | false | 10 |
| R00453 | 3090 power budget = 350W under load | 351 | E0029 | non-negotiable | false | 10 |
| R00454 | 9900X power budget = 120W TDP (higher under PBO) | 352 | E0029 | non-negotiable | false | 10 |
| R00455 | Board + NVMe + fans budget = 80–150W | 353 | E0029 | non-negotiable | false | 10 |
| R00456 | CUDA bare-metal PCIe P2P unsupported with IOMMU on Linux — design implication | 597 | E0031 | non-negotiable | false | 10 |
| R00457 | 3090 VFIO design — treat as separate machine behind RPC boundary | 597 | E0031 | non-negotiable | false | 10 |
| R00458 | Cross-GPU transport — compact symbols only (tokens/scores/ids/summaries/intents/patch summaries) | 526–536 | E0031 | non-negotiable | false | 10 |
| R00459 | Cross-GPU transport — avoid KV tensors / activations / layer-split / constant sync | 540–547 | E0031 | non-negotiable | false | 10 |
| R00460 | Blackwell first PCIe 5.0 slot at x8 electrical width | 259 | E0028 | non-negotiable | false | 10 |
| R00461 | 3090 second PCIe slot at x8 electrical via Gen 5 chassis path | 260 | E0028 | non-negotiable | false | 10 |
| R00462 | NVMe hot tier at M.2_1 PCIe 5.0 x4 | 261 | E0028 | non-negotiable | false | 10 |
| R00463 | NVMe bulk at M.2_3 / M.2_4 PCIe 4.0 x4 via chipset | 262 | E0028 | non-negotiable | false | 10 |
| R00464 | Friction-audit pass criterion — x8/x8 GPU + IOMMU groups distinct + cppc preferred-CCD identified + MOK key generated | 216 | F00197 | non-negotiable | false | 10 |
| R00465 | Friction-audit must run at first-boot via systemd one-shot unit | 216 | F00197 | non-negotiable | false | 10 |
| R00466 | Friction-audit must produce JSON report at `/var/lib/sovereign-os/friction-audit.json` | 216 | F00197 | non-negotiable | true | 10 |
| R00467 | Friction-audit must emit OTel spans for each verified invariant | 216 | F00197 | non-negotiable | false | 10 |
| R00468 | Friction-audit failure must block subsequent SAIN-01-only modules from loading | 216 | F00197 | non-negotiable | false | 10 |
| R00469 | Friction-audit must support `--allow-degraded` to operate on non-SAIN-01 hardware | 216 | F00197 | non-negotiable | true | 10 |
| R00470 | Hardware capabilities JSON schema versioned (selfdef SDD-017 contract) | 215 | F00177 | non-negotiable | false | 10 |
| R00471 | Hardware capabilities JSON schema mirrored to selfdef cross-repo binding crate `selfdef-hardware-manifest` | 215 | F00177 | non-negotiable | false | 10 |
| R00472 | Hardware capabilities JSON file path `/var/lib/sovereign-os/hardware-capabilities.json` | 215 | F00177 | non-negotiable | false | 10 |
| R00473 | Hardware capabilities JSON file written atomically (tempfile + rename) | 215 | F00177 | non-negotiable | false | 10 |
| R00474 | Hardware capabilities JSON file mode 0644 | 215 | F00177 | non-negotiable | false | 10 |
| R00475 | Hardware capabilities JSON file owner `sovereign-os:sovereign-os` | 215 | F00177 | non-negotiable | false | 10 |
| R00476 | Hardware probe runs at daemon SIGHUP | 215 | M00029 | non-negotiable | false | 10 |
| R00477 | Hardware probe runs at daemon startup | 215 | M00029 | non-negotiable | false | 10 |
| R00478 | Hardware probe never sleeps in main thread | 215 | M00029 | non-negotiable | false | 10 |
| R00479 | Hardware probe completes in < 500ms | 215 | M00029 | preferable | false | 10 |
| R00480 | Profile `production` requires friction-audit pass at startup | 216 | F00197 | non-negotiable | true | 10 |
| R00481 | Profile `experimental` allows friction-audit failures with warning | 216 | F00197 | non-negotiable | true | 10 |
| R00482 | Profile `headless` skips dashboard surfaces but keeps CLI + API + metrics | 216 | F00188 | non-negotiable | true | 10 |
| R00483 | Profile `developer` enables hardware probe debug logging | 215 | M00029 | non-negotiable | true | 10 |
| R00484 | Profile `private` disables /v1/hardware/* API exposure to non-localhost | 215 | F00177 | non-negotiable | true | 10 |
| R00485 | Profile `offline` disables hardware-driver firmware update checks | 221 | F00254 | non-negotiable | true | 10 |
| R00486 | Mode `friction-audit dry-run` reports without aborting | 216 | F00197 | non-negotiable | true | 10 |
| R00487 | Mode `friction-audit strict` aborts on any failure | 216 | F00197 | non-negotiable | true | 10 |
| R00488 | Personalization — operator-defined friction-audit invariant YAML | 216 | F00197 | non-negotiable | true | 10 |
| R00489 | Personalization — operator-defined per-GPU power budget override | 348–355 | F00255 | non-negotiable | true | 10 |
| R00490 | Personalization — operator-defined per-NVMe thermal threshold | 220 | F00242 | non-negotiable | true | 10 |
| R00491 | Personalization — operator-defined VLAN ID per interface | 221 | F00243 | non-negotiable | true | 10 |
| R00492 | Personalization — operator-defined MTU per interface | 221 | F00243 | non-negotiable | true | 10 |
| R00493 | Personalization — operator-defined NIC LACP bonding (future) | 221 | F00243 | preferable | true | 10 |
| R00494 | Personalization — operator-defined RAM channel preference (single/dual/quad) | 219 | F00224 | non-negotiable | true | 10 |
| R00495 | Personalization — operator-defined PCIe slot priority order | 216 | F00186 | non-negotiable | true | 10 |
| R00496 | Personalization — operator-defined IOMMU group remapping (advanced) | 216 | F00187 | preferable | true | 10 |
| R00497 | Personalization — operator-defined Blackwell warm-keep model list | 217 | F00198 | non-negotiable | true | 10 |
| R00498 | Personalization — operator-defined 3090 VFIO bind-id list | 218 | F00212 | non-negotiable | true | 10 |
| R00499 | Personalization — operator-defined CPU core pinning for hardware probe | 215 | M00029 | preferable | true | 10 |
| R00500 | Composite — hardware-watch composite alerts on any subsystem degradation | 213–565 | composite: [M00029, M00031, M00033, M00035, M00039, M00041] | capability | true |
| R00501 | Composite — hardware-watch emits one OTel span per subsystem per minute | 213–565 | composite: [M00029, M00031, M00033, M00035, M00039, M00041] | non-negotiable | false | 10 |
| R00502 | Composite — hardware-watch supports operator-defined thresholds per subsystem | 213–565 | composite: [M00029, M00031, M00033, M00035, M00039, M00041] | non-negotiable | true | 10 |
| R00503 | Composite — hardware-watch routes alerts via selfdef integration channels (ntfy/signal/smtp/twilio/slack/discord/wall/write/pagerduty/loki/opensearch/thehive) | 213–565 | composite: [M00029, M00031, M00033, M00035, M00039, M00041] | non-negotiable | true | 10 |
| R00504 | Composite — hardware-watch persists alert history to ZFS audit trail | 213–565 | composite: [M00029, M00031, M00033, M00035, M00039, M00041] | non-negotiable | false | 10 |
| R00505 | Hardware-tune script `selfdef-tune.sh` ingests JSON capabilities + emits compile flags | 215 | F00177 | non-negotiable | false | 10 |
| R00506 | Hardware-tune script supports `--format sh/env-file/make/json` | 215 | F00177 | non-negotiable | true | 10 |
| R00507 | Hardware-tune script writes atomically | 215 | F00177 | non-negotiable | false | 10 |
| R00508 | Hardware-tune script integrated into kernel rebuild Makefile | 215 | F00177 | non-negotiable | true | 10 |
| R00509 | Hardware-tune script integrated into Wasm-AOT toolchain | 215 | F00177 | non-negotiable | true | 10 |
| R00510 | Hardware-tune script integrated into bitnet.cpp build | 215 | F00177 | non-negotiable | true | 10 |

— End of M003 milestone file.
