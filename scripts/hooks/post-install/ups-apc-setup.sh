#!/usr/bin/env bash
# scripts/hooks/post-install/ups-apc-setup.sh — APC Smart-UPS integration via NUT.
#
# Operator hardware (2026-07-08): APC Smart-UPS 2200VA 1980W SMT2200C — a
# *SmartConnect* model. Its rear panel exposes FOUR independent management
# interfaces: a dedicated SmartConnect Ethernet (RJ45) port, a DB-9 / RJ50
# serial signalling port, a native USB Type-B port, and a SmartSlot. The two
# transports we can drive without a Network Management Card:
#
#   • Modbus TCP  — the embedded SmartConnect Ethernet port serves Modbus/TCP on
#                   the fixed port 502 once "Modbus" + "TCP Protocols" are enabled
#                   in the UPS LCD (Advanced menu) AND the Ethernet jack is cabled
#                   to the LAN. Set LCD ▸ TCP Settings ▸ Master IP = this host.
#   • Modbus RTU  — over the DSD TECH SH-RJ50A USB→RJ50 serial cable, which
#     / serial      enumerates as /dev/ttyUSB<N> (ftdi/ch341/cp210x/pl2303, all in
#                   the znver5 kernel) and plugs into the UPS *serial* jack.
#   • native USB  — a plain USB-A→B cable to the UPS's USB port → a USB HID power
#                   device (vendor 051d), driven by NUT's usbhid-ups.
#
# The correct client for a modern SmartConnect Smart-UPS is **NUT** (Network UPS
# Tools) with the **apc_modbus** driver (NUT ≥ 2.8.1), which speaks Modbus over
# BOTH TCP and serial. (apcupsd's Modbus support is serial-only — it cannot do
# the TCP half at all — which is why this integration is NUT, not apcupsd.)
#
# This first-boot hook (real hardware only — ConditionVirtualization=no on its
# unit) does the "find whatever is needed" work, AUTO-DETECTING in this order:
#   1. Modbus TCP  — SOVEREIGN_OS_UPS_HOST if set, else scan the LAN for an APC
#                    answering on :502; configure apc_modbus porttype=tcp.
#   2. Serial      — /dev/ttyUSB*; configure apc_modbus porttype=serial.
#   3. Native USB  — lsusb 051d; configure usbhid-ups.
#   For each candidate it writes the NUT config, (re)starts the stack, and
#   verifies real comms with `upsc`. First transport that talks wins.
#   4. Leave NUT (upsd + the driver + upsmon) enabled + running so power-status /
#      the graceful-shutdown guard (soft shutdown at runtime < 30 min) have a
#      live data source, and upsmon is a conservative NUT-native backstop.
#
# Idempotent + non-fatal + re-runnable: re-running re-detects; a missing UPS logs
# a warning and exits 0 (the box still boots — it just has no UPS monitoring yet;
# re-run this hook once the UPS is reachable).
set -uo pipefail
__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh" 2>/dev/null || {
  log_info() { echo "INFO  [ups-apc-setup] $*"; }
  log_warn() { echo "WARN  [ups-apc-setup] $*" >&2; }
  log_error() { echo "ERROR [ups-apc-setup] $*" >&2; }
}
# SDD-016 Layer B observability — emit_metric degrades to a no-op when the
# textfile collector isn't active, so it's always safe to call.
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh" 2>/dev/null || emit_metric() { :; }

NUT_DIR="${SOVEREIGN_OS_NUT_DIR:-/etc/nut}"
UPS_NAME="${SOVEREIGN_OS_UPS_NAME:-sain01ups}"
SLAVEID="${SOVEREIGN_OS_UPS_SLAVEID:-1}"
TCP_PORT="${SOVEREIGN_OS_UPS_TCP_PORT:-502}"
LISTEN_PORT="${SOVEREIGN_OS_NUT_LISTEN_PORT:-3493}"

