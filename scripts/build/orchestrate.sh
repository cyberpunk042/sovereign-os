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
#   run [--profile <id>] [--dry-run]   run the pipeline; resume from last state
#   preflight [--profile <id>]   run all pre-install hooks (no build state mutated)
#   status                  print state summary
#   recover                 diagnose failed step + suggest next action (F-13 closure)
#   reset                   wipe build state (confirms first)
#   rewind <step>           mark step + later as pending (re-runs them)
#   skip <step>             mark step as completed (do not run)
#   list                    list all step IDs in order
#   help                    show this message
#
# --dry-run validates the plan (profile loads, each step script exists +
# is executable) without executing any step and without mutating state.
# Same effect via env: SOVEREIGN_OS_DRY_RUN=1.
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
# shellcheck source=./lib/observability.sh
. "${__SCRIPT_DIR}/lib/observability.sh"

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

cmd_recover() {
  # Round 135 (F-13 CRIT closure): when an operator's pipeline fails
  # mid-run, this verb inspects state + the most recent JSONL log + the
  # failure reason recorded in state.yaml and surfaces ONE recommended
  # next action with rationale. Never executes the action — operator
  # decides.

  state_init
  echo "sovereign-osctl orchestrate.sh recover"
  echo "======================================"
  echo
  echo "  state file: ${SOVEREIGN_OS_STATE_FILE}"
  echo

  # Find the FIRST failed step (state machine: pending → running →
  # completed | failed). If no failure, surface the next pending step.
  local failed_step="" failed_reason="" first_pending="" any_completed=0
  for s in "${STEPS[@]}"; do
    local st
    st="$(state_step_status "$s")"
    case "${st}" in
      failed)
        failed_step="${s}"
        # Extract the recorded fail reason from state.yaml
        failed_reason="$(awk -v step="${s}" '
          $0 ~ "  " step ":" { in_step = 1; next }
          in_step && /^    fail_reason:/ { gsub(/"/, "", $2); print $2; exit }
          in_step && /^  [a-z]/ { exit }
        ' "${SOVEREIGN_OS_STATE_FILE}" 2>/dev/null)"
        break
        ;;
      completed)
        any_completed=1
        ;;
      pending|running)
        [ -z "${first_pending}" ] && first_pending="${s}"
        ;;
    esac
  done

  if [ -n "${failed_step}" ]; then
    echo "  ✗ FAILED step: ${failed_step}"
    [ -n "${failed_reason}" ] && echo "    reason:      ${failed_reason}"
    echo

    # Find most recent JSONL log lines relevant to this step
    local log_dir="${HOME}/.sovereign-os/log"
    local recent_log
    recent_log="$(find "${log_dir}" -maxdepth 1 -name '*.jsonl' -printf '%T@ %p\n' 2>/dev/null \
                 | sort -nr | head -1 | awk '{print $2}')"
    if [ -n "${recent_log}" ] && [ -f "${recent_log}" ]; then
      echo "  recent log: ${recent_log}"
      echo "  last 5 error/warn events:"
      grep -E '"level":"(error|warn)"' "${recent_log}" 2>/dev/null \
        | tail -5 \
        | python3 -c "
import sys, json
for line in sys.stdin:
    try: e = json.loads(line)
    except: continue
    print(f'    [{e.get(\"level\",\"?\").upper()}] {e.get(\"msg\",\"\")[:100]}')
