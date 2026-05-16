# Install runbook (SAIN-01 default profile)

End-to-end runbook for building + installing sovereign-os on the
SAIN-01 hardware. Covers pre/during/post-install with operator
checkpoints. Substrate-aware: uses mkosi (primary per SDD-003); the
live-build path swaps the `05/07` build steps but the lifecycle is
identical.

## Prerequisites

| Item | How to confirm |
|---|---|
| SAIN-01 hardware assembled | `friction-audit` script (pre-install spec mode) PASS |
| Debian 13 (Trixie) build host | `cat /etc/debian_version` shows 13.x |
| ≥ 80 GB free RAM for tmpfs forge | `free -g` shows ≥ 80 in `available` |
| mkosi installed (or live-build) | `mkosi --version` ≥ 23.0 |
| podman installed | `podman --version` ≥ 4.x |
| `python3-yaml`, `python3-jsonschema` | `python3 -c 'import yaml, jsonschema'` |

If any are missing, `scripts/build/01-bootstrap-forge.sh` installs the
build toolchain (kernel-compilation deps); the rest is operator-supplied.

## 1. PRE-INSTALL — build the image

### 1.1 Profile spec validation

```sh
SOVEREIGN_OS_PROFILE=sain-01 \
  scripts/hooks/pre-install/friction-audit-spec.sh
```

Confirms profile YAML is internally consistent (CPU features, GPU
roles, ZFS sync=always on tank/context, M.2_2 blocker for sain-01, etc.).
Exit 0 = ready to build.

### 1.2 Run the build pipeline

```sh
# All knobs env-overridable; restart-from-state across crashes
SOVEREIGN_OS_PROFILE=sain-01 \
SOVEREIGN_OS_SUBSTRATE=mkosi \
  sudo scripts/build/orchestrate.sh run
```

Executes 9 steps:

| Step | What | Time (sain-01) |
|---|---|---|
| 01-bootstrap-forge | apt deps + tmpfs (64 GB) at /mnt/kernel_forge | 5 min |
| 02-kernel-fetch | clone linux-stable v6.12 shallow | 2 min |
| 03-kernel-config | seed + apply znver5 enable/disable + olddefconfig | 1 min |
| 04-kernel-compile | `make -j24 bindeb-pkg` with znver5 KCFLAGS | 30-45 min |
| 05-substrate-prepare | mkosi.conf + skeleton + extra + repart emitted | < 1 min |
| 06-whitelabel-render | render templates + overlays into skeleton/extra | < 1 min |
| 07-image-build | `mkosi build` (apt + sealing) | 10-20 min |
| 08-image-sign | sbsign vmlinuz + EFI binaries with MOK | 1 min |
| 09-image-verify | QEMU smoke boot | 2-5 min |

Status anytime: `scripts/build/orchestrate.sh status`. Crashed mid-step? Re-run `run` — resumes.

### 1.3 Image output

After step 09 passes:

```
build/sain-01/output/
  sain-01            ← bootable disk image
  vmlinuz-6.12.x-znver5
  initrd.img-...
  ...
```

## 2. DURING-INSTALL — write to disk

### 2.1 Dump image to first NVMe

```sh
# DESTRUCTIVE — confirm device first
sudo dd if=build/sain-01/output/sain-01 of=/dev/nvme0n1 bs=4M status=progress conv=fsync
```

### 2.2 Boot from NVMe + MOK enrollment

First boot: UEFI MOK Manager prompts to enroll the sovereign-os MOK.
Enter password set in `scripts/hooks/during-install/mok-enroll.sh`.

### 2.3 ZFS pool + datasets

```sh
SOVEREIGN_OS_POOL_DEVICES="/dev/nvme0n1p2 /dev/nvme1n1" \
  sudo scripts/hooks/during-install/zfs-pool-create.sh
sudo scripts/hooks/during-install/zfs-datasets-create.sh
```

Creates `tank` (RAID 0) + `tank/models` (1M lz4) + `tank/context`
(16k zstd-9 copies=2 sync=always) + `tank/agents` (128k zstd-3).

## 3. POST-INSTALL — first-boot hooks

These run automatically once at first boot if the live-build hook
wired them as a systemd `oneshot`. Otherwise invoke manually:

