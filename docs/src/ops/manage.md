# Lifecycle management (operator handbook)

`sovereign-osctl` is the single entry-point. See [ongoing-management lifecycle stage](../lifecycle/ongoing.md) for the full reference.

## Daily operator commands

```sh
sovereign-osctl status                # one-page system overview
sovereign-osctl doctor                # sanity checks
sovereign-osctl inference status      # per-tier inference table
sovereign-osctl audit friction        # runtime hardware audit
```

## Profile management

```sh
sovereign-osctl profiles list
sovereign-osctl profiles show sain-01
sovereign-osctl profiles show-effective sain-01    # with mixins resolved
sovereign-osctl profiles validate                  # schema-check all profiles
sudo sovereign-osctl profiles switch <id>
```

## Whitelabel

```sh
sovereign-osctl whitelabel list
sovereign-osctl whitelabel show
sudo sovereign-osctl whitelabel apply <id>
```

## Perimeter

```sh
sovereign-osctl perimeter status
sudo sovereign-osctl perimeter verify
sudo sovereign-osctl perimeter reload
```

## Models

```sh
sovereign-osctl models list
sudo sovereign-osctl models pull microsoft/bitnet-b1.58-2B-4T
sudo sovereign-osctl models pull nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16
sovereign-osctl models verify
```

## Inference

```sh
sovereign-osctl inference status
sudo sovereign-osctl inference start pulse        # start one tier
sudo sovereign-osctl inference start all          # start everything
sudo sovereign-osctl inference restart logic
sovereign-osctl inference route "```python def f(): pass ```"   # → oracle_core
sovereign-osctl inference logs oracle
```

## Maintenance

```sh
sudo sovereign-osctl maintenance scrub            # manual ZFS scrub
sovereign-osctl maintenance arc-status            # ZFS ARC stats
```

## Decommission

```sh
sudo sovereign-osctl decommission start           # phase 1 (state-fabric wipe)
SOVEREIGN_OS_CONFIRM_DESTROY=YES sudo sovereign-osctl decommission pool
SOVEREIGN_OS_CONFIRM_DESTROY=YES SOVEREIGN_OS_WIPE_DEVICES='/dev/nvme0n1 /dev/nvme1n1' \
  sudo sovereign-osctl decommission wipe
```
