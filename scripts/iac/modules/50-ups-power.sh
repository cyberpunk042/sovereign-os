#!/usr/bin/env bash
# UPS / NUT — profiles.provisioning.power
# gate: IAC_ENABLE_UPS
#
# WHY THIS MODULE EXISTS AS A CORRECTION
#   An earlier triage pass saw nut-server and nut-monitor failing at boot, ran
#   `lsusb | grep -i ups`, found nothing, and MASKED both units as "no hardware".
#   That was wrong. profiles.provisioning.power declares:
#       enabled: true   ups: apc-modbus   ups_host: 192.168.1.69   slave_id: 1
#   This is a NETWORK UPS spoken to over Modbus/TCP. It never appears on USB,
#   and 192.168.1.69 answers ICMP. The units failed because /etc/nut/* was left
#   completely unconfigured — MODE was never set — not because the UPS is absent.
#
#   This module unmasks them and writes the configuration the profile describes.
#
# NUT's apc_modbus driver ships in nut-driver >= 2.8.1 (Ubuntu 26.04 has 2.8.x).
#
# shellcheck shell=bash

_enabled="$(profile_get provisioning.power.enabled false)"
if [ "${_enabled}" != "true" ]; then
  skip "provisioning.power.enabled is not true — leaving NUT alone"
  return 0 2>/dev/null || exit 0
fi
if [ "${IAC_UPS_CONFIGURE:-1}" != 1 ]; then
  skip "IAC_UPS_CONFIGURE=0 in converge.conf — leaving NUT alone"
  return 0 2>/dev/null || exit 0
fi

_driver="$(profile_get provisioning.power.ups apc-modbus)"
_host="$(profile_get provisioning.power.ups_host)"
_slave="$(profile_get provisioning.power.slave_id 1)"
_shutdown_min="$(profile_get provisioning.power.shutdown_minutes 30)"

iac_info "driver=${_driver} host=${_host} slave_id=${_slave}"

if [ -z "${_host}" ]; then
  fail "provisioning.power.ups_host is empty — cannot configure a network UPS"
  return 0 2>/dev/null || exit 0
fi

if ! command -v upsd >/dev/null 2>&1; then
  skip "nut-server not installed — install nut-server nut-client to enable UPS monitoring"
  return 0 2>/dev/null || exit 0
fi

# NUT's driver name for APC Modbus/TCP.
# The driver directory moved: NUT <= 2.8.0 on Debian/Ubuntu used /lib/nut, but
# 2.8.4 (Ubuntu 26.04) installs to /usr/libexec/nut. Probe all known locations
# rather than assume one, or this reports a missing driver that is right there.
_nut_driver="apc_modbus"
_nut_driver_path=""
for d in /usr/libexec/nut /lib/nut /usr/lib/nut /usr/lib/ups/driver; do
  if [ -x "${d}/${_nut_driver}" ]; then _nut_driver_path="${d}/${_nut_driver}"; break; fi
done
if [ -z "${_nut_driver_path}" ]; then
  fail "NUT driver ${_nut_driver} not found (looked in /usr/libexec/nut /lib/nut /usr/lib/nut) — install: apt install nut-modbus"
  return 0 2>/dev/null || exit 0
fi
ok "NUT driver ${_nut_driver} at ${_nut_driver_path}"

# ---- ups.conf: the device definition ----
# porttype IS REQUIRED and defaults to `serial`. Without it, apc_modbus opens
# the port value as a device filesystem path and dies with
#     modbus_connect: unable to connect: No such file or directory
# then respawns every 15s forever. nut-driver-enumerator warns about exactly
# this ("key 'porttype' ... was not found"), so treat that warning as fatal.
# man 8 apc_modbus: porttype = serial|tcp|usb; for tcp, port takes
# "an IP address or a hostname with optional port like example.com:502".
_modbus_port="${IAC_UPS_MODBUS_PORT:-502}"
ensure_file /etc/nut/ups.conf 0640 root:nut <<EOF
# Managed by scripts/iac/modules/50-ups-power.sh — do not edit by hand.
# Source of truth: profiles/${IAC_PROFILE_ID}.yaml  provisioning.power
#
# NETWORK UPS (Modbus/TCP) — deliberately not a USB device. Do not "fix" a
# perceived absence by checking lsusb; this UPS lives at ${_host}.
[sain-ups]
    driver = ${_nut_driver}
    porttype = tcp
    port = ${_host}:${_modbus_port}
    slaveid = ${_slave}
    desc = "APC network UPS (profile provisioning.power)"
