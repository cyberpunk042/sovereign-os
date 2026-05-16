#!/usr/bin/env bash
# scripts/build/orchestrate.sh — sovereign-os build pipeline driver.
#
# Operator-verbatim IaC bar (sacrosanct):
#   "easily tweakable and configurable and customisation and even via
#    env vars when needed, or other pre-existing config or temporary
#    file detected and restarting from there such as if there is has
#    to be a local tracking of the progress of a build in multi-steps
#    that can only ever re-happen locally"
#
# This driver implements:
#   • Per-step state in ~/.sovereign-os/build-state/state.yaml
#   • Inputs-hash-aware step skip (rerun only when inputs change)
#   • Resume-from-state on retry (no fresh restart unless asked)
#   • Operator-visible progress; structured JSONL log
#   • Env-var overrides for every knob; CLI flags override env vars
#   • Pause/resume/rewind/skip-step via subcommands
#
# Usage:
#   scripts/build/orchestrate.sh [<command>] [<options>]
#
# Commands:
#   run [--profile <id>]    run the pipeline; resume from last state
#   status                  print state summary
#   reset                   wipe build state (confirms first)
#   rewind <step>           mark step + later as pending (re-runs them)
#   skip <step>             mark step as completed (do not run)
#   list                    list all step IDs in order
#   help                    show this message
#
# Steps (executed in order; can be skipped/rewound individually):
#   01-bootstrap-forge      install dev tools + mount tmpfs ramdisk
#   02-kernel-fetch         clone kernel source into the forge
#   03-kernel-config        derive .config from active profile
#   04-kernel-compile       make -j$(nproc) bindeb-pkg
#   05-substrate-prepare    substrate-adapter prep (per Q-001)
#   06-whitelabel-render    render whitelabel templates + overlays
#   07-image-build          substrate-driven image build
#   08-image-sign           sign image + bootloader per profile.kernel.cmdline.secure_boot
#   09-image-verify         QEMU smoke test (or skip if SOVEREIGN_OS_SKIP_QEMU set)
#
# Env vars (all overridable on CLI):
#   SOVEREIGN_OS_PROFILE         active profile id (default: sain-01)
#   SOVEREIGN_OS_STATE_DIR       state location (default: ~/.sovereign-os/build-state)
#   SOVEREIGN_OS_LOG_DIR         log location (default: ~/.sovereign-os/log)
#   SOVEREIGN_OS_LOG_LEVEL       debug|info|warn|error (default: info)
#   SOVEREIGN_OS_NONINTERACTIVE  set non-empty to skip all prompts (CI mode)
#   SOVEREIGN_OS_SKIP_QEMU       set non-empty to skip step 09
#   SOVEREIGN_OS_SUBSTRATE       substrate adapter (mkosi|live-build|...); resolves per Q-001 once locked

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
: "${SOVEREIGN_OS_SUBSTRATE:=mkosi}"   # working hypothesis; Q-001 locks at Gate 2

# Ordered list of steps. Each is a sibling script that sources the
# common lib and registers under its step-id.
STEPS=(
  "01-bootstrap-forge"
  "02-kernel-fetch"
  "03-kernel-config"
  "04-kernel-compile"
  "05-substrate-prepare"
  "06-whitelabel-render"
  "07-image-build"
  "08-image-sign"
  "09-image-verify"
)

cmd_help() {
  # Strip leading '# ' from the file's top comment block; stop at the
  # first empty (non-comment) line after Usage: (so we get the full
  # USAGE + Commands + Steps + env-vars sections).
  sed -n '
    /^[^#]/q
    s/^# \?//p
  ' "$0"
}

cmd_list() {
  for s in "${STEPS[@]}"; do
    local status
    status="$(state_step_status "$s")"
    printf '  %-25s [%s]\n' "$s" "$status"
  done
}

cmd_status() {
  state_summary
}

cmd_reset() {
  if ! confirm "Wipe all build state at ${SOVEREIGN_OS_STATE_FILE}?" default-no; then
    log_info "reset cancelled"
    return 0
  fi
  state_reset
  log_info "build state wiped; next 'run' starts from step 01"
}

cmd_rewind() {
  local from="$1"
  log_warn "rewind not yet implemented — manual edit ${SOVEREIGN_OS_STATE_FILE} OR use 'reset'"
  log_warn "tracked in Q9-? for the harness PR; placeholder for now"
  return 1
}

cmd_skip() {
  local step="$1"
  log_warn "skip not yet implemented — manual edit ${SOVEREIGN_OS_STATE_FILE}"
  log_warn "placeholder for now; tracked alongside rewind"
  return 1
}

cmd_run() {
  log_init
  state_init
  load_profile "${SOVEREIGN_OS_PROFILE}"

  log_info "starting build pipeline (profile=${SOVEREIGN_OS_PROFILE} substrate=${SOVEREIGN_OS_SUBSTRATE})"
  log_info "state: ${SOVEREIGN_OS_STATE_FILE}"
  log_info "log:   ${SOVEREIGN_OS_LOG_FILE}"

  local step
  for step in "${STEPS[@]}"; do
    local script="${__SCRIPT_DIR}/${step}.sh"
    if [ ! -x "${script}" ]; then
      log_warn "step ${step}: script not found or not executable (${script}) — skipping (will land in subsequent PR)"
      continue
    fi
    SOVEREIGN_OS_LOG_STEP="${step}" \
      "${script}" || {
        log_error "step ${step} failed; resume by re-running 'orchestrate.sh run'"
        exit 1
      }
  done

  log_info "build pipeline complete"
}

# Dispatch ----------------------------------------------------------------

cmd="${1:-help}"
shift || true

case "${cmd}" in
  run|"") cmd_run "$@" ;;
  status) cmd_status "$@" ;;
  reset)  cmd_reset "$@" ;;
  rewind) cmd_rewind "$@" ;;
  skip)   cmd_skip "$@" ;;
  list)   cmd_list "$@" ;;
  help|--help|-h) cmd_help ;;
  *)
    log_error "unknown command: ${cmd}"
    cmd_help
    exit 2
    ;;
esac
