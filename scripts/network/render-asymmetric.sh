#!/usr/bin/env bash
# scripts/network/render-asymmetric.sh
#
# Master spec § 8 (Network Infrastructure & Perimeter Segregation):
#
#   "The ProArt X870E-Creator features asymmetric networking ports: a
#    Marvell 10GbE adapter and an Intel 2.5GbE adapter. To align with
#    a Zero-Trust OPNsense / SD-WAN core architecture, network traffic
#    is physically segregated at the hardware boundary."
#
# Renders the verbatim master spec § 8.1 /etc/network/interfaces +
# equivalent systemd-networkd units from a profile's hardware.network
# block. Reads address/gateway/MTU directly from the profile YAML so
# no values are hard-coded here — the profile is the source of truth.
#
# Distinguished from scripts/hooks/post-install/network-vlan-config.sh:
#   - vlan-config.sh: generic DHCP-based VLAN renderer (any profile)
#   - render-asymmetric.sh: master spec § 8.1 OPINIONATED renderer for
#     profiles whose hardware.network entries carry address+gateway
#     (currently only sain-01).
#
# CLI:
#   render-asymmetric.sh [--profile <id>]
#     Renders to ${SOVEREIGN_OS_NET_OUT_DIR}
#   render-asymmetric.sh --legacy-interfaces
#     Prints the /etc/network/interfaces master-spec-§-8.1-shaped block
#
# Env vars:
#   SOVEREIGN_OS_PROFILE             active profile id (default: sain-01)
#   SOVEREIGN_OS_NET_OUT_DIR         output dir (default: /etc/systemd/network)
#   SOVEREIGN_OS_LEGACY_INTERFACES   path for /etc/network/interfaces
#                                    (default: /etc/network/interfaces)
#   SOVEREIGN_OS_DRY_RUN             print intent, do not write
#
# Layer B metrics:
#   sovereign_os_network_asymmetric_render_total{profile,result}
#   sovereign_os_network_asymmetric_render_last_timestamp

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/build/lib/common.sh" 2>/dev/null || true
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/build/lib/observability.sh" 2>/dev/null || true

type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [network/render-asymmetric] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [network/render-asymmetric] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [network/render-asymmetric] $*" >&2; }
type emit_metric >/dev/null 2>&1 || emit_metric() { :; }

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
: "${SOVEREIGN_OS_NET_OUT_DIR:=/etc/systemd/network}"
: "${SOVEREIGN_OS_LEGACY_INTERFACES:=/etc/network/interfaces}"

PROFILE_FILE="${__REPO_ROOT}/../profiles/${SOVEREIGN_OS_PROFILE}.yaml"
[ -f "${PROFILE_FILE}" ] || PROFILE_FILE="${__REPO_ROOT}/profiles/${SOVEREIGN_OS_PROFILE}.yaml"

MODE="systemd-networkd"
if [ "${1:-}" = "--legacy-interfaces" ]; then
  MODE="legacy-interfaces"
elif [ "${1:-}" = "--profile" ]; then
  SOVEREIGN_OS_PROFILE="$2"
  PROFILE_FILE="${__REPO_ROOT}/../profiles/${SOVEREIGN_OS_PROFILE}.yaml"
  [ -f "${PROFILE_FILE}" ] || PROFILE_FILE="${__REPO_ROOT}/profiles/${SOVEREIGN_OS_PROFILE}.yaml"
fi

if [ ! -f "${PROFILE_FILE}" ]; then
  log_error "profile yaml not found: ${PROFILE_FILE}"
  exit 1
fi

log_info "==== sovereign-os asymmetric network renderer ===="
log_info "  master spec § 8 (Zero-Trust perimeter segregation)"
log_info "  profile:     ${SOVEREIGN_OS_PROFILE} (${PROFILE_FILE})"
log_info "  out dir:     ${SOVEREIGN_OS_NET_OUT_DIR}"
log_info "  mode:        ${MODE}"

# ---------- read network entries from profile ----------
network_entries="$(python3 - "${PROFILE_FILE}" <<'PYEOF'
import sys, yaml
with open(sys.argv[1]) as f:
    doc = yaml.safe_load(f)
nics = (doc.get("hardware") or {}).get("network") or []
for n in nics:
    role = n.get("role", "?")
    vlan = n.get("vlan", "")
    mtu = n.get("mtu", "")
    addr = n.get("address", "")
    gw = n.get("gateway", "")
    dns = ",".join(n.get("dns_nameservers", []) or [])
    iface = n.get("iface_hint", "")
    vendor = n.get("vendor", "")
    model = n.get("model", "")
    default_gw = "yes" if n.get("default_gateway") else "no"
    print(f"{role}|{vlan}|{mtu}|{addr}|{gw}|{dns}|{iface}|{vendor}|{model}|{default_gw}")
PYEOF
)"

if [ -z "${network_entries}" ]; then
  log_warn "no hardware.network entries in profile — nothing to render"
  emit_metric sovereign_os_network_asymmetric_render_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"skip-empty\""
  exit 0
fi

