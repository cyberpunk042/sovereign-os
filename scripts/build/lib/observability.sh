#!/usr/bin/env bash
# scripts/build/lib/observability.sh — Layer B metrics emission.
#
# Implements SDD-016's Prometheus textfile collector contract:
#   write `.prom` files to ${SOVEREIGN_OS_METRICS_DIR} (default
#   /var/lib/node_exporter/textfile_collector/) atomically (tempfile
#   + rename — no file-locking, no partial reads by the scraper).
#
# Operator's IaC bar (sacrosanct verbatim): "observable and operable,
# at all stages of lifecycle".
#
# Public API:
#   emit_metric NAME VALUE [LABELS]  — write or update a single metric
#   emit_metric_set FILE_BASENAME METRICS  — bulk-write multiple metrics into one .prom file
#
# Honors SOVEREIGN_OS_DRY_RUN=1 (logs "would emit" instead of writing).
# Honors profile.observability.telemetry_sink (skips writes entirely
# when sink is not 'prometheus-local').
#
# Sourcing is idempotent (source-guard).

if [ -n "${__SOVEREIGN_OS_OBSERVABILITY_LIB_SOURCED:-}" ]; then
  return 0
fi
__SOVEREIGN_OS_OBSERVABILITY_LIB_SOURCED=1

: "${SOVEREIGN_OS_METRICS_DIR:=/var/lib/node_exporter/textfile_collector}"
: "${SOVEREIGN_OS_METRICS_PREFIX:=sovereign-os}"

# Check if metrics emission is active.
# Returns 0 if we should emit, non-zero if we should skip.
_metrics_active() {
  # Skip if explicitly disabled
  if [ "${SOVEREIGN_OS_METRICS_DISABLE:-}" = "1" ]; then
    return 1
  fi

  # Honor profile.observability.telemetry_sink when available
  if [ -n "${SOVEREIGN_OS_PROFILE_FILE:-}" ] && declare -F profile_field >/dev/null 2>&1; then
    local sink
    sink="$(profile_field observability.telemetry_sink 2>/dev/null || true)"
    if [ -n "${sink}" ] && [ "${sink}" != "prometheus-local" ]; then
      return 1
    fi
  fi

  return 0
}

# emit_metric NAME VALUE [LABELS]
#
# Writes a single metric line to a per-subsystem .prom file. The
# subsystem is derived from the metric name's first segment after
# the 'sovereign_os_' prefix (e.g., sovereign_os_log_rotation_files_
# rotated → 'log_rotation' → sovereign-os-log-rotation.prom).
#
# Each call REWRITES the named metric's gauge value (textfile collector
# semantics: latest value wins). For counters, the caller computes the
# new value (we don't accumulate here).
#
# Example:
#   emit_metric sovereign_os_log_rotation_files_rotated 3
#   emit_metric sovereign_os_log_rotation_files_purged 1
#   emit_metric sovereign_os_inference_route_total 42 'tier="pulse"'
emit_metric() {
  local name="$1" value="$2" labels="${3:-}"

  if ! _metrics_active; then
    return 0
  fi

  # Derive subsystem (second segment of the metric name after 'sovereign_os_')
  local subsystem
  subsystem="$(echo "${name}" | sed -E 's/^sovereign_os_//; s/_[^_]+_[^_]+_.*$//; s/_[^_]+$//')"
  if [ -z "${subsystem}" ]; then
    subsystem="misc"
  fi

  local prom_file="${SOVEREIGN_OS_METRICS_DIR}/${SOVEREIGN_OS_METRICS_PREFIX}-${subsystem//_/-}.prom"

  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    echo "  would emit: ${name}{${labels}} ${value} → ${prom_file}"
    return 0
  fi

  mkdir -p "${SOVEREIGN_OS_METRICS_DIR}" 2>/dev/null || {
    # Metrics dir unavailable (not root / no exporter installed yet);
    # silent skip — observability is optional, never break the caller.
    return 0
  }

  # Atomic write: build new content in a tempfile, then rename.
  # If file exists, preserve other metrics; replace any matching name+labels line.
  local tmp; tmp="$(mktemp "${prom_file}.XXXXXX" 2>/dev/null)" || return 0

  local match="^${name}"
  if [ -n "${labels}" ]; then
    match="^${name}{${labels}}"
  fi

  if [ -f "${prom_file}" ]; then
    # Drop any prior line for this metric+labels combo
    grep -vE "${match}([[:space:]]|\{)" "${prom_file}" 2>/dev/null > "${tmp}" || true
  else
    : > "${tmp}"
  fi

  # Append the new line
  if [ -n "${labels}" ]; then
    printf '%s{%s} %s\n' "${name}" "${labels}" "${value}" >> "${tmp}"
  else
    printf '%s %s\n' "${name}" "${value}" >> "${tmp}"
  fi

  # Atomic rename
  mv "${tmp}" "${prom_file}" 2>/dev/null || rm -f "${tmp}"
}

# emit_metric_set BASENAME LINES...
#
# Bulk-write multiple metrics into one .prom file in a single atomic
# operation. Use when emitting a coherent set (e.g., a full log-rotate
# run's metrics).
#
# Each metric line is a full Prometheus text-format line (incl. HELP/
# TYPE if desired).
#
# Example:
#   emit_metric_set log-rotation \
#     '# HELP sovereign_os_log_rotation_files_rotated Last run rotated' \
#     '# TYPE sovereign_os_log_rotation_files_rotated gauge' \
#     "sovereign_os_log_rotation_files_rotated ${rotated}" \
#     "sovereign_os_log_rotation_files_purged ${purged}" \
#     "sovereign_os_log_rotation_last_run_timestamp $(date +%s)"
emit_metric_set() {
  local basename="$1"; shift

  if ! _metrics_active; then
    return 0
  fi

  local prom_file="${SOVEREIGN_OS_METRICS_DIR}/${SOVEREIGN_OS_METRICS_PREFIX}-${basename//_/-}.prom"

  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    echo "  would emit ${#@} metric line(s) → ${prom_file}"
    return 0
  fi

  mkdir -p "${SOVEREIGN_OS_METRICS_DIR}" 2>/dev/null || return 0

  local tmp; tmp="$(mktemp "${prom_file}.XXXXXX" 2>/dev/null)" || return 0

  for line in "$@"; do
    printf '%s\n' "${line}" >> "${tmp}"
  done

  mv "${tmp}" "${prom_file}" 2>/dev/null || rm -f "${tmp}"
}
