# Alternate profile — `old-workstation`

Constrained-hardware target: the operator's existing workstation. ~11 GB RAM + 8 GB GPU class. See [`profiles/old-workstation.yaml`](https://github.com/cyberpunk042/sovereign-os/blob/main/profiles/old-workstation.yaml).

## Hardware target (placeholder pending operator-supplied specifics)

| Component | Spec |
|---|---|
| **CPU** | x86_64; `-march=x86-64-v3` baseline (operator pins real `march` when machine known) |
| **GPU** | NVIDIA 8 GB (model TBD) |
| **Memory** | 11 GB target; 8 GB minimum; DDR4 |
| **Storage** | Single SATA SSD; ext4 |
| **Network** | 1 GbE LAN |

## What's different from `sain-01`

| Concern | sain-01 | old-workstation |
|---|---|---|
| Storage layout | zfs-tiered (3 datasets) | ext4 single device |
| Kernel | custom `-march=znver5` | substrate-default (stock Debian) |
| Secure boot | signed (operator MOK) | shim (Microsoft chain) |
| Inference Pulse | bitnet.cpp on CCD 0 | not applicable (no AVX-512) |
| Inference Logic | vLLM on VFIO 4090 | llama.cpp on 8 GB GPU |
| Inference Oracle | vLLM + DFlash on Blackwell | not applicable |
| Tetragon perimeter | required | optional |

## Why it exists

1. **Schema-pluralism check** — validates the profile schema works for non-SAIN-01 hardware.
2. **SLM/RLM target** — operator-named in goal directive: "Small Language Models (SLMs) and Recursive Language Models (RLMs)".
3. **Existing workstation reuse** — runs sovereign-os without requiring SAIN-01 hardware.

## Build

```sh
# Dry-run first (always)
SOVEREIGN_OS_PROFILE=old-workstation scripts/build/orchestrate.sh run --dry-run

# Real build — substrate-default kernel (no custom compile; ~5 min)
SOVEREIGN_OS_PROFILE=old-workstation \
  sudo scripts/build/orchestrate.sh run

# For shim posture (default for this profile)
SOVEREIGN_OS_PROFILE=old-workstation \
SOVEREIGN_OS_MOK_KEY=/path/to/MOK.priv \
SOVEREIGN_OS_MOK_CERT=/path/to/MOK.der \
  sudo scripts/build/orchestrate.sh run

# Verify provenance
sovereign-osctl audit provenance --deep build/old-workstation/output/build-provenance.json
```

## Install + boot

```sh
sovereign-osctl install image --plan build/old-workstation/output/old-workstation.raw --to /dev/sda
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
  sudo sovereign-osctl install image build/old-workstation/output/old-workstation.raw --to /dev/sda
```

First-boot: shim MOK enrollment prompt → enroll the operator MOK once →
boots into sovereign-os with hardening applied (4 workstation drop-ins).

## Daily use

```sh
sovereign-osctl profiles switch old-workstation
sovereign-osctl status
sovereign-osctl inference status      # only router + logic-engine (llama.cpp) active
sovereign-osctl audit drift           # hardening drift check
```

Only `sovereign-router.service` + `sovereign-logic-engine.service` (with
`SOVEREIGN_OS_LOGIC_BACKEND=llama_cpp`) are activated. No Pulse, no Oracle
Core, no DFlash. The 24GB context-window ceiling of the 8GB GPU drives this.

## What's NOT yet built specific to old-workstation

Most of the gap list is sain-01-specific (Pulse · CCD pinning · Wasm AOT ·
Guardian). What lands for ALL profiles affects this one too: R148
per-profile docs (this), R156 model catalog (the llama.cpp tier's model
becomes a first-class choice), R158 networking opinionated defaults.

## Customization

| Want to… | How |
|---|---|
| Use a stronger card | fork to `old-workstation-12gb` etc. + bump GPU spec; vRAM ceilings cascade through inference router config |
| Try ZFS instead of ext4 | edit `profiles/old-workstation.yaml § hardware.storage.layout` from ext4 to zfs-tiered; orchestrator's during-install hooks adapt |
| Enable Tetragon | `sovereign-osctl hooks add post_install_first_boot scripts/hooks/post-install/tetragon-policy-load.sh --profile old-workstation` |
