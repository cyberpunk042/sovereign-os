# shellcheck shell=bash
# scripts/osctl.d/thermals.sh — sovereign-osctl `thermals` verb module (F-2026-025).
# Sourced by the main sovereign-osctl dispatcher; do not run directly.
#
# thermal sensors summary + `--json`.
# Extracted verbatim from the sovereign-osctl monolith — behavior is
# byte-identical (same shell, same globals: __REPO_ROOT / PYTHON3 /
# log_* / common.sh helpers are all resident before dispatch sources this).

cmd_thermals() {
  local json_mode=0
  local probe_mode=0
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --json) json_mode=1; shift ;;
      --probe) probe_mode=1; shift ;;
      -h|--help)
        cat <<'EOF'
sovereign-osctl thermals — per-sensor thermal status (R175)

Usage:
  sovereign-osctl thermals           Show cached .prom-file readings
  sovereign-osctl thermals --json    Re-probe and emit JSON
  sovereign-osctl thermals --probe   Re-probe NOW (off the timer)

Exit codes:
  0   all sensors OK
  1   at least one WARN
  2   at least one CRITICAL
  3   no sensors / thermal-watch not run yet

Underlying source: scripts/hardware/thermal-watch.py (R172).
EOF
        return 0
        ;;
      *) log_error "unknown thermals flag: $1"; return 2 ;;
    esac
  done

  local script="${__REPO_ROOT:-/opt/sovereign-os}/scripts/hardware/thermal-watch.py"
  if [ ! -x "${script}" ]; then
    script="/opt/sovereign-os/scripts/hardware/thermal-watch.py"
  fi

  if [ "${probe_mode}" -eq 1 ] || [ "${json_mode}" -eq 1 ]; then
    if [ ! -x "${script}" ]; then
      log_error "thermal-watch.py not found at ${script}"
      exit 3
    fi
    if [ "${json_mode}" -eq 1 ]; then
      python3 "${script}" --json --dry-run-events
      exit $?
    fi
    python3 "${script}" --dry-run-events
    exit $?
  fi

  # Cached-.prom path: read the latest sovereign-os-thermal-watch.prom
  # written by the timer.
  : "${SOVEREIGN_OS_METRICS_DIR:=/var/lib/node_exporter/textfile_collector}"
  local prom="${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-thermal-watch.prom"
  if [ ! -f "${prom}" ]; then
    echo "no cached thermal readings yet at ${prom}"
    echo "  run 'sovereign-osctl thermals --probe' for a live read,"
    echo "  or wait for the sovereign-thermal-watch.timer 5-min tick."
    exit 3
  fi
  local mtime
  mtime="$(date -r "${prom}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown)"
  echo "# sovereign-osctl thermals (cached read; mtime ${mtime})"
  echo "# source: ${prom}"
  echo
  printf "%-32s  %8s  %8s\n" "SENSOR" "C" "STATUS"

  # Parse the textfile-collector emission. Two relevant series:
  #   sovereign_os_thermal_celsius{sensor="..."} <N>
  #   sovereign_os_thermal_severity{sensor="...",level="..."} 0|1
  local worst=0  # 0 ok, 1 warn, 2 critical
  local sensors=()
  declare -A celsius severity 2>/dev/null || true
  while IFS= read -r line; do
    case "${line}" in
      \#*|"") continue ;;
    esac
    if [[ "${line}" =~ ^sovereign_os_thermal_celsius\{sensor=\"([^\"]+)\"\}[[:space:]]+(-?[0-9]+) ]]; then
      celsius["${BASH_REMATCH[1]}"]="${BASH_REMATCH[2]}"
      sensors+=("${BASH_REMATCH[1]}")
    elif [[ "${line}" =~ ^sovereign_os_thermal_severity\{sensor=\"([^\"]+)\",level=\"([^\"]+)\"\}[[:space:]]+1 ]]; then
      severity["${BASH_REMATCH[1]}"]="${BASH_REMATCH[2]}"
    fi
  done < "${prom}"

  # Dedup sensors list while preserving order.
  local seen=""
  for s in "${sensors[@]}"; do
    case ":${seen}:" in
      *":${s}:"*) continue ;;
    esac
    seen="${seen}:${s}"
    local c="${celsius[${s}]:-?}"
    local sev="${severity[${s}]:-?}"
    local marker=" "
    case "${sev}" in
      critical) marker="✗"; [ "${worst}" -lt 2 ] && worst=2 ;;
      warn)     marker="!"; [ "${worst}" -lt 1 ] && worst=1 ;;
      ok)       marker="✓" ;;
    esac
    printf "%-32s  %8s  %s %s\n" "${s}" "${c}" "${marker}" "${sev}"
  done

  echo
  case "${worst}" in
    0) echo "ALL OK"; exit 0 ;;
    1) echo "WARN — at least one sensor above warn threshold"; exit 1 ;;
    2) echo "CRITICAL — at least one sensor above critical threshold"; exit 2 ;;
  esac
}
