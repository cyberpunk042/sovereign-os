#!/usr/bin/env bash
# scripts/bootstrap/run.sh — Master spec § 12 phase executor (R201).
#
# Sister to phases.sh (R160). phases.sh INVENTORIES the 5-phase pipeline
# (presence-check at authoring time); run.sh DRIVES it (enumerates the
# execution plan operators would invoke on real hardware).
#
# Per master spec § 12: "Each phase must be completed and validated
# before the downstream phase is initiated." run.sh enforces that
# sequencing constraint by phase-at-a-time invocation + by surfacing
# the execution kind of every artifact (build-step / installer-hook /
# post-install-hook / systemd-unit / recurrent-hook / tooling) so the
# operator knows WHERE each artifact runs.
#
# Safety posture:
#   - Default is DRY-RUN. Phase III-V artifacts are destructive
#     (zfs-pool-create wipes NVMe, vfio-bind detaches the GPU,
#     tetragon-policy-load loads kernel BPF).
#   - Real --apply requires ALL THREE gates:
#       1) --apply flag
#       2) --confirm-apply flag
#       3) SOVEREIGN_OS_CONFIRM_DESTROY=YES environment variable
#   - When all three gates hold AND the operator confirms the
#     interactive prompt (or SOVEREIGN_OS_NONINTERACTIVE is set),
#     run.sh executes applicable artifacts instead of merely listing them.
#
# CLI:
#   run.sh --phase N [--json]          enumerate phase N's plan
#   run.sh --phase N --apply           attempt real execution (triple-gated)
#   run.sh --phase all [--json]        enumerate ALL phases (default)
#
# Exit codes:
#   0 — execution plan emitted / all artifacts applied successfully
#   1 — at least one artifact missing or apply failure
#   2 — usage error or gate failure

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
__REPO_ROOT="$(cd "${__REPO_ROOT}/.." && pwd)"

# ---------- python3 resolver ----------
# Some environments (linuxbrew) ship a python3 without PyYAML. Pick the
# first python3 in PATH that can import yaml; fall back to /usr/bin/python3.
PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3="/usr/bin/python3"
  fi
fi

# Source common helpers for confirm() and logging when available.
COMMON_SH="${__REPO_ROOT}/scripts/build/lib/common.sh"
if [ -f "${COMMON_SH}" ]; then
  # shellcheck source=../build/lib/common.sh
  . "${COMMON_SH}"
else
  # Lightweight fallback confirm for environments without common.sh.
  confirm() {
    local prompt="$1" default="${2:-default-no}"
    if [ -n "${SOVEREIGN_OS_NONINTERACTIVE:-}" ]; then
      [ "${default}" = "default-yes" ]
      return $?
    fi
    if [ "${default}" = "default-yes" ]; then
      read -rp "${prompt} [Y/n] " ans
      ans="${ans:-y}"
    else
      read -rp "${prompt} [y/N] " ans
      ans="${ans:-n}"
    fi
    [[ "${ans}" =~ ^[Yy]([Ee][Ss])?$ ]]
  }
fi

JSON_OUT=0
PHASE_FILTER="all"
APPLY=0
CONFIRM_APPLY=0
FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON_OUT=1; shift ;;
    --phase) PHASE_FILTER="$2"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --confirm-apply) CONFIRM_APPLY=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help)
      sed -n '1,38p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *) echo "ERROR unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "${PHASE_FILTER}" in
  all) ;;
  I|i|1) PHASE_FILTER=1 ;;
  II|ii|2) PHASE_FILTER=2 ;;
  III|iii|3) PHASE_FILTER=3 ;;
  IV|iv|4) PHASE_FILTER=4 ;;
  V|v|5) PHASE_FILTER=5 ;;
  *) echo "ERROR --phase must be 1-5, I-V, or 'all' (got '${PHASE_FILTER}')" >&2; exit 2 ;;
esac

# ---------- triple-gate evaluation ----------
# Uses safe_apply.py evaluate_triple_gate when available; otherwise
# lightweight bash parity.
SOVEREIGN_OS_CONFIRM_DESTROY="${SOVEREIGN_OS_CONFIRM_DESTROY:-}"
GATE_APPLY="${APPLY}"
GATE_CONFIRM="${CONFIRM_APPLY}"
GATE_ENV="$([ "${SOVEREIGN_OS_CONFIRM_DESTROY}" = "YES" ] && echo 1 || echo 0)"

