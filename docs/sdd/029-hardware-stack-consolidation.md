# SDD-029 — Hardware-stack consolidation (Z-14 / Z-17 / Z-18 / Z-19)

> Status: **review**
> Owner: sovereign-os core
> Last updated: 2026-05-17
> Closes findings: none (vector grouping + cross-vector contract)
> Derived from: R239 (kernel-tuning) + R251 (bios-info) + R252 (power-status)
>                + R253 (power-shutdown-guard) + R255 (virt-info)

> **Parent standing directive:**
> [`docs/standing-directives/2026-05-17-operator-mandate.md`](../standing-directives/2026-05-17-operator-mandate.md)
> (Epic E1 — Hardware-stack visibility & control).
> Each round in this SDD closes one Module under E1.

## Mission

Operator's 2026-05-17 expansion named SEVEN distinct hardware-stack
concerns in a single block (kernel optimization / OS / BIOS / memory /
PCI / PSU / UPS / virtualization). SDD-029 codifies the layered
HARDWARE-STACK DOCTRINE that the cycle-8 rounds R239-R255 followed
when those concerns landed as four new SDD-026 Z-vectors:

  Z-14 — kernel tuning (sysctl presets + GRUB cmdline hints)
  Z-17 — BIOS / baseboard / memory (board-specific advisories)
  Z-18 — PSU + UPS + wattage budget + graceful shutdown
  Z-19 — virtualization (CPU virt flags + KVM + IOMMU + PCIe lanes + runtimes)

Each Z-vector got: a probe script under `scripts/hardware/`, an osctl
bridge, a dashboard card, and an L3 test asserting JSON-shape stability
+ operator-readable rendering. The four together form the
"hardware-stack" doctrine documented here.

## Operator-verbatim source

The relevant operator expansion (sacrosanct):

> "Kernel optimisation, OS, Services, Modules, Tools, Dashboards,
>  Configurations, Options. Network, App, & In between. Memory too
>  I guess and bios settings directives and admonition of things
>  that might also not be possible on some board, possibly detecting
>  the ASUS ProArt X870E-CREATOR WIFI and its settings and potential
>  optimisations and fixes. pci lane splits and whatever like
>  virtualization or what we find relevant via search online and
>  such. Adapting / Considering the given PSU (probably not detectable
>  ?) wattage and rating ? (me: be Quiet! Dark Power Pro 13 1600W
>  Power Supply | ATX 3.1 Compliant | 80 Plus Titanium), considering
>  XMP profile and OC profile and room for each and estimated at 100%
>  usage and then real time tracking and intelligence around it.
>  (Possibly heat too I guess) My PSU even have an overclock mode
>  which might be important. Then there is the PSU/APC integration
>  with the power management and the scheduled shutdown when battery
>  reach a certain point as one default profile.
>  (schedule/planifest/graceful on all levels, orderly)."

## Doctrine

### 1. Per-vector probe contract

Every hardware-stack vector ships a `scripts/hardware/<name>.py`
script that:

- Returns JSON via `--json` with a stable schema (`round`, `vector`,
  + per-vector fields).
- Returns operator-readable text without `--json` (banner +
  per-section blocks).
- Reads ONLY (no mutation in the probe; mutation lives in companion
  scripts like `gpu-remediate.py` or systemd hooks).
- Degrades gracefully when underlying tools are absent (dmidecode /
  lspci / apcaccess / upsc) — JSON shape stays consistent;
  human render says "(unavailable)".

### 2. Operator-supplied configuration

Operators declare site-specific facts in `/etc/sovereign-os/*.toml`:

| File                       | Vector | Declares                       |
|----------------------------|--------|--------------------------------|
| kernel-tuning.toml         | Z-14   | sysctl presets + cmdline hints |
| power.toml                 | Z-18   | PSU model + rated W + UPS thresholds |
| (n/a — sysfs-only)         | Z-17   | BIOS/memory read from dmidecode |
| (n/a — kernel-only)        | Z-19   | virt state read from /proc + /sys |

Secrets NEVER live in-repo (SDD-009): UPS credentials, BIOS passwords,
etc. are referenced via env-var indirection where they exist.

