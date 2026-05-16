# Unattended install — cloud-init + preseed answer files

Q-018 "pre-add" path per operator directive: *"post install script ready to be pre-added or even automatically launch on first login and such. based on what is chosen by the user"*.

Two delivery mechanisms, choose one per install:

## A. cloud-init (NoCloud datasource)

Easier; works without debian-installer; uses YAML.

| File | Profile |
|---|---|
| [`sain-01.user-data.example.yaml`](sain-01.user-data.example.yaml) | SAIN-01 default — full Trinity stack |
| [`old-workstation.user-data.example.yaml`](old-workstation.user-data.example.yaml) | Constrained-hardware alternate (llama.cpp only) |

### Procedure

1. Copy the example to your USB stick / ISO / HTTP source as `user-data`.
2. Edit operator-specific values (ssh keys, hostname, model picks).
3. Add a `meta-data` file alongside with at least:
   ```yaml
   instance-id: $(uuidgen)
   ```
4. Format the USB stick or ISO with VFAT, label it **CIDATA**.
5. Boot the sovereign-os install image with the CIDATA source attached.
6. cloud-init reads + applies on first boot.

### What the cloud-init file does

- Sets hostname, SSH key, locale, timezone.
- Writes `/etc/sovereign-os/active-profile.env` + `active-profile` + `active-whitelabel`.
- Pre-populates `/var/lib/sovereign-os/assistant/state.yaml` with `completed: true` (skips interactive first-login assistant).
- Enables `sovereign-firstboot.target` + inference stack services + recurrent timers.
- Optional: pre-pulls a default model (commented by default).

## B. debian-installer preseed (alternative path)

Use this if you're booting a debian-installer-derived image. Provides the same end-state via preseed.

| File | Profile |
|---|---|
| [`../preseed/sain-01.preseed.example.cfg`](../preseed/sain-01.preseed.example.cfg) | SAIN-01 default |

### Procedure

1. Place at `/preseed/sain-01.cfg` on the install media.
2. Boot installer with kernel cmdline: `auto url=file:///preseed/sain-01.cfg`
3. Installer reads + applies non-interactively.

## What stays interactive even with pre-add files

- MOK enrollment password (`secure_boot=signed` profiles only) — UEFI MOK Manager prompts at first boot regardless.
- Operator confirmation for destructive operations (decommission flow has `SOVEREIGN_OS_CONFIRM_DESTROY=YES` env gate that can't be bypassed by config).

## Verifying unattended install

```sh
# Should show: completed: true; preadded_by: cloud-init
cat /var/lib/sovereign-os/assistant/state.yaml

# Should show: cloud-init unattended install complete
cat /var/lib/sovereign-os/cloud-init.log

# Should show services active
sovereign-osctl inference status
sovereign-osctl status
```
