# First-boot orchestration

Wires the 9 post-install hook scripts as systemd `oneshot` services + a target. Reaching `sovereign-firstboot.target` means every first-boot hook has run successfully.

## Units

| Unit | Hook | Trigger condition | Order |
|---|---|---|---|
| `sovereign-firstboot.target` | (group target) | — | — |
| `sovereign-friction-audit.service` | `post-install/friction-audit-runtime.sh` | `ConditionFirstBoot=yes` | 1 |
| `sovereign-vfio-bind.service` | `post-install/vfio-bind-4090.sh` | `ConditionFirstBoot=yes` | 2 (after friction) |
| `sovereign-network-vlan.service` | `post-install/network-vlan-config.sh` | `ConditionFirstBoot=yes` | 2 (after friction) |
| `sovereign-tetragon-policy-load.service` | `post-install/tetragon-policy-load.sh` | `ConditionFirstBoot=yes` | 3 (after Tetragon daemon + ZFS) |
| `sovereign-zfs-arc-clamp.service` | `post-install/zfs-arc-clamp.sh` | `ConditionFirstBoot=yes` | 2 (after ZFS) |
| `sovereign-nvidia-driver-bind.service` | `post-install/nvidia-driver-bind.sh` | `ConditionFirstBoot=yes` | 2 (after friction) |
| `sovereign-warp-setup.service` | `post-install/warp-setup.sh` | `ConditionFirstBoot=yes` | 3 (after nvidia-driver-bind; pip-installs `warp-lang`, R558/SDD-070) |
| `sovereign-workstation-shell-setup.service` | `post-install/workstation-shell-setup.sh` | `ConditionFirstBoot=yes` | 2 |
| `sovereign-firstboot.service` | (marker + reboot notice) | After all above complete | last |

The first-login assistant (`first-login-assistant.sh`) is **NOT** part of this target — it runs only at actual first user login via a user-level mechanism (operator's choice: pam_exec, ~/.profile, or sovereign-osctl assistant on demand).

## ConditionFirstBoot semantics

systemd considers a boot to be "first boot" when `/etc/machine-id` is empty or absent at startup. After the first boot, the file is populated and these services won't run again. To force-rerun (e.g., for testing): `sudo rm /etc/machine-id && sudo systemd-machine-id-setup && sudo systemctl reset-failed && reboot`.

For idempotent re-run on demand without rebooting: each hook script is itself idempotent — call directly via `sovereign-osctl audit friction` / etc.

## Install

```sh
sudo cp systemd/system/sovereign-firstboot*.{service,target} /etc/systemd/system/
sudo cp systemd/system/sovereign-{friction-audit,vfio-bind,network-vlan,tetragon-policy-load,zfs-arc-clamp,nvidia-driver-bind,warp-setup,workstation-shell-setup}.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sovereign-firstboot.target

# Profile env file (read by services via EnvironmentFile=-)
sudo install -d /etc/sovereign-os
sudo tee /etc/sovereign-os/active-profile.env <<'EOF'
SOVEREIGN_OS_PROFILE=sain-01
EOF
```

## VFIO reboot notice

`sovereign-vfio-bind.service` writes `/var/lib/sovereign-os/.vfio-bind-needs-reboot`. The completion service (`sovereign-firstboot.service`) prints a reboot notice to `/dev/console` if that flag is present. After reboot, `vfio-pci` claims the device from the initramfs and the flag is cleared by hand (`sudo rm /var/lib/sovereign-os/.vfio-bind-needs-reboot`).

## Verifying first-boot completion

```sh
systemctl status sovereign-firstboot.target
cat /var/lib/sovereign-os/first-boot-complete    # ISO 8601 timestamp
journalctl -u sovereign-friction-audit.service   # per-hook logs
```

## Override per profile

The `old-workstation` profile doesn't need VFIO + Tetragon + ARC clamp. To skip those services for a non-SAIN-01 profile:

```sh
# Either mask the services explicitly:
sudo systemctl mask sovereign-vfio-bind.service \
  sovereign-tetragon-policy-load.service \
  sovereign-zfs-arc-clamp.service

# Or set the profile env:
echo "SOVEREIGN_OS_PROFILE=old-workstation" | sudo tee /etc/sovereign-os/active-profile.env
# (each hook script checks the profile and exits 0 early when not applicable)
```

The hooks already short-circuit when the profile doesn't declare the relevant feature (e.g., `zfs-arc-clamp.sh` checks `hardware.storage.layout` and exits early on `ext4`).
