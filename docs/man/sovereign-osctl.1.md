% SOVEREIGN-OSCTL(1) sovereign-os 0.2.0 | sovereign-os Operator Manual
% cyberpunk042
% 2026-05-16

# NAME

sovereign-osctl - lifecycle management CLI for sovereign-os

# SYNOPSIS

**sovereign-osctl** [_command_] [_subcommand_] [_options_]

# DESCRIPTION

**sovereign-osctl** is the single operator entry-point for managing
an installed sovereign-os system. It surfaces every recurrent hook,
every audit verb, every inference-tier control, and the management
flows for profiles / whitelabels / models / perimeter / decommission.

Designed to be installed at `/usr/local/bin/sovereign-osctl` on the
target system; in-repo it dispatches to scripts under
`scripts/hooks/*` via the common library.

# COMMANDS

## Top-level
**status**
:   System state overview: profile · OS · kernel · uptime · ZFS pool ·
    Tetragon · GPU · network · whitelabel.

**doctor**
:   Profile-conditioned multi-section health audit covering tooling,
    systemd, ZFS (zfs-tiered profiles only), TPM2 (signed/shim profiles),
    observability, inference reachability, and build-state freshness.
    Exits non-zero on any issue (warnings don't block).

**version** [**--json**]
:   Print sovereign-osctl + system version info. Use `--json` for
    fleet-tool integration (7-key stable contract).

**help**, **--help**, **-h**
:   This help.

## Profile management
**profiles list**
:   List declared profiles.

**profiles show** _id_
:   Print raw profile YAML.

**profiles show-effective** _id_
:   Print profile with mixins + parent resolved (via profile_merger).

**profiles active**
:   Echo the active profile ID.

**profiles switch** _id_
:   Swap active profile (flags items requiring rebuild).

**profiles validate**
:   Schema-validate all profiles (raw + resolved).

## Whitelabel
**whitelabel list**, **whitelabel show**, **whitelabel apply** _id_,
**whitelabel diff** _id_
:   Manage the operator's whitelabel selection. `diff` shows a
    unified diff between active and `id` before applying.

## Models (HuggingFace + on-disk catalog)
**models list**, **models pull** _hf-id_, **models verify**,
**models size**, **models remove** _name_
:   List residents, pull from HuggingFace, verify manifest.sha256,
    show per-model disk usage, delete (confirms; SOVEREIGN_OS_ASSUME_YES=1
    bypasses).

## Perimeter (Tetragon)
**perimeter status**, **perimeter verify**, **perimeter reload**

## Inference (Pulse + Logic Engine + Oracle Core + Router)
**inference status**
:   Per-tier systemd unit state.

**inference health**
:   HTTP `/healthz` probe + TCP fallback for every tier.

**inference start** {**pulse** | **logic** | **oracle** | **router** | **all**}
:   Start a tier (requires root).

**inference stop** _tier_, **inference restart** _tier_

**inference route** _prompt_
:   Show which tier the router would pick for a sample prompt
    (deterministic classify() result; no actual dispatch).

**inference logs** _tier_
:   Tail systemd journal for the tier.

## Audit
**audit friction**
:   Runtime hardware audit (lspci / lscpu / IOMMU).

**audit perimeter**
:   Tetragon policy integrity.

**audit storage**
:   ZFS pool + dataset health.

**audit provenance** [_manifest-path_]
:   Inspect SLSA v1 build-provenance.json + cross-check sha256sums.txt.
    Exits 2 on digest mismatch (alarm signal).

## Maintenance (on-demand recurrent ops)
**maintenance list**, **maintenance scrub**, **maintenance arc-status**,
**maintenance log-rotate**, **maintenance snapshot**,
**maintenance security-check**, **maintenance models-sync**,
**maintenance perimeter-check**
:   Each subverb runs the matching recurrent hook on demand. Useful
    when you don't want to wait for the systemd timer cadence.

## Assistant (first-login flow)
**assistant full**, **assistant status**, **assistant reset**,
**assistant list**

## Decommission (destructive — gated)
**decommission start**, **decommission pool**, **decommission wipe**
:   Three-phase destructive flow. All gates require
    `SOVEREIGN_OS_CONFIRM_DESTROY=YES` env + interactive confirm.

# ENVIRONMENT

**SOVEREIGN_OS_PROFILE**
:   Active profile (default: contents of `/etc/sovereign-os/active-profile`,
    falling back to `sain-01`).

**SOVEREIGN_OS_NONINTERACTIVE**
:   When set, skip interactive prompts; `confirm default-yes` succeeds,
    `confirm default-no` refuses.

**SOVEREIGN_OS_ASSUME_YES**
:   Set to `1` to bypass `confirm` for scripted invocations of
    state-mutating commands (rewind, skip, models remove, assistant
    reset, etc.).

**SOVEREIGN_OS_LOG_LEVEL**
:   `debug` | `info` | `warn` | `error` (default `info`).

**SOVEREIGN_OS_METRICS_DIR**
:   Prometheus textfile collector dir (default:
    `/var/lib/node_exporter/textfile_collector`).

**SOVEREIGN_OS_METRICS_DISABLE**
:   Set to `1` to suppress all Layer B metric emission.

# EXAMPLES

Verify the system after fresh install:

    sudo sovereign-osctl doctor
    sovereign-osctl status

Verify the build is reproducible:

    sovereign-osctl audit provenance build/sain-01/output/build-provenance.json

Probe inference tiers:

    sovereign-osctl inference health
    sovereign-osctl inference route "compute 2+2 in python"

Switch whitelabel after previewing the change:

    sovereign-osctl whitelabel diff custom-brand
    sudo sovereign-osctl whitelabel apply custom-brand

Trigger ZFS snapshot + log rotation on demand:

    sudo sovereign-osctl maintenance snapshot
    sudo sovereign-osctl maintenance log-rotate

# FILES

**/etc/sovereign-os/active-profile**
:   One-line profile id; read by sovereign-osctl on startup.

**/etc/sovereign-os/active-whitelabel**
:   One-line whitelabel id.

**/var/lib/sovereign-os/**
:   Per-machine runtime state (assistant state, first-boot markers).

**/mnt/vault/models/**
:   HuggingFace model catalog (for zfs-tiered profiles).

**/var/lib/node_exporter/textfile_collector/sovereign-os-*.prom**
:   Layer B Prometheus metrics output.

# SEE ALSO

**orchestrate.sh**(1) — build pipeline driver

# REPORTING BUGS

GitHub: <https://github.com/cyberpunk042/sovereign-os/issues>

# LICENSE

AGPL-3.0-or-later
