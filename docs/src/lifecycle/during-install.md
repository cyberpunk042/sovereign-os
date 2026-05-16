# During-install lifecycle stage

What runs **while writing the image to disk + first-boot setup**.

## Profile hooks (`hooks.during_install`)

For `sain-01`:

| Hook | Purpose |
|---|---|
| `zfs-pool-create.sh` | `zpool create tank` (RAID 0 across NVMe per `hardware.storage.devices`) |
| `zfs-datasets-create.sh` | Create `tank/models` (1M lz4) + `tank/context` (16k zstd-9 sync=always copies=2) + `tank/agents` (128k zstd-3) |
| `mok-enroll.sh` | Generate operator MOK keypair + queue mokutil import (only when `secure_boot=signed`) |

For `old-workstation`:

| Hook | Purpose |
|---|---|
| `rootfs-format-ext4.sh` | `mkfs.ext4` on operator-supplied device |

## Manual invocation

```sh
# Image is dd'd to NVMe; first boot brings up minimal Debian.
# Then run during-install hooks:
sudo SOVEREIGN_OS_POOL_DEVICES="/dev/nvme0n1p2 /dev/nvme1n1" \
  scripts/hooks/during-install/zfs-pool-create.sh
sudo scripts/hooks/during-install/zfs-datasets-create.sh
sudo scripts/hooks/during-install/mok-enroll.sh    # only if secure_boot=signed
```

## Destructive operations gated

- `zfs-pool-create.sh` — confirms device list; refuses without `SOVEREIGN_OS_POOL_DEVICES`
- `mok-enroll.sh` — generates key in `/var/lib/sovereign-os/mok/` (chmod 700) and queues for next-reboot enrollment via mokutil
- `rootfs-format-ext4.sh` — confirms operator wants to format the device (default no)

## Operator-supplied env vars

| Var | Used by | Default |
|---|---|---|
| `SOVEREIGN_OS_POOL_DEVICES` | zfs-pool-create | (required; operator supplies) |
| `SOVEREIGN_OS_ROOTFS_DEV` | rootfs-format-ext4 | (required; operator supplies) |
| `SOVEREIGN_OS_MOK_DIR` | mok-enroll | `/var/lib/sovereign-os/mok` |
