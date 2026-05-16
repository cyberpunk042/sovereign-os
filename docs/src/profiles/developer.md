# Profile: developer — polyglot dev workstation

> Developer workstation with full polyglot toolchain. Not SAIN-01-class
> (no Tetragon perimeter, no VFIO, no Blackwell), but more substantive
> than minimal (real GPU, dev tooling, GUI-capable base).
>
> Profile YAML: [`profiles/developer.yaml`](../../../profiles/developer.yaml).

---

## Hardware target

| Component | Expected |
|---|---|
| CPU | generic x86-64-v3 (laptop or desktop) |
| GPU | single NVIDIA card (operator's existing 3090 / 4090 / similar) |
| RAM | 16 GB minimum, 32 GB+ recommended for AI dev work |
| Storage | single NVMe with ext4 |
| Secure boot | `shim` (operator-supplied MOK) |
| Network | LAN sufficient |

---

## What's profile-specific

| Aspect | developer | Differs from sain-01 |
|---|---|---|
| Toolchain | gcc/clang/rust/go/python/node + gdb/lldb/strace/valgrind + cmake/meson/ninja + podman/buildah/skopeo + vim/neovim/emacs-nox | sain-01 is workstation-class but NOT polyglot dev |
| Mixins | role-developer + whitelabel-default + observability-tier-1 | role-workstation for sain-01 |
| Kernel | substrate-default | custom for sain-01 |
| ZFS | none — ext4 | zfs-tiered for sain-01 |
| VFIO | none | binds 3090 for sain-01 |
| Tetragon | not active | active for sain-01 |
| First-login assistant | interactive (operator picks setup) | sain-01 has it as opt-in too |
| Hardening | NONE (role-developer mixin, deliberate — devs need flexibility) | sain-01 has role-workstation hardening |

---

## Build

```sh
# Dry-run
SOVEREIGN_OS_PROFILE=developer scripts/build/orchestrate.sh run --dry-run

# Real build — substrate-default kernel; ~5-10 min
SOVEREIGN_OS_PROFILE=developer \
SOVEREIGN_OS_MOK_KEY=/path/MOK.priv \
SOVEREIGN_OS_MOK_CERT=/path/MOK.der \
  sudo scripts/build/orchestrate.sh run
```

---

## Install + boot

```sh
sovereign-osctl install image --plan build/developer/output/developer.raw --to /dev/nvme0n1
SOVEREIGN_OS_CONFIRM_DESTROY=YES \
  sudo sovereign-osctl install image build/developer/output/developer.raw --to /dev/nvme0n1
```

First boot: shim MOK enrollment on first launch (UEFI MOK Manager prompts
once → enroll operator MOK → continue boot). After enrollment, regular
boots are signed-chain-validated transparently.

---

## Daily use

```sh
sovereign-osctl profiles switch developer
sovereign-osctl status
sovereign-osctl doctor                       # profile-conditioned (won't check zfs/tetragon)
sovereign-osctl audit customization
sovereign-osctl maintenance security-check   # pending security updates check
```

---

## What this profile is FOR

1. The operator's day-to-day dev box — they write code on it, run model
   experiments on a single GPU.
2. Pre-SAIN-01 dev environment — operator iterating on sovereign-os
   itself + selfdef + info-hub from their existing dev workstation.
3. A reference for what "no perimeter, no Tetragon" looks like —
   sain-01 is the locked-down workstation; developer is the workshop.

## What this profile is NOT FOR

- Production AI inference (use sain-01)
- Server workloads (use headless)
- Hardened deployment (use sain-01 or headless — devs need to break things; perimeter would impede)

---

## Customization

| Want to… | How |
|---|---|
| Add a language's toolchain | edit `profiles/mixins/role-developer.yaml § packages.role.developer` |
| Enable Tetragon | `sovereign-osctl hooks add post_install_first_boot scripts/hooks/post-install/tetragon-policy-load.sh --profile developer` |
| Switch to ZFS | edit `profiles/developer.yaml § hardware.storage.layout` to zfs-tiered |
| Use the GUI | role-developer doesn't include a DE; install one manually (apt install gnome-core or similar) — or fork the profile |