# ── preconditions ──────────────────────────────────────────────────────────
if ! command -v upsc >/dev/null 2>&1 || ! command -v upsdrvctl >/dev/null 2>&1; then
  log_warn "NUT not installed (no upsc/upsdrvctl) — skipping UPS setup"
  log_warn "  add 'nut-server' + 'nut-client' to the profile packages"
  exit 0
fi
if [ ! -d "${NUT_DIR}" ]; then
  log_warn "no ${NUT_DIR} — is nut-server installed? skipping"
  exit 0
fi

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — detection order: (1) Modbus TCP :${TCP_PORT} (SOVEREIGN_OS_UPS_HOST or LAN scan)"
  log_info "  (2) serial /dev/ttyUSB* (apc_modbus)  (3) native USB-HID 051d (usbhid-ups)"
  log_info "  would write ${NUT_DIR}/{nut.conf,ups.conf,upsd.conf,upsd.users,upsmon.conf} + verify via upsc"
  exit 0
fi

DRIVER_DIR=""
for d in "${SOVEREIGN_OS_NUT_DRIVER_DIR:-}" /lib/nut /usr/lib/nut /usr/libexec/nut; do
  [ -n "${d}" ] && [ -x "${d}/apc_modbus" ] && DRIVER_DIR="${d}" && break
done
if [ -z "${DRIVER_DIR}" ]; then
  log_warn "apc_modbus driver not found under /lib/nut|/usr/lib/nut (NUT ${NUT_DIR} present but driver missing)"
  log_warn "  the SmartConnect UPS speaks Modbus — install a NUT (>=2.8.1) that ships apc_modbus"
  # usbhid-ups may still exist for the native-USB fallback; don't hard-fail
fi

# generate a stable-per-boot monitor password (NUT files are root:nut 0640)
_gen_pass() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex 16
  else head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'; fi
}
MON_PASS="$(_gen_pass)"
[ -n "${MON_PASS}" ] || MON_PASS="sovereign-ups"   # never empty

# ── NUT base config (daemons: driver → upsd → upsmon; standalone, loopback) ──
_write_base_conf() {
  # nut.conf — run mode
  printf 'MODE=standalone\n' > "${NUT_DIR}/nut.conf"

  # upsd.conf — listen on loopback only (operator exposes deliberately)
  cat > "${NUT_DIR}/upsd.conf" <<EOF
# sovereign-os — generated by ups-apc-setup
LISTEN 127.0.0.1 ${LISTEN_PORT}
LISTEN ::1 ${LISTEN_PORT}
EOF

  # upsd.users — a monitor account for upsmon (primary = this host owns shutdown)
  cat > "${NUT_DIR}/upsd.users" <<EOF
# sovereign-os — generated by ups-apc-setup
[upsmon]
    password = ${MON_PASS}
    upsmon primary
EOF

  # upsmon.conf — NUT-native conservative backstop. The sovereign
  # power-shutdown-guard fires the GRACEFUL shutdown first at runtime < 30 min;
  # upsmon only acts on the UPS's own LOW-BATTERY (LB) flag as a last resort.
  cat > "${NUT_DIR}/upsmon.conf" <<EOF
# sovereign-os — generated by ups-apc-setup
MONITOR ${UPS_NAME}@localhost 1 upsmon ${MON_PASS} primary
MINSUPPLIES 1
POLLFREQ 5
POLLFREQALERT 5
DEADTIME 15
SHUTDOWNCMD "/sbin/shutdown -h +0 'UPS low battery — NUT upsmon backstop shutdown'"
EOF

  # lock down the two files that carry the password
  chmod 640 "${NUT_DIR}/upsd.users" "${NUT_DIR}/upsmon.conf" 2>/dev/null || true
  chgrp nut "${NUT_DIR}/upsd.users" "${NUT_DIR}/upsmon.conf" 2>/dev/null || true
}

