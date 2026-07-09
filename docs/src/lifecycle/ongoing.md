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

The full operator-named maintenance + telemetry cadence (18 timers; each
fires a hook under `scripts/hooks/recurrent/` that emits a Layer B metric
snapshot — see `docs/observability/dashboards/README.md` for the metrics).
Ordered most-frequent first:

| Timer | Schedule | What |
|---|---|---|
| `sovereign-power-shutdown-guard.timer` | Every minute | UPS / battery monitor + graceful-shutdown guard (R253, Z-18) |
| `sovereign-wattage-sample.timer` | Every minute | PSU wattage Layer-B sampler (R258, Z-18) |
| `sovereign-memory-pressure-sample.timer` | Every minute | Memory-pressure / OOM Layer-B sampler (E1.M15) |
| `sovereign-wattage-heat-trend.timer` | Every minute | Wattage + heat trend-verdict tick (E1.M36) |
| `sovereign-telemetry-textfile.timer` | Every minute | sovereign-telemetry probe → node_exporter textfile (M045 E0430 / M013) |
| `sovereign-thermal-watch.timer` | Every 5 min | Chassis / CPU / GPU thermal sample (R172) |
| `sovereign-session-reaper.timer` | Every 2 min | M057 session reaper — archive sessions whose process exited (SDD-065) |
| `sovereign-memory-observe.timer` | Every 5 min | M028 observation event stream — auto-feed memory admission from the OCSF span log (SDD-069) |
| `sovereign-alerts-check.timer` | Hourly | Alert derivation snapshot |
| `sovereign-notify-dispatch.timer` | Hourly | Health-scan + notification fan-out (R229, Z-6) |
| `sovereign-backup-snapshot.timer` | Daily 02:30 | State-fabric ZFS snapshot |
| `sovereign-models-sync.timer` | Daily 03:30 | Resident model catalog verification |
| `sovereign-log-rotate.timer` | Daily 03:30 | Log rotation trigger |
| `sovereign-tetragon-verify.timer` | Daily 04:00 | Perimeter TracingPolicy integrity check |
| `sovereign-security-update-check.timer` | Daily 04:15 | Security-update availability check |
| `sovereign-zfs-scrub.timer` | Weekly (Sun 02:00) | ZFS pool scrub |
| `sovereign-selfdef-sync.timer` | Weekly (Sun 05:30) | selfdef checkout freshness check (SDD-001) |
| `sovereign-ghostproxy-verify.timer` | Weekly (Sun 06:00) | root-ghostproxy AI-agent envelope drift verify — read-only `--check`, endpoint mode (SDD-046) |

This table is the operator-facing mirror of the canonical 18-hook cadence
locked by `tests/lint/test_recurrent_hooks_contract.py`; adding or removing
a recurrent hook means updating both.

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
