#!/usr/bin/env bash
# systemd unit state — desired enable/disable/mask for every unit we assert on
# gate: IAC_ENABLE_SYSTEMD
#
# WHY: profiles.provisioning.posture is "installed-off" — units ship present but
# inactive, and the operator turns things on deliberately. That posture is
# correct, but it says nothing about units that are actively BROKEN. This module
# encodes both: the installed-off baseline, plus the specific units that must be
# held down because their dependencies were never installed.
#
# The table below is the whole spec. Format:  <unit> <masked|disabled|enabled>
# Anything not listed is left exactly as the operator/packaging left it —
# converge asserts, it does not sweep.
#
# shellcheck shell=bash

# ─── units held down: shipped, but their dependency does not exist ───────────
#
# sovereign-gatewayd: /usr/local/bin/sovereign-gatewayd was never shipped
#   (sovereign-os-cockpit is Architecture:all and carries no compiled crates).
#   sovereign-jobs-api.service has Wants=sovereign-gatewayd.service, which pulls
#   it in at boot even though it is 'disabled' — so `disabled` is NOT enough,
#   it must be MASKED. It then respawned every 3s forever: RestartSec=3 with
#   the default StartLimitIntervalSec=10s means 5 restarts take 15s > 10s, so
#   the burst limiter never trips. 782 restarts before it was caught.
#   Unmask once crates/sovereign-gatewayd is built and installed.
#
# sovereign-telemetry-textfile.timer: the hook is correct-by-design (writes a
#   sovereign_telemetry_probe_failed sentinel and exits 1 when the probe is
#   unavailable) but /opt/sovereign-os/bin/sovereign-telemetry does not exist,
#   so it can only ever fail — once a minute, permanently degrading the system.
#
# sovereign-zfs-scrub.timer / sovereign-backup-snapshot.timer: originally held
#   down because there was no ZFS pool at all — both NVMe devices were
#   vfat/ext4/swap, and the custom 6.12.0 kernel had no zfs module either. The
#   stock 7.0.0 kernel restored the module, and module 95 built the pool the
#   hooks expect (tank, tank/context) on the reclaimed Debian disk. Their state
#   is now DERIVED from whether that pool is imported, so they hold themselves
#   down again if it ever disappears rather than failing on every fire.
#
# sovereign-tetragon-verify.timer: tetragon is not installed (no binary,
#   sovereign-tetragon-install.service is disabled) so the daily verify fails.
#
# These two are DERIVED, not hard-coded: their desired state is a function of
# whether module 80 has managed to install the executable they point at. Held
# down while absent; promoted automatically once present. That way "fix the
# packaging gap" and "turn the feature on" are the same operation, and nobody
# has to remember to edit this table.
# Note the two-word values: "<enable-state> <run-state>". `enabled` alone only
# takes effect at the NEXT boot — a daemon whose binary exists should be serving
# now, and a timer that is enabled but not started never fires until reboot.
# "enabled" without a run-state is correct only for units something else starts.
if [ -x /usr/local/bin/sovereign-gatewayd ]; then
  _gatewayd_state="enabled started"
  iac_info "sovereign-gatewayd binary present → promoting unit to enabled"
else
  _gatewayd_state="masked"
fi
if command -v sovereign-telemetry >/dev/null 2>&1 || [ -x /opt/sovereign-os/bin/sovereign-telemetry ]; then
  _telemetry_state="enabled started"
  iac_info "sovereign-telemetry binary present → promoting timer to enabled"
else
  _telemetry_state="disabled"
fi

# The ZFS timers are derived the same way, on the POOL rather than a binary.
# Both hooks default to exactly what module 95 builds:
#     zfs-scrub.sh        SOVEREIGN_OS_POOL_NAME=tank
#     backup-snapshot.sh  SOVEREIGN_OS_SNAPSHOT_DATASET=tank/context
# They were held disabled because no pool existed and they would fail on every
# fire. Timers are STARTED but not run immediately: a weekly scrub and a daily
# snapshot should begin on their own schedule, not the moment converge runs.
if zpool list -H -o name 2>/dev/null | grep -qx "${IAC_TANK_POOL:-tank}"; then
  _zfs_state="enabled started"
  iac_info "pool '${IAC_TANK_POOL:-tank}' imported → promoting the ZFS timers to enabled"
else
  _zfs_state="disabled"
fi

IAC_UNIT_STATE="
sovereign-gatewayd.service                ${_gatewayd_state}
sovereign-telemetry-textfile.timer        ${_telemetry_state}
sovereign-zfs-scrub.timer                 ${_zfs_state}
sovereign-backup-snapshot.timer           ${_zfs_state}
sovereign-tetragon-verify.timer           disabled
openipmi.service                          masked
whoopsie.service                          masked
sovereign-nvidia-power-limit.service      enabled
sovereign-control-exec-api.service        enabled started
"

