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
| Inference Logic | vLLM on VFIO 3090 | llama.cpp on 8 GB GPU |
| Inference Oracle | vLLM + DFlash on Blackwell | not applicable |
| Tetragon perimeter | required | optional |

## Why it exists

1. **Schema-pluralism check** — validates the profile schema works for non-SAIN-01 hardware.
2. **SLM/RLM target** — operator-named in goal directive: "Small Language Models (SLMs) and Recursive Language Models (RLMs)".
3. **Existing workstation reuse** — runs sovereign-os without requiring SAIN-01 hardware.

## Activation

```sh
sovereign-osctl profiles switch old-workstation
sovereign-osctl profiles show-effective old-workstation
sovereign-osctl inference status
```

Only `sovereign-router.service` + `sovereign-logic-engine.service` (with `SOVEREIGN_OS_LOGIC_BACKEND=llama_cpp`) are activated. No Pulse, no Oracle Core, no DFlash.
