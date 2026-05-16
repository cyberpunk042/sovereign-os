# Default profile — `sain-01`

The SAIN-01 AI Workstation. See [`profiles/sain-01.yaml`](https://github.com/cyberpunk042/sovereign-os/blob/main/profiles/sain-01.yaml) for the full declaration.

## Hardware target

| Component | Spec |
|---|---|
| **CPU** | AMD Ryzen 9 9900X — Zen 5; 12C/24T dual-CCD; `-march=znver5` with single-cycle 512-bit AVX-512 + VNNI |
| **Primary GPU** | NVIDIA RTX PRO 6000 Blackwell 96 GB — host-resident; hosts the Oracle Core |
| **VFIO GPU** | NVIDIA RTX 3090 24 GB — `vfio-pci` bound; isolated for Logic Engine sandbox |
| **Memory** | 256 GB DDR5 (128 GB minimum); ECC unavailable on consumer DDR5 |
| **Storage** | Dual PCIe 5.0 NVMe in RAID 0 (operator-accepted no-redundancy trade-off) |
| **Network** | Intel I226-V 2.5 GbE (mgmt VLAN 100) + Marvell AQC113C 10 GbE (data VLAN 200, MTU 9000) |
| **Motherboard** | ASUS ProArt X870E-Creator; PCIe constraint: **M.2_2 must remain empty** |

## CCD partition (SRP Trinity mapping)

```
CCD 0  (cores 0-5, mask 0xfff)        → Pulse — bitnet.cpp ternary inference
CCD 1  (cores 6-9, mask 0xff000)      → Weaver + Auditor — state fabric + Tetragon
CCD 1  (cores 10-11, mask 0xf00000)   → Host / kernel / IRQ
```

## ZFS dataset stratification

| Dataset | Recordsize | Compression | Sync | Purpose |
|---|---|---|---|---|
| `tank/models` | 1M | lz4 | standard | 100GB+ weight files; sequential reads |
| `tank/context` | 16k | zstd-9 (copies=2) | **always** | State-fabric race-free atomic transitions |
| `tank/agents` | 128k | zstd-3 | standard | Runtime cache + sub-agent scratch |

## Inference stack (per SDD-011)

| Tier | Backend | Hardware |
|---|---|---|
| **Pulse** | bitnet.cpp | CCD 0 (CPU) |
| **Logic Engine** | vLLM (primary) + llama.cpp (fallback) | RTX 3090 (VFIO sandbox via podman) |
| **Oracle Core** | vLLM + DFlash drafts | RTX PRO 6000 Blackwell (host-resident) |
| **Router** | OpenAI-compatible front | 127.0.0.1:8080 |

## Default model picks

| Tier | Model | Source |
|---|---|---|
| Pulse | `microsoft/bitnet-b1.58-2B-4T` | Microsoft canonical ternary |
| Logic Engine | operator-chosen quantized model (Qwen3-coder default) | apt/HF |
| Oracle Core | `nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16` (default) or `inclusionAI/Ling-2.6-flash` | See [Ling vs Nemotron comparison](https://github.com/cyberpunk042/devops-solutions-information-hub/blob/main/wiki/comparisons/cmp-ling-26-flash-vs-nemotron-3-nano-omni.md) |

## Activation

```sh
sovereign-osctl profiles switch sain-01
sovereign-osctl profiles show-effective sain-01   # see mixin-resolved profile
sovereign-osctl inference status                  # per-tier table
sovereign-osctl audit friction                    # runtime friction-audit
```
