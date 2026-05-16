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

## Build (exact commands)

```sh
# 1. Dry-run (always first)
SOVEREIGN_OS_PROFILE=sain-01 scripts/build/orchestrate.sh run --dry-run

# 2. Generate operator-owned secure-boot keys (one-time, signed posture)
sovereign-osctl secure-boot gen-keys --out ~/.sovereign-os/secure-boot-keys

# 3. Real build (~30-45 min including custom kernel compile)
SOURCE_DATE_EPOCH=$(date +%s) \
DEBIAN_SNAPSHOT=20260515T000000Z \
SOVEREIGN_OS_PROFILE=sain-01 \
SOVEREIGN_OS_DB_KEY=~/.sovereign-os/secure-boot-keys/db.key \
SOVEREIGN_OS_DB_CERT=~/.sovereign-os/secure-boot-keys/db.crt \
SOVEREIGN_OS_PK_KEY=~/.sovereign-os/secure-boot-keys/PK.key \
SOVEREIGN_OS_PK_CERT=~/.sovereign-os/secure-boot-keys/PK.crt \
  sudo scripts/build/orchestrate.sh run

# 4. Verify provenance triangle (manifest ↔ sums.txt ↔ on-disk)
sovereign-osctl audit provenance --deep build/sain-01/output/build-provenance.json
```

## Install + boot

```sh
sovereign-osctl install image --plan build/sain-01/output/sain-01.raw --to /dev/nvme1n1
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
  sudo sovereign-osctl install image build/sain-01/output/sain-01.raw --to /dev/nvme1n1
```

First-boot hook order:
1. `friction-audit-runtime` — confirms x8/x8 PCIe + AVX-512 + ZFS health
2. `vfio-bind-3090` — binds 3090 to vfio-pci
3. `network-vlan-config` — applies asymmetric VLAN (R158 lands master-spec defaults)
4. `tetragon-policy-load` — loads sovereign-kernel-fence
5. `arc-clamp-128gb` — clamps ZFS ARC at 128 GB
6. `apply-workstation-hardening` — 4 IaC drop-ins (auditd · pwquality · unattended · sshd)
7. `first-login-assistant` — interactive operator flow

## Activation + daily use

```sh
sovereign-osctl profiles switch sain-01
sovereign-osctl status                       # health overview
sovereign-osctl doctor                       # sanity check
sovereign-osctl perimeter status             # Tetragon integrity
sovereign-osctl inference status             # per-tier table
sovereign-osctl audit drift                  # hardening drift check
sovereign-osctl audit customization          # did all my customization land?
sovereign-osctl maintenance scrub            # ZFS scrub
sovereign-osctl maintenance arc-status       # ZFS ARC stats
```

## What to do if it fails

| Failure | Recovery |
|---|---|
| Build fails mid-step | `scripts/build/orchestrate.sh recover` (4 ranked options) |
| friction-audit FAIL at boot (PCIe x8) | Power down · check M.2_2 is empty · check BIOS bifurcation |
| VFIO bind FAIL | Check kernel cmdline has `vfio-pci.ids=10de:2204,10de:1ad8` · `dmesg \| grep -i iommu` |
| Tetragon not active | `systemctl status tetragon` · `sovereign-osctl perimeter reload` |
| Hardening drop-in mismatch | `sovereign-osctl audit drift` to see which; re-apply with the post-install hook |

## What's NOT yet built specific to sain-01 (master-spec materialization arc)

| Master spec | Round | Status |
|---|---|---|
| Trinity surfaced as `trinity` verb | R149 | not started |
| 3 runtime profiles selectable (Ultra-Sovereign · High-Concurrency · Deep Context) | R150 | not started |
| CCD-pinned start scripts | R151 | not started |
| Real bitnet.cpp build from source | R152 | not started |
| Wasm-to-AVX-512 AOT pipeline | R153 | not started |
| Atomic state transition protocol | R154 | not started |
| Guardian Daemon | R155 | not started |
| Real model catalog (Qwen-32B · DeepSeek-V3/R1 · Ling-2.6 · Nemotron-3-Nano) | R156 | not started |
| DFlash speculative decoding | R157 | not started |
| Asymmetric networking opinionated to master-spec values | R158 | not started |
| `bootstrap verify` (master spec § 22 checklist) | R159 | not started |

## Customization

| Want to… | How |
|---|---|
| Change kernel options | edit `profiles/sain-01.yaml § kernel.config.enable / disable` |
| Fork to match your specific hardware | `sovereign-osctl profiles fork sain-01 my-sain` |
| Author your whitelabel | edit `whitelabel/<id>.yaml` (SDD-007 7-strategy taxonomy) |
| Add a post-install hook | `sovereign-osctl hooks add post_install_first_boot scripts/hooks/my-hook.sh --profile sain-01` |
| Override hardening per host | drop a `99operator.*` file in `/etc/*/*.d/` (lexicographically wins) |