# ── ups.conf writer — one stanza per candidate transport ────────────────────
_write_ups_conf() {   # $1=driver $2=key=val ...  (extra driver lines)
  local drv="$1"; shift
  {
    printf '# sovereign-os — generated by ups-apc-setup (auto-detected transport)\n'
    printf 'maxretry = 3\n'
    printf 'pollinterval = 5\n\n'
    printf '[%s]\n' "${UPS_NAME}"
    printf '    driver = %s\n' "${drv}"
    local kv
    for kv in "$@"; do printf '    %s\n' "${kv}"; done
    printf '    desc = "APC Smart-UPS SMT2200C (SAIN-01)"\n'
  } > "${NUT_DIR}/ups.conf"
}

# ── (re)start the NUT stack and confirm the driver talks ───────────────────
_nut_apply() {
  # Debian: nut-driver-enumerator reads ups.conf → creates nut-driver@<name>.
  systemctl restart nut-driver-enumerator.service 2>/dev/null || true
  systemctl restart nut-server.service            2>/dev/null || true
  systemctl restart nut-monitor.service           2>/dev/null || true
  # Belt-and-suspenders for environments where the enumerator/instances lag:
  # start the driver directly, then bounce upsd so it re-reads the socket.
  upsdrvctl stop  >/dev/null 2>&1 || true
  upsdrvctl start >/dev/null 2>&1 || true
  systemctl restart nut-server.service 2>/dev/null || true
  sleep 3
}

_ups_talks() {   # 0 if upsd reports a live ups.status for our device
  local st; st="$(upsc "${UPS_NAME}@localhost" ups.status 2>/dev/null)"
  [ -n "${st}" ]
}

_ups_is_apc() {  # 0 if the reported vendor/model looks like an APC (avoids
                 # latching onto some *other* Modbus device on :502)
  local mfr model
  mfr="$(upsc "${UPS_NAME}@localhost" device.mfr 2>/dev/null || true)"
  [ -n "${mfr}" ] || mfr="$(upsc "${UPS_NAME}@localhost" ups.mfr 2>/dev/null || true)"
  model="$(upsc "${UPS_NAME}@localhost" device.model 2>/dev/null || true)"
  [ -n "${model}" ] || model="$(upsc "${UPS_NAME}@localhost" ups.model 2>/dev/null || true)"
  echo "${mfr} ${model}" | grep -qiE 'apc|american power|smart-?ups|schneider'
}

_report_success() {   # $1=transport-label
  systemctl enable nut-server.service nut-monitor.service nut-driver-enumerator.service >/dev/null 2>&1 || true
  local model charge runtime
  model="$(upsc "${UPS_NAME}@localhost" device.model 2>/dev/null || upsc "${UPS_NAME}@localhost" ups.model 2>/dev/null || echo '?')"
  charge="$(upsc "${UPS_NAME}@localhost" battery.charge 2>/dev/null || echo '?')"
  runtime="$(upsc "${UPS_NAME}@localhost" battery.runtime 2>/dev/null || echo '')"
  [ -n "${runtime}" ] && runtime="$(( runtime / 60 )) min" || runtime="?"
  log_info "UPS ONLINE via ${1} — model='${model}' battery=${charge}% runtime≈${runtime}"
  log_info "  soft shutdown fires at runtime < 30 min (sovereign-power-shutdown-guard);"
  log_info "  upsmon is the NUT-native low-battery backstop. Check: 'upsc ${UPS_NAME}@localhost'"
  # first word of the label is the transport kind (tcp/serial/native) for a clean series
  local kind="${1%% *}"
  emit_metric sovereign_os_post_install_ups_setup_total 1 \
    "result=\"success\",transport=\"$(echo "${kind}" | tr 'A-Z' 'a-z')\""
}

# ── 0. idempotent short-circuit ────────────────────────────────────────────
# If NUT is ALREADY talking to an APC (a prior run configured it), leave the
# working setup entirely untouched. Re-scanning would be actively harmful: an
# APC SmartConnect serves ONE Modbus-TCP session at a time, held by the running
# driver — so a fresh :502 probe is refused, we'd wrongly conclude "no UPS", and
# tear down a healthy monitor. This makes re-runs safe + fast.
if _ups_talks && _ups_is_apc; then
  drv="$(upsc "${UPS_NAME}@localhost" driver.name 2>/dev/null || echo apc_modbus)"
  log_info "NUT already talking to an APC (${drv}) — leaving it untouched (idempotent)"
  _report_success "existing (${drv})"
  exit 0