all_gates_ok=0
if [ "${GATE_APPLY}" -eq 1 ] && [ "${GATE_CONFIRM}" -eq 1 ] && [ "${GATE_ENV}" -eq 1 ]; then
  all_gates_ok=1
fi

# In apply mode but gates incomplete → emit plan + exit 2.
if [ "${APPLY}" -eq 1 ] && [ "${all_gates_ok}" -eq 0 ]; then
  {
    echo "═══ APPLY GATE FAILURE ═══"
    echo "  --apply requested but one or more gates are missing:"
    echo "    --apply              : $([ "${GATE_APPLY}" -eq 1 ] && echo yes || echo NO)"
    echo "    --confirm-apply      : $([ "${GATE_CONFIRM}" -eq 1 ] && echo yes || echo NO)"
    echo "    SOVEREIGN_OS_CONFIRM_DESTROY=YES : $([ "${GATE_ENV}" -eq 1 ] && echo yes || echo NO)"
    echo
    echo "  Re-run with all three gates to execute Phase ${PHASE_FILTER} artifacts on this host."
  } >&2
  exit 2
fi

# In apply mode with all gates: interactive confirmation (unless forced).
MODE="dry-run"
if [ "${APPLY}" -eq 1 ] && [ "${all_gates_ok}" -eq 1 ]; then
  if [ "${FORCE}" -eq 1 ]; then
    MODE="apply"
  elif confirm "Execute Phase ${PHASE_FILTER} artifacts on this host? This will modify system state." default-no; then
    MODE="apply"
  else
    echo "Apply aborted by operator (no changes made)." >&2
    exit 2
  fi
fi

# ---------- phase definitions ----------
# R202: canonical phase table lives in config/bootstrap/phases.yaml.
# Loader emits: id|name|description|artifact...
mapfile -t PHASES < <(${PYTHON3} "${__REPO_ROOT}/scripts/bootstrap/lib/load-phases.py")
if [ "${#PHASES[@]}" -eq 0 ]; then
  echo "ERROR phases.yaml loader returned empty table" >&2
  exit 2
fi