EOF

# ---- nut.conf: standalone means "this host runs both driver and server" ----
ensure_file /etc/nut/nut.conf 0640 root:nut <<EOF
# Managed by scripts/iac/modules/50-ups-power.sh — do not edit by hand.
# MODE was empty on this host, which is precisely why nut-server and
# nut-monitor failed at boot with "Start request repeated too quickly".
MODE=standalone
EOF

# ---- upsmon.conf: who to shut down, and when ----
# The password here is local-only (loopback upsd) and exists to satisfy NUT's
# protocol, not to protect a secret. Rotate via /etc/nut/upsd.users if exposed.
ensure_file /etc/nut/upsd.users 0640 root:nut <<'EOF'
# Managed by scripts/iac/modules/50-ups-power.sh — do not edit by hand.
[upsmon]
    password = sovereign-local
    upsmon primary
EOF

ensure_file /etc/nut/upsmon.conf 0640 root:nut <<EOF
# Managed by scripts/iac/modules/50-ups-power.sh — do not edit by hand.
# provisioning.power.shutdown_minutes = ${_shutdown_min}
MONITOR sain-ups@localhost 1 upsmon sovereign-local primary
MINSUPPLIES 1
SHUTDOWNCMD "/sbin/shutdown -h +0"
POLLFREQ 5
POLLFREQALERT 5
HOSTSYNC 15
DEADTIME 15
RBWARNTIME 43200
NOCOMMWARNTIME 300
FINALDELAY 5
EOF

ensure_file /etc/nut/upsd.conf 0640 root:nut <<'EOF'
# Managed by scripts/iac/modules/50-ups-power.sh — do not edit by hand.
# Loopback only: the operator decides any wider exposure deliberately.
LISTEN 127.0.0.1 3493
EOF

# ---- NO PRE-FLIGHT TCP PROBE. THIS IS DELIBERATE. ----
# This APC Network Management Card accepts exactly ONE concurrent Modbus/TCP
# session. Verified 2026-07-30: a single connect to 502 succeeds every time, but
# a second CONCURRENT connect is refused immediately:
#     bash: connect: Connection refused
# So a "is the UPS reachable?" probe does not observe the system — it STEALS the
# session the driver is about to need, and the driver then fails with
#     modbus_connect: unable to connect: Connection refused
# which reads like a dead UPS and is actually self-inflicted. An earlier version
# of this module did exactly that.
#
# The driver start below IS the connectivity test. It is the only one that can
# be trusted here, because it is the thing that must hold the session anyway.

# ---- driver first, dependents second ----
# nut-driver-enumerator turns each ups.conf section into nut-driver@<name> with
# Restart= on failure, so a misconfigured driver respawns forever — the same
# trap sovereign-gatewayd fell into (782 restarts). Converge writes the config,
# so converge owns the consequence: prove the driver holds, or leave the machine
# quiet and diagnosable.
#
# Ordering matters for idempotency too. Starting upsd/upsmon BEFORE the driver is
# proven means every failed run stops them and every next run restarts them —
# a permanent 2-change oscillation that can never report "0 changed".
_inst="nut-driver@sain-ups.service"
_driver_up=0

if [ "${IAC_DRY_RUN}" = 1 ]; then
  iac_info "would start ${_inst}, then upsd/upsmon only if it holds"
  _driver_up=1
