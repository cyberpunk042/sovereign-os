# shellcheck shell=bash
# scripts/osctl.d/metrics.sh — sovereign-osctl `metrics` verb module (F-2026-025).
# Sourced by the main sovereign-osctl dispatcher; do not run directly.
#
# Prometheus textfile-collector metric surface.
# Extracted verbatim from the sovereign-osctl monolith — behavior is
# byte-identical (same shell, same globals: __REPO_ROOT / PYTHON3 /
# log_* / common.sh helpers are all resident before dispatch sources this).

cmd_metrics() {
  local sub="${1:-list}"
  shift || true

  : "${SOVEREIGN_OS_METRICS_DIR:=/var/lib/node_exporter/textfile_collector}"

  case "${sub}" in
    list)
      if [ ! -d "${SOVEREIGN_OS_METRICS_DIR}" ]; then
        echo "metrics dir absent: ${SOVEREIGN_OS_METRICS_DIR}"
        echo "  (node_exporter textfile collector may not be installed,"
        echo "   or no hook has emitted a metric yet)"
        return 0
      fi
      local files
      mapfile -t files < <(find "${SOVEREIGN_OS_METRICS_DIR}" -maxdepth 1 -name 'sovereign-os-*.prom' -type f 2>/dev/null | sort)
      if [ "${#files[@]}" -eq 0 ]; then
        echo "no sovereign-os-*.prom files in ${SOVEREIGN_OS_METRICS_DIR}"
        return 0
      fi
      printf "%-50s  %-20s  %s\n" "FILE" "LAST UPDATE" "METRICS"
      for f in "${files[@]}"; do
        local bn mtime n
        bn="$(basename "${f}")"
        mtime="$(date -r "${f}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown)"
        n="$(grep -vc '^#\|^$' "${f}" 2>/dev/null || echo 0)"
        printf "%-50s  %-20s  %s\n" "${bn}" "${mtime}" "${n}"
      done
      ;;
    show)
      local name="${1:-}"
      if [ -z "${name}" ]; then
        log_error "usage: sovereign-osctl metrics show <basename>"
        log_error "  example: sovereign-osctl metrics show log-rotation"
        log_error "  (.prom suffix optional; sovereign-os- prefix optional)"
        return 2
      fi
      # Resolve: try exact, then with sovereign-os- prefix, then with .prom suffix
      local file=""
      for candidate in \
        "${SOVEREIGN_OS_METRICS_DIR}/${name}" \
        "${SOVEREIGN_OS_METRICS_DIR}/${name}.prom" \
        "${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-${name}" \
        "${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-${name}.prom"; do
        if [ -f "${candidate}" ]; then
          file="${candidate}"
          break
        fi
      done
      if [ -z "${file}" ]; then
        log_error "no .prom file matches '${name}' in ${SOVEREIGN_OS_METRICS_DIR}"
        log_error "  run 'sovereign-osctl metrics list' to see what's available"
        return 1
      fi
      echo "# file:  ${file}"
      echo "# mtime: $(date -r "${file}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo unknown)"
      echo
      cat "${file}"
      ;;
    tail)
      local n="${1:-5}"
      if ! [[ "${n}" =~ ^[0-9]+$ ]]; then
        log_error "tail count must be a non-negative integer (got: ${n})"
        return 2
      fi
      if [ ! -d "${SOVEREIGN_OS_METRICS_DIR}" ]; then
        echo "metrics dir absent: ${SOVEREIGN_OS_METRICS_DIR}"
        return 0
      fi
      # Newest-first ordering by mtime; cap at N
      mapfile -t recent < <(find "${SOVEREIGN_OS_METRICS_DIR}" -maxdepth 1 -name 'sovereign-os-*.prom' -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n "${n}" | awk '{print $2}')
      if [ "${#recent[@]}" -eq 0 ]; then
        echo "no sovereign-os-*.prom files in ${SOVEREIGN_OS_METRICS_DIR}"
        return 0
      fi
      for f in "${recent[@]}"; do
        echo "===== $(basename "${f}")  ($(date -r "${f}" '+%Y-%m-%d %H:%M:%S')) ====="
        grep -v '^#' "${f}" | grep -v '^$' || true
        echo
      done
      ;;
    health)
      local issues=0
      if [ ! -d "${SOVEREIGN_OS_METRICS_DIR}" ]; then
        log_warn "metrics dir absent: ${SOVEREIGN_OS_METRICS_DIR}"
        log_warn "  install node_exporter and create the dir, or set"
        log_warn "  SOVEREIGN_OS_METRICS_DIR to an alternate path"
        return 1
      fi
      log_info "metrics dir: ${SOVEREIGN_OS_METRICS_DIR}"
      mapfile -t files < <(find "${SOVEREIGN_OS_METRICS_DIR}" -maxdepth 1 -name 'sovereign-os-*.prom' -type f 2>/dev/null | sort)
      if [ "${#files[@]}" -eq 0 ]; then
        log_warn "  no sovereign-os-*.prom files present (no hook has emitted yet)"
        return 0
      fi
      log_info "  ${#files[@]} sovereign-os-*.prom files"
      local now stale_threshold
      now="$(date +%s)"
      stale_threshold="${SOVEREIGN_OS_METRICS_STALE_DAYS:-7}"
      for f in "${files[@]}"; do
        local mtime age_days
        mtime="$(stat -c '%Y' "${f}" 2>/dev/null || echo "${now}")"
        age_days=$(( (now - mtime) / 86400 ))
        if [ "${age_days}" -gt "${stale_threshold}" ]; then
          log_warn "  STALE — $(basename "${f}") (${age_days}d old, threshold ${stale_threshold}d)"
          issues=$((issues + 1))
        fi
        # format sanity: each non-comment, non-empty line should be 'name value' or 'name{labels} value'
        local bad_lines
        bad_lines="$(grep -v '^#' "${f}" | grep -v '^$' | grep -cvE '^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^}]*\})?\s+[-0-9.eE+]+(\s+[0-9]+)?\s*$' || true)"
        if [ "${bad_lines:-0}" -gt 0 ]; then
          log_error "  MALFORMED — $(basename "${f}") has ${bad_lines} non-conforming line(s)"
          issues=$((issues + 1))
        fi
      done
      if [ "${issues}" -eq 0 ]; then
        log_info "  all files fresh + well-formed"
        return 0
      else
        log_error "  ${issues} issue(s) found"
        return 1
      fi
      ;;
    *)
      log_error "unknown metrics subcommand: ${sub}"
      log_error "  available: list / show <name> / tail [N] / health"
      return 2
      ;;
  esac
}
