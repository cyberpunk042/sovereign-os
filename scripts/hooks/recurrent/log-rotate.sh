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

# ---- gzip + move old *.jsonl into archive/ ----
rotated=0
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