### 3. Board-specific advisory table

`scripts/hardware/bios-info.py` ships a `KNOWN_BOARDS` registry.
Cycle-8 seeds operator's actual hardware: **ASUS ProArt X870E-CREATOR
WIFI** with 6 advisories spanning AMD EXPO, PCIEX16_1/PCIEX16_2 lane
splits, AMD-V (SVM), IOMMU + ACS Override, firmware ≥ 1303 fix, and
Marvell AQC113 cloudflared workaround.

Operator-pull workflow: future round adds boards via:

```toml
# config/known-boards.toml.example (TODO)
[[boards]]
match_id = "ProArt X870E-CREATOR WIFI"
vendor = "ASUSTeK COMPUTER INC."
...
```

(Cycle-8 ships the table hardcoded in Python; the move to TOML is a
future-round refactor when the table grows past ~5 entries.)

### 4. Graceful-shutdown contract

`power-shutdown-guard.sh` (R253) ties the R252 advisory verdict to a
`shutdown(8)` invocation through THREE explicit gates:

1. Probe verdict MUST be `critical` (battery ≤ threshold AND/OR
   time_left ≤ threshold).
2. Arm flag MUST be set
   (`SOVEREIGN_OS_POWER_SHUTDOWN_ARMED=YES` env OR
   `[graceful_shutdown] enabled = true` config).
3. `SOVEREIGN_OS_DRY_RUN=1` short-circuits all paths.

When critical-but-not-armed, the hook WARNS loudly with the exact
arm instructions instead of either silently doing nothing or silently
shutting down. Operators see both ends. Wall warning goes out via
`shutdown -h +N <message>` so live sessions can save work.

Per-minute timer cadence — frequent enough to catch the critical
threshold within the operator's `shutdown_minutes` window.

### 5. Dashboard surface contract

Every hardware-stack vector grows a dashboard card matching the
SDD-026 Z-1 contract: `{id, title, data: {round, vector, summary,
needs_attention, ...}}`. The R248 terminal grid surfaces every
card; the R225 HTML dashboard renders them in a 3-column flex grid.

R254 wired R251 (bios) + R252 (power) into the dashboard. R256
(this SDD) does NOT add cards — Z-14 and Z-19 dashboard cards land
in a follow-up round when the value justifies the dashboard real
estate. Operators today consume Z-14/Z-19 via the CLI + JSON
endpoints.

## Cross-vector composition

The vectors share signals where useful:

  Z-18 budget    ← reads R219 GPU watt .prom file from Z-5
  Z-14 cmdline   ← lists IOMMU enablement that Z-19 then verifies
  Z-17 advisories ← cites kernel-tuning + virt knobs from Z-14/Z-19
  Z-18 shutdown  ← consults Z-15 services to gracefully stop them
                   first (FUTURE-round refinement — cycle 8 just
                   calls `shutdown -h +N` which systemd handles)

## What this SDD does NOT cover

- Live thermal probing (already handled by R172 thermal-watch).
- GPU power remediation (R219 + R249).
- CPU mode hotswap (R221 + R230).
- Profile lifecycle (R224 + R245 flex).

Those vectors predate the cycle-8 hardware-stack work and follow
their own contracts.

## Future-round roadmap

| Round | Title                                          | Vector   |
|-------|------------------------------------------------|----------|
| R257  | XMP/EXPO profile detection (DIMM rated vs configured) | Z-17 |
| R258  | Real-time wattage sampler (Z-18 + R219 → time-series .prom) | Z-18 |
| R259  | PSU overclock mode toggle (gated via config flag) | Z-18 |
| R260  | KNOWN_BOARDS TOML refactor when table > 5 entries | Z-17 |
| R261  | Z-14 + Z-19 dashboard cards                    | Z-14 + Z-19 |
| R262  | Schedule-manifest framework (gracefully drain & shutdown N services then poweroff) | Z-18 + Z-15 |

## Verification

Each cycle-8 round's L3 test asserts JSON-shape stability across
absent-tool paths. 272 lint+schema tests + 30+ L3 tests stay green
through every round of this arc.
