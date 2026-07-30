# scripts/iac — day-2 convergence

Make this machine match its profile. Re-runnable, idempotent, no manual commands.

```bash
sudo ./converge.sh --dry-run     # show what would change, touch nothing
sudo ./converge.sh               # apply
sudo ./converge.sh               # run again — must report "0 changed"
sudo ./converge.sh --only 30     # one module
sudo ./converge.sh --list        # modules + which gates are on
```

## The model

**The profile is the spec.** `/opt/sovereign-os/profiles/<id>.yaml` already declares
everything under `provisioning.*` — the operator account, the bake list, the model,
open-computer, the UPS. Converge reads that same file the runtime hooks read, so the
two can never disagree about intent. There is no second config language.

`converge.conf` holds only what the profile *cannot* express:

1. **Machine truth** — where physical hardware contradicts the profile. Documented
   deviations, not preferences.
2. **Gates** — which heavy/networked modules run by default.

Modules only enforce. Each mutation goes through an `ensure_*` helper in `lib/iac.sh`
that checks first, applies second, and records `ok` / `changed` / `skip` / `fail`.

## Why this exists

Package upgrades silently revert package-owned files. `dpkg --verify sovereign-os-cockpit`
already reports `??5?????? /opt/sovereign-os/profiles/sain-01.yaml` — it is **not** a
dpkg conffile, so `apt upgrade` will overwrite it and take the GPU power cap with it.
Converge is the loop that puts it back. Run it after every upgrade.

## Rules

- **Never edit a shipped unit file.** Use `ensure_dropin` → `/etc/systemd/system/<unit>.d/`,
  which dpkg does not own.
- **Never destroy.** Modules refuse rather than clobber (see `15-source-repo.sh` declining
  to clone over a non-empty directory).
- **Refuse impossible state.** `30-gpu-power.sh` will not request a wattage below the
  card's `power.min_limit`; asking for 350W on a 400W-floor card is what made the boot
  hook fail every boot.
- **Report blockers, don't work around them.** `70-local-model.sh` stops when `/mnt/vault`
  is not a mount rather than quietly writing 60GB to `/`.
- **Absent ≠ failed.** A unit or group that does not exist on this host is `skip`, not `fail`.

## Modules

| | | |
|---|---|---|
| `10-operator-user` | on | Creates the `operator` account three shipped units need. Nothing in the sovereign-os tree creates it — `open-computer-install.sh` only does `usermod -aG kvm` and `chown`, both assuming it exists. Without it those units die at `217/USER`. |
| `15-source-repo` | on | Clones `cyberpunk042/sovereign-os` to the operator's home. **`/opt/sovereign-os` is a dpkg payload subset — not a checkout** (no `crates/`, `docs/`, `Makefile`, `Cargo.toml`), and the module refuses to make it one. Also unblocks building `sovereign-gatewayd` + `guardian-core`, which live in `crates/`. |
| `20-systemd-state` | on | Desired enable/disable/mask per unit, plus the gatewayd start-limit drop-in. |
| `30-gpu-power` | on | Per-GPU caps by PCI id, honouring the hardware floor. Re-asserts the profile value the boot hook reads, and keeps `gpu-policy.toml`'s alert threshold aligned. |
| `40-boot-kernel` | on | Pins the GRUB default to the newest **packaged** kernel. Verifies vmlinuz/initrd/DKMS first and refuses to pin a kernel that cannot boot. |
| `50-ups-power` | on | Configures NUT for the network UPS the profile declares. |
| `60-open-computer` | **off** | Provisions the QEMU sandbox. ~3GB download. |
| `70-local-model` | **off** | Fetches the profile's model. Tens of GB. |
| `80-binaries` | on | Installs the executables the `.deb` did not carry. `guardian-core` is a Python script — free, done by default. The Rust trio (`sovereign-gatewayd`, `sovereign-telemetry`, `sovereign-resource-control`) needs rustup 1.89.0 and a long build, so it is behind `IAC_ENABLE_RUST_BINS`. |

## Known blockers this codifies

These are recorded as `fail`/`skip` with reasons rather than silently worked around:

- **No ZFS pool.** `sovereign-zfs-scrub.timer` and `sovereign-backup-snapshot.timer` are
  held disabled. Both NVMe devices are vfat/ext4/swap; `tank/context` was never created.
  Re-enable in `20-systemd-state.sh` once it exists.
- **`/mnt/vault` does not exist**, so the 30B model has nowhere to land. Almost certainly
  the same missing pool.
- **`sovereign-gatewayd`, `sovereign-telemetry` and `guardian-core` were absent**, not broken.
  `sovereign-os-cockpit` is `Architecture: all` and carried neither `make guardian`'s script
  nor `make bins`' Rust output. Module 80 installs them. Module 20 does not hard-code those
  units' state — it **derives** it from whether the binary exists, so building them promotes
  the units automatically on the next run. Upstream hit this same class of bug and documented
  it in the Makefile: *"the fleet install must carry the binary the unit points at, or the
  unit ships as an orphan"* (fixed for guardian-core 2026-07-17; our package predates it).
- **Tetragon is not installed**, so its verify timer is held disabled.

## A correction worth knowing

`50-ups-power.sh` exists partly to *undo* an earlier mistake. Triage saw `nut-server`
and `nut-monitor` failing, ran `lsusb | grep -i ups`, found nothing, and masked both as
"no hardware". Wrong: `provisioning.power` declares an `apc-modbus` UPS at
`192.168.1.69` — a **network** UPS that never appears on USB, and the host pings. They
failed because `/etc/nut/*` was entirely unconfigured (`MODE` unset), not because the
UPS was missing. Check the profile before concluding hardware is absent.
