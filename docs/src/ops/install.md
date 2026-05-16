# Image installation (operator handbook)

Full step-by-step at [install-runbook.md](../install-runbook.md) — the canonical operator document.

## TL;DR

```sh
# 1. Build the image (build host, not target)
sudo scripts/build/orchestrate.sh run

# 2. dd to target NVMe
sudo dd if=build/sain-01/output/sain-01 of=/dev/nvme0n1 bs=4M status=progress conv=fsync

# 3. Boot from NVMe; MOK manager prompts at first boot (if secure_boot=signed)

# 4. Run during-install hooks
sudo SOVEREIGN_OS_POOL_DEVICES="/dev/nvme0n1p2 /dev/nvme1n1" \
  scripts/hooks/during-install/zfs-pool-create.sh
sudo scripts/hooks/during-install/zfs-datasets-create.sh

# 5. Run post-install hooks
sudo scripts/hooks/post-install/friction-audit-runtime.sh
sudo scripts/hooks/post-install/vfio-bind-3090.sh
# ... full list in the install runbook

# 6. Install systemd units
sudo cp -r systemd/system/*.{service,timer} /etc/systemd/system/
sudo mkdir -p /etc/sovereign-os
sudo cp systemd/env.examples/inference-*.env /etc/sovereign-os/
sudo systemctl daemon-reload

# 7. Enable + start inference stack
sudo sovereign-osctl inference start all
```

## Installer experience (Q-008)

Currently: manual hook invocation per the recipe above. Stage-2 next round: an installer wrapper (debian-installer derivative OR Calamares OR custom TUI — Q-008 operator decision pending).
