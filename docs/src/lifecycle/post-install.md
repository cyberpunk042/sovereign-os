# Post-install lifecycle stage (first boot + assistant)

What runs **after the system boots into the installed userspace** — once.

## Profile hooks (`hooks.post_install_first_boot`)

For `sain-01`:

| Hook | Purpose |
|---|---|
| `friction-audit-runtime.sh` | Verify actual lspci / lscpu / IOMMU groups match profile; GPU-BDF-scoped PCIe lane check (corrects L0 dump's wide-scope bug per SDD-006) |
| `vfio-bind-4090.sh` | Configure GRUB cmdline `vfio-pci.ids=10de:2684,10de:22ba`; write `/etc/modprobe.d/vfio.conf`; rebuild initramfs |
| `network-vlan-config.sh` | Emit systemd-networkd .network + .netdev units for VLAN 100 (mgmt) + 200 (data MTU 9000) |
| `tetragon-policy-load.sh` | Install `sovereign-kernel-fence.yaml` TracingPolicy; enable + restart tetragon |
| `zfs-arc-clamp.sh` | Clamp `zfs_arc_max` to 128 GB; write `/etc/modprobe.d/zfs.conf`; rebuild initramfs |
| `nvidia-driver-bind.sh` | Blacklist nouveau; verify `nvidia-smi` |
| `workstation-shell-setup.sh` | Bash-completion + `/etc/skel/.bash_aliases` + `.inputrc` |
| **`first-login-assistant.sh`** | **Operator-stated requirement (Q-018)**: auto-launch-capable; interactive TUI; idempotent; state at `/var/lib/sovereign-os/assistant/state.yaml` |

## First-login assistant (Q-018)

Operator-verbatim: *"post install script ready to be pre-added or even automatically launch on first login and such. based on what is chosen by the user."*

Current implementation: CLI prompts for hostname, NVIDIA enable, model catalog pre-pull, Tetragon verify, whitelabel sanity check. Runs once; re-runnable via `sudo sovereign-osctl assistant`.

Stage-2 next round: TUI elaboration via `whiptail` / `textual` (Q-018-D); pre-add path via cloud-init / preseed (Q-018-D).

## Activation order

```
1. friction-audit-runtime (validate)
2. vfio-bind-4090           ── reboot required after
3. (REBOOT)
4. network-vlan-config
5. tetragon-policy-load
6. zfs-arc-clamp             ── rebuild initramfs
7. nvidia-driver-bind
8. workstation-shell-setup
9. first-login-assistant
```

Wired as systemd `oneshot` services + `Wants=` ordering at Stage 2+ next round. For now: manual invocation. <!-- anti-min-waiver: R480 systemd-oneshot-wiring-anchored-to-Stage-2-next-round-per-SDD-013-installer-experience -->
