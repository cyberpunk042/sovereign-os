# SDD-701 — NVIDIA GPU bring-up: install the pinned ≥570 driver + apply the power caps at boot (F-2026-109..110)

> Status: draft
> Owner: operator-directed 2026-07-14 (build-and-flash readiness review — GPU bring-up; driver channel chosen: CUDA-repo-pinned `.run` ≥570); agent-authored.
> Closes: **F-2026-109** (HIGH), **F-2026-110** (MED).
> Mandate module: **E11.M701**.
> Number band: **700–799 (phase-1 audit continuation — build-and-flash readiness)** per SDD-100.

## The directive

Batch 3 of the build-and-flash readiness pass. After SDD-998/999 made the box
*boot* its hooks correctly, and SDD-700 locked the sudoers, the next gap is the
GPUs themselves: a flashed SAIN-01 would come up with **no usable NVIDIA driver**
and, once one exists, **no power caps** — the two things that make the Blackwell
cards actually run within budget. Driver channel chosen by the operator:
**CUDA-repo-pinned `.run` ≥570** (not distro backports).

## F-2026-109 (HIGH) — the flashed image has no ≥570 Blackwell driver; the GPUs stay dark

The profile bakes `nvidia-open-kernel-dkms` + `nvidia-driver`, but trixie ships
**550.163**, which predates the Blackwell **GB202** (RTX PRO 6000 Max-Q + RTX
5090) — the profile itself notes *"the primary GPU needs a ≥570 driver at first
boot"*. Nothing installed it: `nvidia-driver-bind.sh` only blacklists nouveau +
rebuilds the initramfs; there was no hook that actually brings a ≥570 driver onto
the box. So the flashed workstation boots with `nvidia-smi` failing and both
Blackwell cards unusable — the AI node has no GPUs.

**Fix — a first-boot driver-install hook** (`nvidia-driver-install.sh`), gated
`ConditionFirstBoot=yes` + `ConditionVirtualization=no`, ordered **before** the
nouveau bind:

1. **Idempotent** — if a running driver already reports major ≥570, no-op.
2. **Pinned open-kernel `.run`** — version + URL from a new `provisioning.nvidia`
   profile block (`driver_runfile_version` / `runfile_url_base` /
   `kernel_module_type: open` — Blackwell requires the *open* modules). Downloads
   from NVIDIA's server, **fails loudly** on a 404 or an implausibly-small file
   (an error page, not a driver), and **refuses a pin below the 570 floor**.
3. **Supersedes the distro 550** — purges the conflicting `nvidia-driver*` /
   `nvidia-kernel*` / `nvidia-open-kernel-dkms` packages the `.run` can't coexist
   with, then installs `--silent --dkms --kernel-module-type=open`.
4. **Secure boot** — the box already enrolls a per-machine MOK
   (`mok-enroll.sh` → `/var/lib/sovereign-os/mok`). When it's present the `.run`
   signs the built modules with it (`--module-signing-secret-key/-public-key`),
   and we write `/etc/dkms/nvidia.conf` (`mok_signing_key`/`mok_certificate`) so a
   later kernel-update DKMS rebuild **re-signs** — otherwise the kernel refuses
   the unsigned `nvidia`/`nvidia_drm`/`nvidia_modeset`/`nvidia_uvm` modules and the
   GPUs go dark on the next kernel bump. If secure boot is on but no MOK exists it
   warns loudly rather than shipping unsigned-and-silently-broken.
5. **Serialized initramfs** (SDD-998 `boot_regen`) + a reboot marker the
   completion service surfaces on the console (a fresh driver binds on reboot).

## F-2026-110 (MED) — the profile power caps were declared but never applied

Each GPU declares `tdp_watts` (PRO 6000 Max-Q **300W**, 5090 **350W** — the 5090
power-limited down from its **575W** stock TGP), and the profile comments even
name `nvidia-smi -pl 350` — but nothing ran it. So a flashed box would run the
5090 at its full 575W stock TGP: ~225W over the profile's intent, on a 1600W PSU
shared with the PRO 6000 + a 9900X — a real power/thermal-budget and
efficiency-knee miss.

