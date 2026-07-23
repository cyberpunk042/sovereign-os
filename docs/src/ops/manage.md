# Lifecycle management (operator handbook)

`sovereign-osctl` is the single entry-point. See [ongoing-management lifecycle stage](../lifecycle/ongoing.md) for the full reference.

## Daily operator commands

```sh
sovereign-osctl status                # one-page system overview
sovereign-osctl doctor                # profile-conditioned multi-section health audit
                                      # (tooling / systemd / zfs / tpm2 /
                                      # observability / inference / build-state)
sovereign-osctl inference status      # per-tier systemd unit state
sovereign-osctl inference health      # per-tier HTTP /healthz probe + TCP fallback
sovereign-osctl audit friction        # runtime hardware audit
sovereign-osctl audit perimeter       # Tetragon policy integrity
sovereign-osctl audit storage         # ZFS pool + dataset health
sovereign-osctl audit provenance      # SLSA v1 build-provenance + sha256sums cross-check
```

`doctor` and `inference health` are both safe to run unprivileged and
exit non-zero when something needs attention — wire them into
operator-side cron / Prometheus blackbox / fleet-manager dashboards.

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

## Desktop + agent runtimes (SDD-704–707)

The box's **face** and two **AI agent runtimes** are build-time-selectable (in the
profile's `provisioning:` block) and runtime-switchable — no reflash. Full guide:
[Use the box as your AI backend](../ai-backend.md).

```sh
# the face — what boots on the display
sovereign-osctl frontend list
sudo sovereign-osctl frontend set {gnome|kde-plasma|dashboards-kiosk|open-computer-kiosk|none}

# OpenClaw — Node agent gateway (installed-off; SDD-705)
sovereign-osctl openclaw status
sudo sovereign-osctl openclaw install          # first-boot installer (Node + npm + preconfig)
sudo sovereign-osctl openclaw {on|off}
sudo sovereign-osctl openclaw backend {local|anthropic|show} [--key K]   # local model ↔ hosted Claude

# open-computer — QEMU AI-sandbox VM (installed-off; SDD-706)
sovereign-osctl open-computer status
sudo sovereign-osctl open-computer install     # QEMU/KVM + Node + ~3GB base image
sudo sovereign-osctl open-computer {on|off}
sovereign-osctl open-computer url               # the sandbox UI (http://localhost:9800)
sudo sovereign-osctl open-computer backend {local|anthropic|show} [--key K]
```

The hosted-Claude key is operator-supplied (`--key` → root-only
`/etc/sovereign-os/anthropic-key.env`), **never baked** into the image.

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

## Observability dashboards

Three Grafana JSON dashboard templates ship at
`docs/observability/dashboards/`:

| File | Coverage |
|---|---|
| `sovereign-os-overview.json` | At-a-glance: pipeline last-run, per-tier inference counters, ZFS health, perimeter status, build step durations, log rotation, snapshots, pending security updates |
| `sovereign-os-inference.json` | Per-tier route rate + cumulative, last-router-decision age, backend start success/fail/skip counts |
| `sovereign-os-install.json` | Install lifecycle: rootfs-format / pool-create / datasets-create / MOK enroll / friction-audit failures + warnings / VFIO bind / NVIDIA bind / ARC max bytes / Tetragon policy / network VLAN / shell setup / image-sign per posture |

Operator imports via Grafana → Dashboards → New → Import → Upload JSON.
See `docs/observability/dashboards/README.md` for the full metric
inventory (51 metric names emitted across build pipeline, pre-install,
during-install, post-install, recurrent maintenance, inference, and
perimeter) and provisioning notes.

CI gates a two-way contract:
  • `test_dashboard_metrics_lockstep.py` — a panel that references a
    metric no script emits fails Layer 1 lint
  • `test_metric_inventory_lockstep.py` — a metric emitted by a script
    that isn't documented in the inventory fails Layer 1 lint
  • `test_hook_layer_b_coverage.py` — a lifecycle hook that never calls
    `emit_metric` (and lacks an explicit `# LAYER-B-WAIVER:`) fails
    Layer 1 lint

Together: every metric the code emits is documented, every metric the
dashboards reference is emitted, and every lifecycle hook participates.