" 2>/dev/null
      echo
    fi

    echo "  RECOMMENDED NEXT ACTIONS (operator decides):"
    echo
    echo "  (a) Most common — fix the underlying issue, then re-run:"
    echo "        scripts/build/orchestrate.sh run"
    echo "      The pipeline will resume from ${failed_step} (inputs_hash gate"
    echo "      re-runs only changed steps)."
    echo
    echo "  (b) If the failure is transient / environmental and you want"
    echo "      to retry without changing inputs:"
    echo "        scripts/build/orchestrate.sh rewind ${failed_step}"
    echo "        scripts/build/orchestrate.sh run"
    echo
    echo "  (c) If the step is genuinely not-applicable to your profile"
    echo "      and you want to bypass it (e.g., 02-kernel-fetch on a"
    echo "      substrate-default profile):"
    echo "        scripts/build/orchestrate.sh skip ${failed_step}"
    echo "        scripts/build/orchestrate.sh run"
    echo
    echo "  (d) If you want to start completely over (DESTRUCTIVE):"
    echo "        scripts/build/orchestrate.sh reset"
    echo "        scripts/build/orchestrate.sh run"
    echo
    echo "  Full event log:    sovereign-osctl journal show $(basename "${recent_log:-?}" .jsonl 2>/dev/null)"
    echo "  Filter to errors:  sovereign-osctl journal errors"
    return 0
  fi

  # No failure — surface state
  if [ -n "${first_pending}" ]; then
    echo "  no failure recorded"
    echo "  next pending step: ${first_pending}"
    echo
    echo "  RECOMMENDED:"
    echo "    scripts/build/orchestrate.sh run"
    echo "  resumes from ${first_pending}."
  elif [ "${any_completed}" -eq 1 ]; then
    echo "  ✓ all steps completed; nothing to recover"
    echo
    echo "  RECOMMENDED:"
    echo "    sovereign-osctl install image --plan build/<profile>/output/<image> --to /dev/<target>"
    echo "  (Round 134 safety-gated install verb)"
  else
    echo "  state is empty (no steps run yet)"
    echo "  RECOMMENDED: scripts/build/orchestrate.sh run"
  fi
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
  local from="${1:-}"
  if [ -z "${from}" ]; then
    log_error "usage: orchestrate.sh rewind <step-id>"
    log_error "  marks <step-id> + all later steps as pending; next 'run' re-executes from <step-id>"
    log_error "  step IDs: $(IFS=,; echo "${STEPS[*]}")"
    return 2
  fi

  # Validate the step name
  local found=0 idx
  for idx in "${!STEPS[@]}"; do
    if [ "${STEPS[$idx]}" = "${from}" ]; then
      found=1
      break
    fi
  done
  if [ "${found}" -eq 0 ]; then
    log_error "unknown step: ${from} (valid: ${STEPS[*]})"
    return 2
  fi

  state_init

  # Confirm — rewind is reversible (just re-runs steps) but destroys
  # state-history for the rewound range. SOVEREIGN_OS_ASSUME_YES=1
  # bypasses the prompt for scripted invocations.
  if [ "${SOVEREIGN_OS_ASSUME_YES:-}" != "1" ]; then
    if ! confirm "Rewind from ${from} (and all later steps) to pending state?" default-no; then
      log_info "rewind cancelled"
      return 0
    fi
  fi

  # Strip every step from <from> onward out of state.yaml. Steps NOT in
  # state.yaml are 'pending' by default (state_step_status returns
  # 'pending' when the step entry is absent).
  local removed=0
  for ((i = idx; i < ${#STEPS[@]}; i++)); do
    local s="${STEPS[$i]}"
    # Same sed pattern state_step_start uses to wipe a step entry.
    sed -i "/^  ${s}:/,/^  [a-z]/{ /^  ${s}:/d ; /^  [a-z]/!d ; }" "${SOVEREIGN_OS_STATE_FILE}" 2>/dev/null || true
    log_info "  rewound: ${s} → pending"
    removed=$((removed + 1))
  done

  log_info "rewind complete — ${removed} step(s) marked pending"
  log_info "  next 'orchestrate.sh run' will re-execute from ${from}"
}

cmd_skip() {
  local step="${1:-}"
  if [ -z "${step}" ]; then
    log_error "usage: orchestrate.sh skip <step-id>"
    log_error "  marks <step-id> as completed WITHOUT running it"
    log_error "  step IDs: $(IFS=,; echo "${STEPS[*]}")"
    return 2
  fi

  # Validate the step name
  local found=0
  local s
  for s in "${STEPS[@]}"; do
    [ "${s}" = "${step}" ] && found=1
  done
  if [ "${found}" -eq 0 ]; then
    log_error "unknown step: ${step} (valid: ${STEPS[*]})"
    return 2
  fi

  state_init

  if [ "${SOVEREIGN_OS_ASSUME_YES:-}" != "1" ]; then
    if ! confirm "Mark ${step} as completed (skip its body)?" default-no; then
      log_info "skip cancelled"
      return 0
    fi
  fi

  # Pretend the step started + completed with a sentinel inputs_hash
  state_step_start "${step}" "skipped-by-operator"
  state_step_complete "${step}"
  log_info "  ${step} marked completed (skipped — body not executed)"
  log_info "  next 'orchestrate.sh run' will move past ${step}"
}

cmd_preflight() {
  # preflight: run every executable in scripts/hooks/pre-install/ against
  # the active profile. No build state mutation. Used by operators (and CI)
  # to validate the install-time environment before commit ing to a build.
  while [ $# -gt 0 ]; do
    case "$1" in
      --profile)   SOVEREIGN_OS_PROFILE="${2:?--profile requires an id}"; shift 2 ;;
      --profile=*) SOVEREIGN_OS_PROFILE="${1#--profile=}"; shift ;;
      *) log_error "unknown preflight flag: $1"; return 2 ;;
    esac
  done

  log_init
  load_profile "${SOVEREIGN_OS_PROFILE}"

  local pre_dir="${__SCRIPT_DIR}/../hooks/pre-install"
  if [ ! -d "${pre_dir}" ]; then
    log_error "pre-install hook dir missing: ${pre_dir}"
    return 1
  fi

  log_info "running pre-install hooks for profile=${SOVEREIGN_OS_PROFILE}"
  local fail=0 count=0
  while IFS= read -r hook; do
    count=$((count + 1))
    local hook_name; hook_name="$(basename "${hook}")"
    log_info "→ ${hook_name}"
    if SOVEREIGN_OS_LOG_STEP="preflight/${hook_name%.sh}" "${hook}"; then
      log_info "  ${hook_name}: PASS"
    else
      log_error "  ${hook_name}: FAIL"
      fail=$((fail + 1))
    fi
  done < <(find "${pre_dir}" -maxdepth 1 -name '*.sh' -type f -executable | sort)

  if [ "${count}" -eq 0 ]; then
    log_warn "no pre-install hooks found in ${pre_dir}"
    return 0
  fi

  echo
  if [ "${fail}" -eq 0 ]; then
    log_info "preflight: ${count}/${count} hooks PASSED"
    return 0
  else
    log_error "preflight: ${fail}/${count} hook(s) FAILED"
    return 1
  fi
}