**Fix — an every-boot power-limit hook** (`nvidia-power-limit.sh`) + unit. It
enables persistence mode and applies each card's `tdp_watts` via `nvidia-smi -pl`,
matching each physical card to its cap by **PCI device-id** (profile `pci_id`
`10de:2bb4` → the `nvidia-smi` GPU whose `pci.device_id` contains `2bb4`) so
enumeration order never mis-assigns a cap. It runs **every boot** (enabled at
`multi-user.target`, *not* a first-boot member) because `nvidia-smi -pl` does not
persist across reboots; `role: vfio` GPUs are skipped (they belong to the isolated
sandbox). Idempotent (`-pl` is reapply-safe) and VM-skipped.

## The lint

`tests/lint/test_nvidia_gpu_bringup_contract.py` (8 cases) pins the load-bearing
properties: the driver hook MOK-signs + persists the DKMS re-sign + enforces the
570 floor + serializes initramfs; the power hook applies per-card `-pl` matched by
device-id; the install unit is a first-boot member ordered before the bind; the
power unit runs every boot (no `ConditionFirstBoot`); the profile pins a ≥570
open-module driver. The existing per-unit systemd coverage/hardening + firstboot
membership + install-coverage lints already cover the two new units generically.

## Verification (real, observed)

- `bash -n` on both hooks + `provision-bake.sh` clean; the inline power-limit
  Python parses (`ast.parse`).
- `pytest tests/lint/test_nvidia_gpu_bringup_contract.py` → **8 passed**;
  `pytest -k "firstboot or systemd or hardening or unit or shell or install_coverage or posture"`
  → **1042 passed** (the driver-install unit's hardening waiver + `RestrictNamespaces`,
  the firstboot membership floor, and the README fleet-count bump all green).
- `ruff` clean. Full `tests/lint` green (see PR).
- **Not** verified: the actual driver install / GPU bind / power draw — that needs
  the physical SAIN-01 (no Blackwell GPU or NVIDIA driver in CI). Consistent with
  how every other first-boot hardware hook is validated (static contract + lints;
  behavior on the real machine). The pinned `driver_runfile_version` must be
  confirmed against NVIDIA's server at build (the hook fails loudly if it 404s).

## Scope / safety

New: `nvidia-driver-install.sh` + `nvidia-power-limit.sh` hooks,
`sovereign-nvidia-driver-install.service` (first-boot) +
`sovereign-nvidia-power-limit.service` (every-boot) units, the contract lint, the
`provisioning.nvidia` profile block. Wired: firstboot target `Wants=` + membership
lint floor + `firstboot.service` `After=`/console-notice, `provision-bake.sh`
FB_UNITS + power-limit enable, systemd README fleet count. No Rust crate, no
gatewayd/cockpit/webapp change; no new dependency. Both hooks idempotent +
VM-skipped; the driver unit carries the full R171 baseline minus the
`ProtectKernelModules` it must omit (it builds/loads modules — waived with reason).
MS003 `unsigned-pending-MS003`.

## Non-goals

- vLLM + the inference model (Batch 4 — its own SDD; the operator asked me to
  research the model rather than pick blindly).
- Multi-GPU tensor-parallel / MPS tuning (`sovereign-nvidia-mps.service` exists).
- Pinning the exact latest ≥570 patch (operator-confirmed at build; the hook
  refuses <570 and fails loudly on a bad URL).
- The RTX 4090 eGPU (OcuLink, `role: egpu` host-resident) driver — same driver
  covers it once installed; its power cap applies via the same device-id match if
  a `tdp_watts` is set.

## Cross-references

- `scripts/hooks/post-install/nvidia-driver-install.sh` — pinned ≥570 `.run` + MOK signing
- `scripts/hooks/post-install/nvidia-power-limit.sh` — per-card `-pl` by device-id, every boot
- `scripts/hooks/during-install/mok-enroll.sh` — the MOK this signs with
- `docs/sdd/998-firstboot-orchestration-correctness.md` — the target membership + `boot_regen` this builds on
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-109, F-2026-110 (closed here)
