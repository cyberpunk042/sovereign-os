# shellcheck shell=bash
# scripts/osctl.d/status.sh — sovereign-osctl `status` verb module (F-2026-025).
# Sourced by the main sovereign-osctl dispatcher; do not run directly.
#
# system status summary (default) + `--json` machine shape.
# Extracted verbatim from the sovereign-osctl monolith — behavior is
# byte-identical (same shell, same globals: __REPO_ROOT / PYTHON3 /
# log_* / common.sh helpers are all resident before dispatch sources this).

cmd_status() {
  # --json mode: machine-readable status for fleet aggregation
  if [ "${1:-}" = "--json" ]; then
    local profile="${SOVEREIGN_OS_PROFILE:-unknown}"
    local active_whitelabel="default"
    [ -r /etc/sovereign-os/active-whitelabel ] && \
      active_whitelabel="$(cat /etc/sovereign-os/active-whitelabel)"
    local zfs_state="absent"
    if command -v zpool >/dev/null 2>&1 && zpool list tank >/dev/null 2>&1; then
      if zpool status tank | grep -q "state: ONLINE"; then zfs_state="online"; else zfs_state="degraded"; fi
    fi
    local tetragon_state="not-installed"
    if command -v tetragon >/dev/null 2>&1; then
      systemctl is-active --quiet tetragon && tetragon_state="active" || tetragon_state="inactive"
    fi
    local kernel; kernel="$(uname -r)"
    local os_pretty="unknown"
    [ -r /etc/os-release ] && os_pretty="$(grep PRETTY_NAME /etc/os-release | cut -d= -f2- | tr -d '"')"
    local first_boot_done="false"
    [ -r /var/lib/sovereign-os/first-boot-complete ] && first_boot_done="true"
    cat <<EOF
{
  "profile": "${profile}",
  "active_whitelabel": "${active_whitelabel}",
  "kernel_release": "${kernel}",
  "os_pretty_name": "${os_pretty}",
  "zfs_pool_state": "${zfs_state}",
  "tetragon_state": "${tetragon_state}",
  "first_boot_complete": ${first_boot_done},
  "timestamp": $(date +%s)
}
EOF
    return 0
  fi

  echo "sovereign-os status"
  echo "==================="
  echo
  echo "Profile:    ${SOVEREIGN_OS_PROFILE}"
  if [ -r /etc/os-release ]; then
    echo "OS release: $(grep PRETTY_NAME /etc/os-release | cut -d= -f2-)"
  fi
  echo "Kernel:     $(uname -r)"
  echo "Uptime:     $(uptime -p 2>/dev/null || uptime)"
  echo

  # ZFS pool
  if command -v zpool >/dev/null 2>&1; then
    echo "[ZFS pool 'tank']"
    if zpool list tank >/dev/null 2>&1; then
      zpool list tank
      echo
      zfs list -r tank -o name,used,available,refer,mountpoint 2>/dev/null
    else
      echo "  pool 'tank' not present"
    fi
    echo
  fi

  # Tetragon
  if command -v tetragon >/dev/null 2>&1; then
    echo "[Tetragon]"
    if systemctl is-active --quiet tetragon; then
      echo "  status: active"
    else
      echo "  status: INACTIVE"
    fi
    echo
  fi

  # GPUs (host-visible)
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "[NVIDIA GPUs (host-visible)]"
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | sed 's/^/  /' || echo "  nvidia-smi present but no GPUs visible (VFIO bound?)"
    echo
  fi

  # Network
  echo "[Network]"
  ip -brief addr show | grep -v '^lo' | sed 's/^/  /'
  echo

  # Whitelabel
  echo "[Whitelabel]"
  if [ -r /etc/sovereign-os/active-whitelabel ]; then
    echo "  active: $(cat /etc/sovereign-os/active-whitelabel)"
  else
    echo "  active: default (no /etc/sovereign-os/active-whitelabel)"
  fi
  echo

  # Compute posture (R226 health-scan probes): the box's execution modes +
  # the cross-system compatibility verdict, surfaced where the operator reads
  # status. avx_mode is the M002 AVX/bit-machine path, cpu_mode the governor
  # mode, compat the ⚖ registry verdict. Read-only; attention (e.g. custom
  # bit-machine on a host without AVX-512) is marked [!]. rc=1 on a probe means
  # "attention", not a status failure, so the invocations tolerate it.
  local _hs="${__REPO_ROOT}/scripts/hardware/health-scan.py"
  if [ -r "${_hs}" ]; then
    echo "[Compute posture]"
    local _probe _json
    for _probe in avx_mode cpu_mode compat; do
      _json="$("${PYTHON3}" "${_hs}" --probe "${_probe}" --json 2>/dev/null || true)"
      if [ -n "${_json}" ]; then
        printf '%s' "${_json}" | "${PYTHON3}" -c '
import json, sys
name = sys.argv[1]
try:
    p = json.load(sys.stdin)
except Exception:
    p = None
if not p:
    print("  " + name + ": (verdict unavailable)")
else:
    sev = p.get("severity", "?")
    det = p.get("detail", "")
    mark = "[!] " if sev in ("attention", "down") else ""
    print("  " + p.get("probe", name) + ": " + mark + sev + " - " + det)
' "${_probe}" 2>/dev/null || echo "  ${_probe}: (verdict unavailable)"
      else
        echo "  ${_probe}: (probe unavailable)"
      fi
    done
    echo
  fi
}
