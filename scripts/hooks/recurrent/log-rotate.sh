#!/usr/bin/env bash
# scripts/hooks/recurrent/log-rotate.sh
#
# Daily log rotation for sovereign-os JSONL logs.
#
# What it does:
#   • For every *.jsonl in ${SOVEREIGN_OS_LOG_DIR} older than
#     SOVEREIGN_OS_LOG_RETENTION_DAYS (default: 14), gzip + move to
#     ${SOVEREIGN_OS_LOG_DIR}/archive/.
#   • For archive files older than SOVEREIGN_OS_LOG_ARCHIVE_DAYS
#     (default: 90), delete.
#   • Idempotent; safe to run multiple times per day.
#
# Honors profile.observability.log_retention_days when set —
# overrides the default but is overridden by an explicit env var.
#
# Tunable env:
#   SOVEREIGN_OS_LOG_DIR              default: ~/.sovereign-os/log
#   SOVEREIGN_OS_LOG_RETENTION_DAYS   default: 14 (after which: gzip+archive)
#   SOVEREIGN_OS_LOG_ARCHIVE_DAYS     default: 90 (after which: delete)

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

: "${SOVEREIGN_OS_LOG_DIR:=${HOME}/.sovereign-os/log}"
: "${SOVEREIGN_OS_LOG_RETENTION_DAYS:=14}"
: "${SOVEREIGN_OS_LOG_ARCHIVE_DAYS:=90}"
# Size cap for ACTIVELY-APPENDED logs. The mtime-based rotation below never
# fires on a continuously-written file (e.g. notify.jsonl — its mtime is
# always current), so without a size trigger it would grow unbounded and
# fill the disk. Default 50 MiB; set 0 to disable size-based rotation.
: "${SOVEREIGN_OS_LOG_MAX_BYTES:=52428800}"

# Optionally read retention from the active profile (operator wins via env)
if [ -z "${SOVEREIGN_OS_LOG_RETENTION_DAYS_USER_SET:-}" ] && [ -n "${SOVEREIGN_OS_PROFILE:-}" ]; then
  load_profile "${SOVEREIGN_OS_PROFILE}" 2>/dev/null || true
  pf="$(profile_field observability.log_retention_days 2>/dev/null || true)"
  if [ -n "${pf}" ] && [[ "${pf}" =~ ^[0-9]+$ ]]; then
    SOVEREIGN_OS_LOG_RETENTION_DAYS="${pf}"
  fi
fi

log_step_header "log-rotate" "rotate >${SOVEREIGN_OS_LOG_RETENTION_DAYS}d; purge >${SOVEREIGN_OS_LOG_ARCHIVE_DAYS}d"

if [ ! -d "${SOVEREIGN_OS_LOG_DIR}" ]; then
  log_info "log dir ${SOVEREIGN_OS_LOG_DIR} doesn't exist; nothing to rotate"
  exit 0
fi

archive_dir="${SOVEREIGN_OS_LOG_DIR}/archive"
mkdir -p "${archive_dir}"

rotated=0

# ---- size-based rotation for active (continuously-appended) logs ----
# A continuously-written *.jsonl never ages past RETENTION_DAYS by mtime, so
# rotate by SIZE too. Atomic `mv` to a timestamped name first: an appender
# holding the file open ("a") keeps writing to the renamed inode (archived
# intact), and its NEXT invocation (sovereign-os appenders open per-call)
# recreates a fresh file — no lost lines.
if [ "${SOVEREIGN_OS_LOG_MAX_BYTES}" -gt 0 ] 2>/dev/null; then
  while IFS= read -r f; do
    if [ -z "${f}" ]; then continue; fi
    ts="$(date -u +%Y%m%dT%H%M%S)"
    rotated_name="${f}.${ts}"
    if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
      log_info "  would size-rotate: $(basename "${f}") (>$((SOVEREIGN_OS_LOG_MAX_BYTES / 1048576)) MiB) → archive/$(basename "${rotated_name}").gz"
    else
      mv "${f}" "${rotated_name}" \
        && gzip "${rotated_name}" \
        && mv "${rotated_name}.gz" "${archive_dir}/"
      log_info "  size-rotated: $(basename "${f}") → archive/$(basename "${rotated_name}").gz"
    fi
    rotated=$((rotated + 1))
  done < <(find "${SOVEREIGN_OS_LOG_DIR}" -maxdepth 1 -name '*.jsonl' -type f -size "+${SOVEREIGN_OS_LOG_MAX_BYTES}c" 2>/dev/null)
fi

# ---- gzip + move old *.jsonl into archive/ ----
while IFS= read -r f; do
  if [ -z "${f}" ]; then continue; fi
  gz="${f}.gz"
  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    log_info "  would rotate: ${f} → ${archive_dir}/$(basename "${gz}")"
  else
    gzip -c "${f}" > "${gz}" && rm -f "${f}"
    mv "${gz}" "${archive_dir}/"
    log_info "  rotated: $(basename "${f}") → archive/"
  fi
  rotated=$((rotated + 1))
done < <(find "${SOVEREIGN_OS_LOG_DIR}" -maxdepth 1 -name '*.jsonl' -type f -mtime "+${SOVEREIGN_OS_LOG_RETENTION_DAYS}" 2>/dev/null)

# ---- delete archive files older than ARCHIVE_DAYS ----
purged=0
while IFS= read -r f; do
  if [ -z "${f}" ]; then continue; fi
  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    log_info "  would purge: ${f}"
  else
    rm -f "${f}"
    log_info "  purged: $(basename "${f}")"
  fi
  purged=$((purged + 1))
done < <(find "${archive_dir}" -maxdepth 1 -name '*.gz' -type f -mtime "+${SOVEREIGN_OS_LOG_ARCHIVE_DAYS}" 2>/dev/null)

log_info "log-rotate: ${rotated} rotated, ${purged} purged"

# ---- emit Layer B metrics (SDD-016) ----
emit_metric_set log-rotation \
  '# HELP sovereign_os_log_rotation_files_rotated Files rotated by the last log-rotate run' \
  '# TYPE sovereign_os_log_rotation_files_rotated gauge' \
  "sovereign_os_log_rotation_files_rotated ${rotated}" \
  '# HELP sovereign_os_log_rotation_files_purged Archive files purged by the last log-rotate run' \
  '# TYPE sovereign_os_log_rotation_files_purged gauge' \
  "sovereign_os_log_rotation_files_purged ${purged}" \
  '# HELP sovereign_os_log_rotation_last_run_timestamp Unix timestamp of last successful run' \
  '# TYPE sovereign_os_log_rotation_last_run_timestamp gauge' \
  "sovereign_os_log_rotation_last_run_timestamp $(date +%s)"

exit 0
