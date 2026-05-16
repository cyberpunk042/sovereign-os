#!/usr/bin/env bash
# scripts/build/lib/logging.sh — structured logging for the build
# pipeline. Observable per IaC bar.
#
# Each log entry: timestamp · step · level · message. Plain-text
# stdout for operator visibility; JSON-lines file for machine
# consumption.

if [ -n "${__SOVEREIGN_OS_LOG_LIB_LOADED:-}" ]; then
  return 0
fi
__SOVEREIGN_OS_LOG_LIB_LOADED=1

: "${SOVEREIGN_OS_LOG_DIR:=${HOME}/.sovereign-os/log}"
: "${SOVEREIGN_OS_LOG_FILE:=${SOVEREIGN_OS_LOG_DIR}/build-$(date -u +%Y%m%dT%H%M%SZ).jsonl}"
: "${SOVEREIGN_OS_LOG_LEVEL:=info}"   # debug | info | warn | error

# ANSI colors (TTY only; auto-disabled when stdout is not a TTY)
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  __C_BLUE="$(printf '\033[34m')"
  __C_GREEN="$(printf '\033[32m')"
  __C_YELLOW="$(printf '\033[33m')"
  __C_RED="$(printf '\033[31m')"
  __C_BOLD="$(printf '\033[1m')"
  __C_RESET="$(printf '\033[0m')"
else
  __C_BLUE=""; __C_GREEN=""; __C_YELLOW=""; __C_RED=""; __C_BOLD=""; __C_RESET=""
fi

log_init() {
  mkdir -p "${SOVEREIGN_OS_LOG_DIR}"
  touch "${SOVEREIGN_OS_LOG_FILE}"
}

__log_emit() {
  # __log_emit <level> <color> <step> <message>
  local level="$1" color="$2" step="$3"
  shift 3
  local message="$*"
  local ts
  ts="$(date -u --iso-8601=seconds)"
  printf '%s%s%-5s%s [%s] %s%s\n' "${color}" "${__C_BOLD}" "${level^^}" "${__C_RESET}${color}" "${step}" "${message}" "${__C_RESET}" >&2
  if [ -n "${SOVEREIGN_OS_LOG_FILE:-}" ]; then
    # Lazy-init the log dir on first write — operators sourcing common.sh
    # without calling log_init() should still get JSONL output.
    local log_dir
    log_dir="$(dirname "${SOVEREIGN_OS_LOG_FILE}")"
    if [ ! -d "${log_dir}" ]; then
      mkdir -p "${log_dir}" 2>/dev/null || return 0
    fi
    # Escape message for JSON (basic — handles quotes + backslashes; sufficient for build-step messages)
    local esc="${message//\\/\\\\}"
    esc="${esc//\"/\\\"}"
    esc="${esc//$'\n'/\\n}"
    printf '{"ts":"%s","level":"%s","step":"%s","msg":"%s"}\n' \
      "${ts}" "${level}" "${step}" "${esc}" >> "${SOVEREIGN_OS_LOG_FILE}" 2>/dev/null || true
  fi
}

log_debug() {
  [ "${SOVEREIGN_OS_LOG_LEVEL}" = "debug" ] || return 0
  __log_emit debug "${__C_BLUE}" "${SOVEREIGN_OS_LOG_STEP:-build}" "$*"
}

log_info() {
  case "${SOVEREIGN_OS_LOG_LEVEL}" in
    debug|info) ;;
    *) return 0 ;;
  esac
  __log_emit info "${__C_GREEN}" "${SOVEREIGN_OS_LOG_STEP:-build}" "$*"
}

log_warn() {
  case "${SOVEREIGN_OS_LOG_LEVEL}" in
    debug|info|warn) ;;
    *) return 0 ;;
  esac
  __log_emit warn "${__C_YELLOW}" "${SOVEREIGN_OS_LOG_STEP:-build}" "$*"
}

log_error() {
  __log_emit error "${__C_RED}" "${SOVEREIGN_OS_LOG_STEP:-build}" "$*"
}

log_step_header() {
  # Visible separator at step start
  local step="$1"
  shift
  local title="$*"
  printf '\n%s%s━━━ STEP %s — %s ━━━%s\n' "${__C_BLUE}" "${__C_BOLD}" "${step}" "${title}" "${__C_RESET}" >&2
}
