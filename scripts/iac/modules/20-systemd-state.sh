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
# sovereign-zfs-scrub.timer / sovereign-backup-snapshot.timer: there is no ZFS
#   pool on this machine (both NVMe devices are vfat/ext4/swap) and, on the
#   custom 6.12.0 kernel, there was no zfs module either. The stock 7.0.0 kernel
#   restores the module but the pool still does not exist. Re-enable after
#   creating the pool these expect (tank/context).
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

IAC_UNIT_STATE="
sovereign-gatewayd.service                ${_gatewayd_state}
sovereign-telemetry-textfile.timer        ${_telemetry_state}
sovereign-zfs-scrub.timer                 disabled
sovereign-backup-snapshot.timer           disabled
sovereign-tetragon-verify.timer           disabled
openipmi.service                          masked
whoopsie.service                          masked
sovereign-nvidia-power-limit.service      enabled
"

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