fi

_write_base_conf
OK_LABEL=""

# ── 0b. reuse a known-good existing stanza (restart NUT, NO re-scan) ────────
# If a prior run already wrote a working apc_modbus/usbhid device stanza, just
# bring NUT back up with it — do NOT re-scan. An APC SmartConnect serves ONE
# Modbus-TCP session at a time and holds it in cleanup for several seconds after
# a driver disconnects, so a scan right after cycling the driver false-negatives
# (the port looks closed). Restarting the driver to the SAME known device is the
# legitimate single session and sidesteps the scan entirely — this is what makes
# re-runs converge instead of tearing themselves down.
if grep -qE '^[[:space:]]*driver[[:space:]]*=[[:space:]]*(apc_modbus|usbhid-ups)' "${NUT_DIR}/ups.conf" 2>/dev/null; then
  existing="$(grep -E '^[[:space:]]*port[[:space:]]*=' "${NUT_DIR}/ups.conf" 2>/dev/null | head -1 | sed -E 's/^[[:space:]]*port[[:space:]]*=[[:space:]]*//')"
  log_info "existing NUT device stanza (port=${existing:-auto}) — restarting NUT with it (no re-scan)"
  _nut_apply
  if _ups_talks && _ups_is_apc; then OK_LABEL="existing config (${existing:-auto})"; fi
fi

# Free any stale driver session ONLY if we still have to scan. A driver left
# holding the UPS's single Modbus session would make the :502 scan see the port
# as closed; the reuse path above already covers the common re-run case.
if [ -z "${OK_LABEL}" ]; then
  upsdrvctl stop >/dev/null 2>&1 || true
  systemctl stop "nut-driver@${UPS_NAME}.service" nut-driver-enumerator.service >/dev/null 2>&1 || true
  sleep 3     # let the UPS release its single Modbus session before probing
fi

# ── 1. Modbus TCP over the SmartConnect Ethernet port (:502) ───────────────
# Preferred for a tower UPS that stays put. Requires the SmartConnect RJ45 jack
# cabled to the LAN + LCD: Modbus ▸ Enable, TCP Protocols ▸ Enable, and TCP
# Settings ▸ Master IP = this host.
_tcp_candidates() {
  # pinned host first (fast + deterministic); if it doesn't answer we fall
  # through to a LAN scan, so a changed DHCP lease still self-heals. When the
  # pinned host works the caller breaks the loop → the scan below never runs.
  [ -n "${SOVEREIGN_OS_UPS_HOST:-}" ] && echo "${SOVEREIGN_OS_UPS_HOST}"
  # scan every IPv4 /24 we're on for an open :502 (bounded, parallel, python3
  # is always present). Emits candidate IPs, most-likely-first is fine.
  local nets; nets="$(ip -o -4 addr show scope global 2>/dev/null | awk '{print $4}')"
  [ -n "${nets}" ] || return 0
  UPS_TCP_PORT="${TCP_PORT}" NUT_SCAN_NETS="${nets}" SKIP_HOST="${SOVEREIGN_OS_UPS_HOST:-}" python3 - <<'PY'
import ipaddress, os, socket, concurrent.futures as cf
port=int(os.environ.get("UPS_TCP_PORT","502"))
skip=os.environ.get("SKIP_HOST","")
hosts=[]
for cidr in os.environ.get("NUT_SCAN_NETS","").split():
    try:
        net=ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        continue
    if net.num_addresses>4096:      # never sweep something enormous
        continue
    for ip in net.hosts():
        hosts.append(str(ip))
def probe(ip):
    try:
        s=socket.socket(); s.settimeout(0.5)
        rc=s.connect_ex((ip,port)); s.close()
        return ip if rc==0 else None
    except Exception:
        return None
seen=[]
with cf.ThreadPoolExecutor(max_workers=256) as ex:
    for r in ex.map(probe, hosts):
        if r: seen.append(r)
for ip in seen:
    if ip != skip:           # already tried first as the pinned host
        print(ip)
PY
}

