# Profile: minimal — VM baseline

> Server-class headless install with NO GUI, NO AI stack, NO custom kernel.
> Purpose: pre-hardware QEMU validation · substrate-adapter validation ·
> CI-friendly smoke target · embedded box.
>
> Profile YAML: [`profiles/minimal.yaml`](../../../profiles/minimal.yaml).

---

## Hardware target

| Component | Expected |
|---|---|
| CPU | generic x86-64-v3 (e.g. typical 4-8 core VM CPU) |
| GPU | none (or virtio-gpu in a VM) |
| RAM | 4 GB minimum, 8 GB recommended |
| Storage | virtio-blk root + ext4 (no ZFS) |
| Network | virtio-net |
| Secure boot | `signed` (useful for VM-testing the signing chain without real hardware) |

The minimal profile validates the schema + pipeline against a third
hardware shape that's NOT sain-01 and NOT old-workstation. It boots in
QEMU in seconds.

---

## What's profile-specific

| Aspect | minimal | Differs from sain-01 |
|---|---|---|
| Kernel | substrate-default (Debian linux-image-amd64) | custom kernel skipped (R30 Q18-A short-circuit) |
| Storage | ext4 single rootfs | no ZFS |
| Networking | systemd-networkd via cloud-init | no VLAN |
| First-login assistant | NOT registered (boots quiet → operator drives via cloud-init/preseed) | sain-01 has it as opt-in |
| GUI | none | none in sain-01 either |
| Mixins | role-headless + whitelabel-default | sain-01 has role-workstation + observability-tier-1 |
| Inference router | none active | sain-01 has all 4 tiers |
| Hardening | none (operator-driven) | sain-01 has role-workstation |

---

## Build

```sh
# Dry-run
SOVEREIGN_OS_PROFILE=minimal scripts/build/orchestrate.sh run --dry-run

# Real build — fast (no kernel compile)
SOVEREIGN_OS_PROFILE=minimal scripts/build/orchestrate.sh run

# Verify provenance
sovereign-osctl audit provenance --deep build/minimal/output/build-provenance.json
```

Expected duration: ~5 minutes (no custom kernel).

---

## Install + boot in QEMU

```sh
# QEMU is the natural target for minimal — see scripts/build/09-image-verify.sh
# which uses qemu-system-x86_64 for the boot smoke test.

SOVEREIGN_OS_PROFILE=minimal \
SOVEREIGN_OS_IMAGE_DIR=build/minimal/output \
  scripts/build/09-image-verify.sh

# Or run the L3 scaffold
tests/qemu/scaffold.sh minimal
```

Without KVM: set `SOVEREIGN_OS_LAYER4_SLOW=1` for the slow-path boot
probe (5-15min instead of fast-with-KVM).

---

## Daily use (when deployed)

```sh
sovereign-osctl profiles switch minimal
sovereign-osctl status                       # minimal surface — no Tetragon, no GPU
sovereign-osctl doctor                       # profile-conditioned (won't check zfs/nvidia/tetragon)
sovereign-osctl audit customization          # confirm minimal customization landed
```

---

## What this profile is FOR

1. **Pre-hardware QEMU validation** — operator without SAIN-01 hardware can iterate on the pipeline + adapter contracts without provisioning anything.
2. **Substrate-adapter validation** — both mkosi + live-build adapters are exercised against the same minimal hardware shape.
3. **CI smoke** — `test_e2e_dry_run_smoke.sh` and `test_reproducibility_self_test.sh` run against minimal.
4. **Embedded boxes / VMs** — when the operator needs a sovereign-os baseline without the AI workstation surface.

## What this profile is NOT FOR

- AI workloads (no GPU)
- Production server workloads (use `headless` — has auditd + fail2ban + chrony + unattended-upgrades)
- Real hardware sovereignty (pick sain-01 or fork it)

---

## Customization

| Want to… | How |
|---|---|
| Try a bigger VM shape | edit `profiles/minimal.yaml § hardware.memory.target_gb` and `hardware.cpu.cores` |
| Enable encryption | set `SOVEREIGN_OS_ENCRYPT=1` at build time (LUKS2 per SDD-022) |
| Add a service | `sovereign-osctl hooks add post_install_first_boot scripts/hooks/my-hook.sh --profile minimal` |
| Fork to a substantive VM profile | `sovereign-osctl profiles fork minimal my-vm` |