cmd_run() {
  # Parse run-time flags
  local dry_run="${SOVEREIGN_OS_DRY_RUN:-}"
  while [ $# -gt 0 ]; do
    case "$1" in
      --dry-run)        dry_run=1; shift ;;
      --profile)        SOVEREIGN_OS_PROFILE="${2:?--profile requires an id}"; shift 2 ;;
      --profile=*)      SOVEREIGN_OS_PROFILE="${1#--profile=}"; shift ;;
      *)                log_error "unknown run flag: $1"; return 2 ;;
    esac
  done

  log_init

  if [ -n "${dry_run}" ]; then
    # Dry-run: validate plan without mutating state. Useful for CI gating
    # + operator preview ("what would happen if I ran this now").
    load_profile "${SOVEREIGN_OS_PROFILE}"
    log_info "DRY-RUN mode — no state mutation, no step execution"
    log_info "profile:   ${SOVEREIGN_OS_PROFILE}"
    log_info "substrate: ${SOVEREIGN_OS_SUBSTRATE}"
    log_info "planned step execution order:"
    local step idx=1 missing=0
    for step in "${STEPS[@]}"; do
      local script="${__SCRIPT_DIR}/${step}.sh"
      if [ -x "${script}" ]; then
        log_info "  [${idx}/${#STEPS[@]}] ${step} — would execute ${script}"
      else
        log_warn "  [${idx}/${#STEPS[@]}] ${step} — script missing or not executable: ${script}"
        missing=$((missing + 1))
      fi
      idx=$((idx + 1))
    done
    if [ "${missing}" -gt 0 ]; then
      log_warn "DRY-RUN: ${missing} step(s) missing or not executable"
      return 1
    fi
    log_info "DRY-RUN complete: all ${#STEPS[@]} steps present + executable"
    return 0
  fi

  state_init
  load_profile "${SOVEREIGN_OS_PROFILE}"

  log_info "starting build pipeline (profile=${SOVEREIGN_OS_PROFILE} substrate=${SOVEREIGN_OS_SUBSTRATE})"
  log_info "state: ${SOVEREIGN_OS_STATE_FILE}"
  log_info "log:   ${SOVEREIGN_OS_LOG_FILE}"

  # Pipeline timing (SDD-016 Layer B)
  local pipeline_start; pipeline_start="$(date +%s)"
  local steps_run=0 steps_failed=0

  local step
  for step in "${STEPS[@]}"; do
    local script="${__SCRIPT_DIR}/${step}.sh"
    if [ ! -x "${script}" ]; then
      log_warn "step ${step}: script not found or not executable (${script}) — skipping (will land in subsequent PR)"
      continue
    fi

    local step_start; step_start="$(date +%s)"
    if SOVEREIGN_OS_LOG_STEP="${step}" "${script}"; then
      local step_dur=$(( $(date +%s) - step_start ))
      steps_run=$((steps_run + 1))
      emit_metric sovereign_os_build_step_duration_seconds "${step_dur}" \
        "step=\"${step}\",profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"success\""
    else
      local step_dur=$(( $(date +%s) - step_start ))
      steps_failed=$((steps_failed + 1))
      emit_metric sovereign_os_build_step_duration_seconds "${step_dur}" \
        "step=\"${step}\",profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
      log_error "step ${step} failed; resume by re-running 'orchestrate.sh run'"
      _emit_pipeline_metrics "${pipeline_start}" "${steps_run}" "${steps_failed}" "fail"
      exit 1
    fi
  done

  log_info "build pipeline complete"
  _emit_pipeline_metrics "${pipeline_start}" "${steps_run}" "${steps_failed}" "success"
}