# Check that at least one entry has address+gateway (the asymmetric
# path is opinionated — if no profile carries the verbatim § 8.1 values
# we exit gracefully)
has_addr=0
while IFS= read -r line; do
  [ -z "${line}" ] && continue
  addr="$(echo "${line}" | cut -d'|' -f4)"
  [ -n "${addr}" ] && has_addr=1
done <<< "${network_entries}"

if [ "${has_addr}" -eq 0 ]; then
  log_warn "profile has no hardware.network[].address — generic DHCP renderer applies"
  log_warn "  use scripts/hooks/post-install/network-vlan-config.sh instead"
  emit_metric sovereign_os_network_asymmetric_render_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"skip-no-address\""
  exit 0
fi

# ---------- render legacy /etc/network/interfaces (master spec § 8.1) ----------
render_legacy() {
  echo "# /etc/network/interfaces — master spec § 8.1 (Zero-Trust)"
  echo "# Profile: ${SOVEREIGN_OS_PROFILE}"
  echo "# Generated by scripts/network/render-asymmetric.sh"
  echo
  while IFS= read -r line; do
    [ -z "${line}" ] && continue
    IFS='|' read -r role vlan mtu addr gw dns iface vendor model default_gw <<< "${line}"
    if [ "${role}" = "mgmt" ]; then
      desc="${vendor^} ${model^^} - Dedicated Secure Management Interface"
    elif [ "${role}" = "data" ]; then
      desc="${vendor^} ${model^^} - High-Speed Isolated Computation Interface (No Default Gateway)"
    else
      desc="${vendor} ${model}"
    fi
    [ -n "${iface}" ] && nic="${iface}" || nic="iface-${role}"
    echo "# ${desc}"
    echo "auto ${nic}"
    echo "iface ${nic} inet static"
    [ -n "${addr}" ] && echo "    address ${addr}"
    [ -n "${gw}" ] && echo "    gateway ${gw}"
    [ -n "${dns}" ] && echo "    dns-nameservers ${dns//,/ }"
    [ -n "${mtu}" ] && echo "    up ip link set dev ${nic} mtu ${mtu} # Enable Jumbo Frames for local 10G NAS ingestion"
    echo
  done <<< "${network_entries}"
}

# ---------- render systemd-networkd files ----------
render_networkd() {
  local out_dir="$1"
  mkdir -p "${out_dir}"
  local idx=0
  while IFS= read -r line; do
    [ -z "${line}" ] && continue
    IFS='|' read -r role vlan mtu addr gw dns iface vendor model default_gw <<< "${line}"
    idx=$((idx + 1))
    [ -n "${iface}" ] && nic="${iface}" || nic="iface-${role}"

    local fname="${out_dir}/${idx}0-sovereign-${role}.network"
    {
      echo "# master spec § 8.1 — ${vendor^} ${model^^} (${role})"
      echo "# Generated by scripts/network/render-asymmetric.sh"
      echo
      echo "[Match]"
      echo "Name=${nic}"
      echo
      echo "[Network]"
      [ -n "${addr}" ] && echo "Address=${addr}"
      [ -n "${gw}" ] && echo "Gateway=${gw}"
      [ -n "${dns}" ] && {
        IFS=',' read -ra dns_arr <<< "${dns}"
        for d in "${dns_arr[@]}"; do
          echo "DNS=${d}"
        done
      }
      [ "${default_gw}" = "no" ] && echo "DefaultRouteOnDevice=no"
      [ -n "${mtu}" ] && {
        echo
        echo "[Link]"
        echo "MTUBytes=${mtu}"
      }
    } > "${fname}"
    log_info "  wrote ${fname}"
  done <<< "${network_entries}"
}

# ---------- dispatch ----------
if [ "${MODE}" = "legacy-interfaces" ]; then
  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    log_info "DRY-RUN: would print /etc/network/interfaces block to stdout"
    render_legacy
  else
    render_legacy
  fi
  emit_metric sovereign_os_network_asymmetric_render_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"legacy-rendered\""
  exit 0
fi

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN: would write systemd-networkd units to ${SOVEREIGN_OS_NET_OUT_DIR}"
  while IFS= read -r line; do
    [ -z "${line}" ] && continue
    IFS='|' read -r role _ _ addr _ _ iface _ _ _ <<< "${line}"
    log_info "  would write: ${SOVEREIGN_OS_NET_OUT_DIR}/N0-sovereign-${role}.network (iface=${iface:-?}, addr=${addr})"
  done <<< "${network_entries}"
  emit_metric sovereign_os_network_asymmetric_render_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"dry-run\""
  exit 0
fi

render_networkd "${SOVEREIGN_OS_NET_OUT_DIR}"
emit_metric sovereign_os_network_asymmetric_render_total 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"success\""
emit_metric sovereign_os_network_asymmetric_render_last_timestamp \
  "$(date +%s)" "profile=\"${SOVEREIGN_OS_PROFILE}\""

log_info "✓ asymmetric network config rendered (master spec § 8.1 materialized)"
log_info "  reload via: systemctl restart systemd-networkd"
