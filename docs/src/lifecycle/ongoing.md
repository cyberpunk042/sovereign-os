# Ongoing-management lifecycle stage

The OS is **not a frozen snapshot**. Per the operator's verbatim quality bar:

> "even once installed and configured it will be possible to manage the OS like we need to even if we need to add such an additional tool and even service possibly or even multiple adapted if need be"

This stage covers **everything that happens after first-boot, for the life of the deployment**.

## Single entry point — `sovereign-osctl`

| Command | Purpose |
|---|---|
| `sovereign-osctl status` | System overview (profile, OS, kernel, uptime, ZFS, Tetragon, GPUs, network, whitelabel) |
| `sovereign-osctl doctor` | Sanity-check required tools + units + pool |
| `sovereign-osctl assistant` | Re-run first-login assistant |
| `sovereign-osctl profiles list \| show \| show-effective \| switch \| validate` | Profile catalog management |
| `sovereign-osctl whitelabel show \| list \| apply` | Whitelabel management |
| `sovereign-osctl perimeter status \| verify \| reload` | Tetragon TracingPolicy ops |
| `sovereign-osctl models list \| pull \| verify` | Resident model catalog |
| `sovereign-osctl audit friction \| perimeter \| storage` | Runtime audits |
| `sovereign-osctl maintenance scrub \| arc-status` | ZFS ops |
| `sovereign-osctl inference status \| start \| stop \| restart \| route \| logs` | Per-tier inference management |
| `sovereign-osctl decommission start \| pool \| wipe` | 3-phase decommission |

## Recurrent hooks (systemd timers)

| Timer | Schedule | What |
|---|---|---|
| `sovereign-zfs-scrub.timer` | Sun 02:00 + ±30min jitter | Weekly ZFS scrub |
| `sovereign-tetragon-verify.timer` | Daily 04:00 + ±15min | Perimeter policy integrity check |
| `sovereign-models-sync.timer` | Daily 03:30 + ±30min | Resident model catalog verification |

## Adding a new tool / service

Operator's explicit ask: *"add such an additional tool and even service possibly or even multiple adapted if need be"*.

Pattern:
1. Add the tool to `profiles/<id>.yaml` `packages.profile` (or a mixin).
2. If it needs a service: write a systemd unit; place in `systemd/system/`.
3. If it needs a perimeter rule: add a Tetragon TracingPolicy YAML in `/etc/tetragon/tracing-policies/`.
4. If it needs lifecycle ops: extend `sovereign-osctl` with a new subcommand pattern.
5. `sovereign-osctl profiles validate` to confirm schema-conformance.

## Profile evolution

Profile bodies are versioned. Increment `identity.version` on substantive changes. The merger respects semver (Q5-B) — bump major for breaking schema changes; minor for additive; patch for fixes.

## Whitelabel evolution

```sh
sovereign-osctl whitelabel apply <new-id>
```

Render-on-running-system for the non-rebuild strategies (template-substitution + file-overlay). Build-time-flag changes (kernel `KBUILD_BUILD_USER`) require image rebuild.

## Decommission

```sh
# Three phases; each confirms; SOVEREIGN_OS_CONFIRM_DESTROY=YES required for destructive
sovereign-osctl decommission start    # wipe state-fabric (shred tank/context)
SOVEREIGN_OS_CONFIRM_DESTROY=YES sudo sovereign-osctl decommission pool   # destroy ZFS pool
SOVEREIGN_OS_CONFIRM_DESTROY=YES SOVEREIGN_OS_WIPE_DEVICES='/dev/nvme0n1 /dev/nvme1n1' \
  sudo sovereign-osctl decommission wipe   # NVMe secure-erase
```

## Q-019 — surface choice closed

The `sovereign-osctl` CLI **IS** the lifecycle-management surface (Q-019). Substrate-agnostic (works regardless of mkosi vs live-build vs rpm-ostree choice). Per-tier ops via systemd; whitelabel render via Python.

A future Stage-2 PR may add a Web UI on top of the same backend operations.