_emit_pipeline_metrics() {
  local start="$1" run="$2" failed="$3" result="$4"
  local dur=$(( $(date +%s) - start ))
  emit_metric_set build-pipeline \
    '# HELP sovereign_os_build_pipeline_duration_seconds Wall-clock duration of last pipeline run' \
    '# TYPE sovereign_os_build_pipeline_duration_seconds gauge' \
    "sovereign_os_build_pipeline_duration_seconds{profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"${result}\"} ${dur}" \
    '# HELP sovereign_os_build_pipeline_steps_total Steps executed in last pipeline run' \
    '# TYPE sovereign_os_build_pipeline_steps_total gauge' \
    "sovereign_os_build_pipeline_steps_total{profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"success\"} ${run}" \
    "sovereign_os_build_pipeline_steps_total{profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\"} ${failed}" \
    '# HELP sovereign_os_build_pipeline_last_run_timestamp Unix timestamp of last pipeline run completion' \
    '# TYPE sovereign_os_build_pipeline_last_run_timestamp gauge' \
    "sovereign_os_build_pipeline_last_run_timestamp{profile=\"${SOVEREIGN_OS_PROFILE}\"} $(date +%s)"
}

# Dispatch ----------------------------------------------------------------

cmd="${1:-help}"
shift || true

case "${cmd}" in
  run|"")    cmd_run "$@" ;;
  preflight) cmd_preflight "$@" ;;
  status)    cmd_status "$@" ;;
  recover)   cmd_recover "$@" ;;
  reset)     cmd_reset "$@" ;;
  rewind)    cmd_rewind "$@" ;;
  skip)      cmd_skip "$@" ;;
  list)      cmd_list "$@" ;;
  help|--help|-h) cmd_help ;;
  *)
    log_error "unknown command: ${cmd}"
    cmd_help
    exit 2
    ;;
esac