if [ -z "${OK_LABEL}" ] && [ -n "${DRIVER_DIR}" ]; then
  log_info "probing Modbus TCP (:${TCP_PORT}) — SmartConnect embedded port ..."
  while IFS= read -r host; do
    [ -n "${host}" ] || continue
    log_info "  trying apc_modbus porttype=tcp ${host}:${TCP_PORT} slaveid=${SLAVEID}"
    _write_ups_conf apc_modbus "porttype = tcp" "port = ${host}:${TCP_PORT}" "slaveid = ${SLAVEID}"
    _nut_apply
    if _ups_talks && _ups_is_apc; then OK_LABEL="Modbus TCP (${host}:${TCP_PORT})"; break; fi
  done < <(_tcp_candidates)
fi

# ── 2. Serial / Modbus RTU over the DSD TECH USB→RJ50 cable ────────────────
if [ -z "${OK_LABEL}" ] && [ -n "${DRIVER_DIR}" ]; then
  mapfile -t TTYS < <(ls /dev/ttyUSB* 2>/dev/null)
  # explicit override is always a candidate, even if the glob matched nothing
  SERIAL_CANDS=()
  [ -n "${SOVEREIGN_OS_UPS_DEVICE:-}" ] && SERIAL_CANDS+=("${SOVEREIGN_OS_UPS_DEVICE}")
  [ "${#TTYS[@]}" -gt 0 ] && SERIAL_CANDS+=("${TTYS[@]}")
  if [ "${#SERIAL_CANDS[@]}" -gt 0 ]; then
    for dev in "${SERIAL_CANDS[@]}"; do
      [ -n "${dev}" ] && [ -e "${dev}" ] || continue
      log_info "  trying apc_modbus porttype=serial ${dev} slaveid=${SLAVEID}"
      _write_ups_conf apc_modbus "porttype = serial" "port = ${dev}" "slaveid = ${SLAVEID}"
      _nut_apply
      if _ups_talks && _ups_is_apc; then OK_LABEL="Modbus serial (${dev})"; break; fi
    done
  else
    log_info "no /dev/ttyUSB* — serial cable not present (or the RJ50 plug is in the"
    log_info "  SmartConnect Ethernet jack by mistake; it belongs in the SERIAL jack)"
  fi
fi

# ── 3. Native USB-HID power device (051d) via usbhid-ups ───────────────────
if [ -z "${OK_LABEL}" ] && [ -x "${DRIVER_DIR:-/lib/nut}/usbhid-ups" ]; then
  if lsusb 2>/dev/null | grep -qiE '051d:|american power|APC .*UPS'; then
    log_info "  trying usbhid-ups (native APC USB HID power device, 051d)"
    _write_ups_conf usbhid-ups "port = auto"
    _nut_apply
    if _ups_talks; then OK_LABEL="native USB-HID (usbhid-ups)"; fi
  fi
fi

# ── 4. verdict ─────────────────────────────────────────────────────────────
if [ -n "${OK_LABEL}" ]; then
  _report_success "${OK_LABEL}"
  exit 0
fi

log_warn "no APC UPS reached over Modbus TCP (:${TCP_PORT}), serial (/dev/ttyUSB*), or native USB (051d)."
log_warn "  TCP path: cable the UPS SmartConnect Ethernet RJ45 to the LAN; LCD ▸ Advanced ▸"
log_warn "            Modbus ▸ Enable, TCP Protocols ▸ Enable, TCP Settings ▸ Master IP = this host."
log_warn "  Serial path: DSD TECH RJ50 plug in the UPS SERIAL jack (not the Ethernet jack)."
log_warn "  Then re-run this hook once the UPS is reachable: ${BASH_SOURCE[0]}"
emit_metric sovereign_os_post_install_ups_setup_total 1 'result="unreached",transport="none"'
# leave upsd/upsmon disabled so they don't flap without a device
systemctl disable --now nut-monitor.service nut-server.service >/dev/null 2>&1 || true
exit 0