```sh
sudo scripts/hooks/post-install/friction-audit-runtime.sh      # validate real hardware
sudo scripts/hooks/post-install/vfio-bind-3090.sh              # bind 3090 to vfio-pci
sudo scripts/hooks/post-install/network-vlan-config.sh         # VLAN 100/200 split
sudo scripts/hooks/post-install/tetragon-policy-load.sh        # load sovereign-kernel-fence
sudo scripts/hooks/post-install/zfs-arc-clamp.sh               # clamp ARC to 128 GB
sudo scripts/hooks/post-install/nvidia-driver-bind.sh          # nouveau blacklist + nvidia check
sudo scripts/hooks/post-install/workstation-shell-setup.sh     # bash-completion + /etc/skel
sudo scripts/hooks/post-install/first-login-assistant.sh       # interactive customization
```

Reboot once after `vfio-bind-3090.sh` so the VFIO module owns the
3090 from initramfs.

## 4. POST-INSTALL — inference stack

### 4.1 Install systemd units

```sh
sudo cp -r systemd/system/*.{service,timer} /etc/systemd/system/
sudo mkdir -p /etc/sovereign-os
sudo cp systemd/env.examples/inference-*.env /etc/sovereign-os/
sudo systemctl daemon-reload
```

### 4.2 Pull a model (sain-01 Oracle Core default = Nemotron)

```sh
sudo sovereign-osctl models pull nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16
sudo sovereign-osctl models pull microsoft/bitnet-b1.58-2B-4T   # Pulse model
```

### 4.3 Enable inference services

```sh
# Per-profile activation; sain-01 enables all four
sudo systemctl enable --now sovereign-pulse sovereign-logic-engine sovereign-oracle-core sovereign-router
sudo systemctl enable --now sovereign-zfs-scrub.timer sovereign-tetragon-verify.timer sovereign-models-sync.timer
```

### 4.4 Verify

```sh
sovereign-osctl status
sovereign-osctl doctor
sovereign-osctl inference status
sovereign-osctl audit friction
sovereign-osctl audit perimeter
sovereign-osctl audit storage
```

All should PASS. Logs: `journalctl -u sovereign-* -f`.

### 4.5 First inference

```sh
# Through the router (auto-routes by request shape)
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "microsoft/bitnet-b1.58-2B-4T", "messages": [{"role": "user", "content": "hello"}]}'
# → routed to Pulse (port 8081, bitnet.cpp)

curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "auto", "messages": [{"role": "user", "content": "```python def f(): pass ```"}]}'
# → routed to Oracle Core (port 8083, vLLM + DFlash)
```

## 5. ONGOING MANAGEMENT

| Task | Command |
|---|---|
| Profile switch | `sovereign-osctl profiles switch <id>` |
| Re-render whitelabel | `sovereign-osctl whitelabel apply <id>` |
| Re-run first-login assistant | `sovereign-osctl assistant` |
| Tetragon reload | `sovereign-osctl perimeter reload` |
| Manual scrub | `sovereign-osctl maintenance scrub` |
| Inference logs | `sovereign-osctl inference logs <tier>` |
| Decommission | `sovereign-osctl decommission start` (3-phase; gated by env var) |

## 6. Troubleshooting

| Symptom | Diagnostic |
|---|---|
| Build crashes mid-kernel-compile | `scripts/build/orchestrate.sh status` → re-run; resumes |
| friction-audit fails M.2_2 check | Power down; remove anything in M.2_2 slot; reboot |
| `nvidia-smi` shows both GPUs (3090 should be hidden) | VFIO didn't load early enough; check `/proc/cmdline` for `vfio-pci.ids=`; rebuild initramfs |
| Tetragon SIGKILLing legitimate process | `sudo journalctl -u tetragon -f`; add allowlist entry to `sovereign-kernel-fence.yaml`; reload |
| Oracle Core OOM | `ORACLE_KV_CACHE_DTYPE=fp8` (default for sain-01); reduce `gpu_memory_utilization` in vLLM start script |
| Router 502 for tier X | `sovereign-osctl inference logs <tier>`; tier daemon likely crashed/not started |

## 7. Old-workstation profile install

Same flow, simpler: skip MOK / VFIO / dual-GPU / ZFS-tiered steps;
ext4 rootfs; only `sovereign-router.service` + `sovereign-logic-engine.service`
(with `SOVEREIGN_OS_LOGIC_BACKEND=llama_cpp`). No Pulse, no Oracle Core,
no DFlash. Tetragon optional.