elif ! systemctl list-unit-files 'nut-driver@.service' --no-legend >/dev/null 2>&1; then
  skip "nut-driver@.service template not installed"
else
  # NEVER BOUNCE A HEALTHY DRIVER.
  # This used to `systemctl restart` unconditionally on every converge run. On a
  # card that accepts ONE Modbus/TCP session that is actively harmful: the stop
  # closes the session, the immediate start reconnects before the card has freed
  # it, and the card answers "Connection refused" — so a working UPS was taken
  # down by a converge run that changed nothing. This module documented the
  # single-session constraint and then violated it.
  #
  # Verified after the fact: with the driver stopped, 502 accepts immediately.
  # The card was never the problem.
  if systemctl is-active --quiet "${_inst}" 2>/dev/null; then
    _driver_up=1
  else
    # nut-driver-enumerator materialises the instance from ups.conf; without it
    # the instance may not exist yet on a first run.
    systemctl start nut-driver-enumerator.service >/dev/null 2>&1 || true
    systemctl start "${_inst}" >/dev/null 2>&1 || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      systemctl is-active --quiet "${_inst}" 2>/dev/null && { _driver_up=1; break; }
      sleep 1
    done
  fi

  if [ "${_driver_up}" = 1 ]; then
    ok "driver ${_inst} connected to ${_host}:${_modbus_port}"
  else
    systemctl stop "${_inst}" >/dev/null 2>&1 || true
    systemctl stop nut-monitor.service nut-server.service >/dev/null 2>&1 || true
    _why="$(journalctl -u "${_inst}" -n 20 --no-pager 2>/dev/null \
            | grep -oE 'modbus_connect: unable to connect: .*' | tail -1)"
    fail "driver will not stay up${_why:+ — ${_why}}"
    iac_info "the card answers a single TCP session only; check the NMC has Modbus/TCP ENABLED"
    iac_info "and that slaveid=${_slave} matches. Diagnose: journalctl -u ${_inst}"
  fi
fi

# ---- upsd / upsmon: only meaningful once the driver holds the session ----
for u in nut-server.service nut-monitor.service; do
  if ! systemctl list-unit-files "${u}" --no-legend 2>/dev/null | grep -q .; then
    skip "unit ${u} not installed"
    continue
  fi
  if [ "${_driver_up}" = 1 ]; then
    ensure_unit_state "${u}" enabled started
  else
    # Enabled (so a good boot brings them up with a working driver) but not
    # started now — starting upsd against a dead driver just adds noise.
    ensure_unit_state "${u}" enabled
    skip "unit ${u} not started — driver is down"
  fi
done

# ---- the D-xx UPS cockpit panel ----
# sovereign-ups-api.service ships disabled under provisioning.posture
# "installed-off", which was right while NUT was unconfigured: the panel reads
# live data via scripts/hardware/power-status.py -> upsc, and explicitly checks
# that nut-server is active. With a real UPS answering (Smart-UPS 2200, OL,
# ~250 min runtime) the panel now has something to show, so the dashboards hub
# stops listing it as unreachable.
#
# Gated on the SAME _driver_up as upsd/upsmon above: enabling a panel whose only
# data source is down would just move the failure one layer up. It binds
# 127.0.0.1:8128 by its own unit default — deliberately not widened here.
_ups_api=sovereign-ups-api.service
if ! systemctl list-unit-files "${_ups_api}" --no-legend 2>/dev/null | grep -q .; then
  skip "unit ${_ups_api} not installed"
elif [ "${IAC_UPS_PANEL:-1}" != 1 ]; then
  skip "${_ups_api} left alone (IAC_UPS_PANEL=0)"
elif [ "${_driver_up}" = 1 ]; then
  ensure_unit_state "${_ups_api}" enabled started
else
  ensure_unit_state "${_ups_api}" enabled
  skip "unit ${_ups_api} not started — UPS driver is down, the panel would have no data"
fi