# ─── sovereign-control-exec-api: the cockpit's control rail ──────────────────
# Shipped disabled under posture "installed-off", which for this one unit
# degrades the ENTIRE cockpit rather than just withholding a feature. Every
# panel's control rail proxies through :8130, so with it down each panel renders
# and then fills with
#     HTTP 502 {"error": "backing API on :8130 not reachable"}
# on /api/control/registry, /compat, /setup, /notifykit. The pages load, the
# health probes pass, and the panels look broken to anyone actually using them —
# which is exactly what the operator reported and what "53/60 reachable" failed
# to capture.
#
# Enabling it is safe by the unit's own design, quoted from its header:
#   "SHIPPED SAFE: DRY_RUN by default. This unit does NOT set
#    SOVEREIGN_OS_ACTION_EXEC_LIVE, so every /api/control/execute is a dry-run
#    that changes no host state."
# It is also loopback-bound and R171-hardened. LIVE mode needs a deliberate
# drop-in (live.conf: User=<operator with NOPASSWD grant>,
# SOVEREIGN_OS_ACTION_EXEC_LIVE=1, relaxed NoNewPrivileges) which is NOT created
# here and remains an explicit operator decision.

# ─── stock units with no hardware behind them ────────────────────────────────
# openipmi: no /dev/ipmi* — this board has no BMC.
# whoopsie: Ubuntu's crash-report uploader. It failed on start-limit-hit, and
#   outbound crash upload contradicts a sovereign/offline posture anyway.
#
# NOTE: nut-server / nut-monitor are deliberately ABSENT from this table.
# An earlier triage pass masked them after checking only `lsusb` and concluding
# "no UPS hardware". That was wrong — profiles.provisioning.power declares an
# apc-modbus UPS at 192.168.1.69, a NETWORK UPS that never appears on USB, and
# the host pings. Module 50 owns those two units and unmasks them.

while read -r unit want run; do
  [ -n "${unit}" ] || continue
  case "${unit}" in \#*) continue ;; esac

  # A unit that isn't installed is not a failure — report and move on, so this
  # table stays valid across profiles that don't ship every unit.
  if ! systemctl list-unit-files "${unit}" --no-legend 2>/dev/null | grep -q .; then
    skip "unit ${unit} not installed on this host"
    continue
  fi
  ensure_unit_state "${unit}" "${want}" "${run:-}"
done <<< "${IAC_UNIT_STATE}"

# ─── restart-loop guard for gatewayd ─────────────────────────────────────────
# Belt-and-braces for the day the binary IS installed and the unit unmasked:
# widen the start-limit window so 5 failures in 60s actually gives up, instead
# of the shipped unit's un-trippable 5-in-10s-at-3s-intervals configuration.
# ─── agentic tool use for the Code Console ───────────────────────────────────
# SDD-712 ships a full ReAct loop inside the daemon, gated on BOTH a per-request
# `sovereign_agentic: true` AND this env var, which defaults OFF ("the daemon
# does not autonomously execute tools unless an operator opts in"). The console
# advertises itself as a tool-using surface, so the operator opting in is the
# intent — enabled here, deliberately and visibly, rather than by an env var
# somebody sets by hand and forgets.
#
# WHAT THIS DOES AND DOES NOT GRANT. The built-in registry is:
#     upper, lower, reverse, wordcount, charcount, calc, time,
#     recall (the daemon's own learned memory), search (the RAG corpus)
# Text utilities plus two READ-ONLY retrievals. Nothing here opens a file, writes
# one, or runs a command, so "can it modify files on my system" stays NO with
# this on — that surface is /api/control/execute on :8130, which is DRY_RUN by
# default and needs its own deliberate live.conf. Turning this on does not move
# that line.
ensure_dropin sovereign-gatewayd.service 20-agentic <<'EOF'
# Managed by scripts/iac — do not edit by hand.
# Enables the SDD-712 in-daemon ReAct loop. Requests must still opt in with
# "sovereign_agentic": true; this only lifts the daemon-side gate.
[Service]
Environment=SOVEREIGN_GATEWAY_AGENTIC=1
EOF

ensure_dropin sovereign-gatewayd.service 10-startlimit <<'EOF'
# Managed by scripts/iac — do not edit by hand.
# The shipped unit cannot ever hit its own rate limit: Restart=on-failure with
# RestartSec=3 means 5 restarts span 15s, but StartLimitIntervalSec defaults to
# 10s, so the burst counter resets before the limit is reached. Widen the window
# so a genuinely broken binary stops instead of respawning forever.
[Unit]
StartLimitIntervalSec=60
StartLimitBurst=5
EOF