# ---------- artifact-kind classification ----------
# Returns one of:
#   build-step          — runs in the build container (forge), authoring-time
#   installer-hook      — runs during cloud-init / preseed install
#   post-install-hook   — runs after first boot (firstboot service)
#   recurrent-hook      — runs on a systemd timer (ongoing)
#   systemd-unit        — operator enables via systemctl
#   systemd-timer       — operator enables via systemctl
#   tooling             — python/shell helper invoked manually or by hooks
#   config              — declarative config consumed by the substrate
classify_artifact() {
  local path="$1"
  case "${path}" in
    scripts/build/*.sh)                    echo "build-step" ;;
    scripts/hooks/during-install/*.sh)     echo "installer-hook" ;;
    scripts/hooks/post-install/*.sh)       echo "post-install-hook" ;;
    scripts/hooks/recurrent/*.sh)          echo "recurrent-hook" ;;
    systemd/system/*.service)              echo "systemd-unit" ;;
    systemd/system/*.timer)                echo "systemd-timer" ;;
    scripts/*.py|scripts/*/*.py)           echo "tooling" ;;
    scripts/*/*.sh)                        echo "tooling" ;;
    config/*|profiles/*|whitelabel/*)      echo "config" ;;
    *)                                     echo "other" ;;
  esac
}

# ---------- apply helper ----------
# Executes an artifact based on its kind. Returns 0 on success, 1 on failure.
apply_artifact() {
  local path="$1" kind="$2"
  local fullpath="${__REPO_ROOT}/${path}"
  local rc=0

  case "${kind}" in
    systemd-unit)
      local unit_name
      unit_name="$(basename "${path}")"
      if command -v systemctl >/dev/null 2>&1; then
        echo "    [systemctl enable --now ${unit_name}]"
        if systemctl enable --now "${unit_name}" >/dev/null 2>&1; then
          echo "    ✓ ${unit_name} enabled + started"
        else
          echo "    ✗ systemctl enable --now ${unit_name} failed (rc=$?)" >&2
          rc=1
        fi
      else
        echo "    ✗ systemctl not available — cannot enable ${unit_name}" >&2
        rc=1
      fi
      ;;
    systemd-timer)
      local timer_name
      timer_name="$(basename "${path}")"
      if command -v systemctl >/dev/null 2>&1; then
        echo "    [systemctl enable --now ${timer_name}]"
        if systemctl enable --now "${timer_name}" >/dev/null 2>&1; then
          echo "    ✓ ${timer_name} enabled + started"
        else
          echo "    ✗ systemctl enable --now ${timer_name} failed (rc=$?)" >&2
          rc=1
        fi
      else
        echo "    ✗ systemctl not available — cannot enable ${timer_name}" >&2
        rc=1
      fi
      ;;
    post-install-hook|recurrent-hook)
      echo "    [bash ${path}]"
      if bash "${fullpath}"; then
        echo "    ✓ ${path} completed"
      else
        echo "    ✗ ${path} exited with rc=$?" >&2
        rc=1
      fi
      ;;
    installer-hook)
      echo "    ⊘ ${kind} skipped — runs during image install, not on a live host"
      ;;
    build-step)
      echo "    ⊘ ${kind} skipped — build-time only (run orchestrate.sh to rebuild image)"
      ;;
    tooling)
      echo "    ⊘ ${kind} skipped — manual invocation only"
      ;;
    config)
      echo "    ⊘ ${kind} skipped — declarative (consumed by substrate, not executed)"
      ;;
    other)
      echo "    ⊘ ${kind} skipped — unknown artifact kind"
      ;;
  esac
  return "${rc}"
}

# ---------- emit / apply ----------
overall_missing=0
overall_apply_failures=0

if [ "${JSON_OUT}" -eq 1 ]; then
  echo "{"
  echo "  \"mode\": \"${MODE}\","
  if [ "${MODE}" = "dry-run" ]; then
    echo "  \"safety_note\": \"R201 emits the execution plan only. --apply requires --confirm-apply + SOVEREIGN_OS_CONFIRM_DESTROY=YES + interactive confirm.\","
  else
    echo "  \"safety_note\": \"R201 apply mode — executing artifacts on this host.\","
  fi
  echo "  \"phases\": ["
fi

emitted_count=0
phase_idx=0
for phase_def in "${PHASES[@]}"; do
  phase_idx=$((phase_idx + 1))
  IFS='|' read -r -a parts <<< "${phase_def}"
  # R202: yaml format is id|name|description|artifact...
  name="${parts[0]}"
  desc="${parts[1]} (${parts[2]})"
  artifacts=("${parts[@]:3}")

  if [ "${PHASE_FILTER}" != "all" ] && [ "${PHASE_FILTER}" != "${phase_idx}" ]; then
    continue
  fi

  phase_missing=0
  phase_failures=0

  if [ "${JSON_OUT}" -eq 1 ]; then
    [ "${emitted_count}" -gt 0 ] && echo "    ,"
    echo "    {"
    echo "      \"phase\": \"${name}\","
    echo "      \"description\": $(${PYTHON3} -c "import json,sys; print(json.dumps('''${desc}'''))"),"
    echo "      \"plan\": ["
    for ((i=0;i<${#artifacts[@]};i++)); do
      a="${artifacts[$i]}"
      kind="$(classify_artifact "${a}")"
      status="present"
      apply_status=""
      if [ ! -e "${__REPO_ROOT}/${a}" ]; then
        status="missing"
        phase_missing=$((phase_missing + 1))
        overall_missing=$((overall_missing + 1))
      elif [ "${MODE}" = "apply" ]; then
        # Redirect apply_artifact stdout to stderr so JSON stays clean.
        if apply_artifact "${a}" "${kind}" >&2; then
          apply_status="applied"
        else
          apply_status="failed"
          phase_failures=$((phase_failures + 1))
          overall_apply_failures=$((overall_apply_failures + 1))
        fi
      fi
      sep=$([ $i -lt $((${#artifacts[@]} - 1)) ] && echo "," || echo "")
      if [ -n "${apply_status}" ]; then
        echo "        {\"artifact\": \"${a}\", \"kind\": \"${kind}\", \"status\": \"${status}\", \"apply_status\": \"${apply_status}\"}${sep}"
      else
        echo "        {\"artifact\": \"${a}\", \"kind\": \"${kind}\", \"status\": \"${status}\"}${sep}"
      fi
    done
    echo "      ],"
    if [ "${MODE}" = "apply" ]; then
      echo "      \"applied\": $((${#artifacts[@]} - phase_missing - phase_failures)),"
      echo "      \"apply_failures\": ${phase_failures},"
    else
      echo "      \"would_invoke\": ${#artifacts[@]},"
    fi
    echo "      \"artifacts_missing\": ${phase_missing}"
    echo "    }"
  else
    echo
    if [ "${MODE}" = "apply" ]; then
      echo "═══ Phase ${name} — APPLYING ═══"
    else
      echo "═══ Phase ${name} — execution plan (DRY-RUN) ═══"
    fi
    echo "  ${desc}"
    echo
    for a in "${artifacts[@]}"; do
      kind="$(classify_artifact "${a}")"
      if [ ! -e "${__REPO_ROOT}/${a}" ]; then
        printf '  [%-18s] MISSING:      %s\n' "${kind}" "${a}"
        phase_missing=$((phase_missing + 1))
        overall_missing=$((overall_missing + 1))
      elif [ "${MODE}" = "apply" ]; then
        printf '  [%-18s] applying:     %s\n' "${kind}" "${a}"
        if apply_artifact "${a}" "${kind}"; then
          :
        else
          phase_failures=$((phase_failures + 1))
          overall_apply_failures=$((overall_apply_failures + 1))
        fi
      else
        printf '  [%-18s] would invoke: %s\n' "${kind}" "${a}"
      fi
    done
    echo
    if [ "${MODE}" = "apply" ]; then
      applied_count=$(( ${#artifacts[@]} - phase_missing - phase_failures ))
      if [ "${phase_missing}" -eq 0 ] && [ "${phase_failures}" -eq 0 ]; then
        echo "  Phase ${name}: ✓ ${applied_count}/${#artifacts[@]} artifacts applied"
      else
        echo "  Phase ${name}: ${phase_missing} missing, ${phase_failures} failed — review above"
      fi
    else
      if [ "${phase_missing}" -eq 0 ]; then
        echo "  Phase ${name}: ✓ ${#artifacts[@]} artifacts plotted, ready for operator-driven apply on real hardware"
      else
        echo "  Phase ${name}: ${phase_missing} missing — plan incomplete"
      fi
    fi
  fi
  emitted_count=$((emitted_count + 1))
done

if [ "${JSON_OUT}" -eq 1 ]; then
  echo "  ],"
  if [ "${MODE}" = "apply" ]; then
    echo "  \"overall_missing\": ${overall_missing},"
    echo "  \"overall_apply_failures\": ${overall_apply_failures}"
  else
    echo "  \"overall_missing\": ${overall_missing}"
  fi
  echo "}"
else
  echo
  if [ "${MODE}" = "dry-run" ]; then
    echo "═══ DRY-RUN ONLY ═══"
    echo "  R201 emits the execution plan + classifies each artifact's runtime"
    echo "  surface (build-step / installer-hook / post-install-hook /"
    echo "  recurrent-hook / systemd-unit / tooling)."
    echo
    echo "  --apply requires all three gates:"
    echo "    1) --apply flag"
    echo "    2) --confirm-apply flag"
    echo "    3) SOVEREIGN_OS_CONFIRM_DESTROY=YES environment variable"
    echo
    echo "  Real execution lives at Layer 5 on the SAIN-01 box behind"
    echo "  interactive confirmation (or --force for unattended scripts)."
  else
    echo "═══ APPLY COMPLETE ═══"
    if [ "${overall_apply_failures}" -gt 0 ]; then
      echo "  ${overall_apply_failures} artifact(s) failed — review output above"
    fi
    if [ "${overall_missing}" -gt 0 ]; then
      echo "  ${overall_missing} artifact(s) missing — plan incomplete"
    fi
    if [ "${overall_apply_failures}" -eq 0 ] && [ "${overall_missing}" -eq 0 ]; then
      echo "  All artifacts applied successfully."
    fi
  fi
fi

if [ "${overall_missing}" -gt 0 ] || [ "${overall_apply_failures}" -gt 0 ]; then
  exit 1
fi
exit 0
