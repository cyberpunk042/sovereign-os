#!/usr/bin/env bash
# tests/nspawn/test_e2e_dry_run_smoke.sh
#
# Layer 3 end-to-end DRY-RUN smoke across ALL profiles. Ties the
# pipeline together: preflight → run --dry-run → decommission gates.
#
# Validates the operator's smoke-test workflow:
#   1. Operator picks a profile
#   2. Runs preflight (pre-install hooks) in DRY_RUN
#   3. Runs orchestrator run --dry-run (validates 9-step plan)
#   4. Verifies decommission gates refuse without confirm env
#
# All 5 profiles (sain-01, old-workstation, minimal, developer,
# headless) must pass this loop cleanly. Catches drift where a new
# profile or new step breaks the e2e flow.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

CTL="${__REPO_ROOT}/scripts/sovereign-osctl"
ORCH="${__REPO_ROOT}/scripts/build/orchestrate.sh"
[ -x "${ORCH}" ] || { echo "FAIL: orchestrator not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_e2e_dry_run_smoke.sh"
echo

PROFILES=(sain-01 old-workstation minimal developer headless)

for profile in "${PROFILES[@]}"; do
  echo "--- profile=${profile} ---"
  tmp="$(mktemp -d)"
  export SOVEREIGN_OS_STATE_DIR="${tmp}/state"
  export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
  export SOVEREIGN_OS_NONINTERACTIVE=1
  export SOVEREIGN_OS_PROFILE="${profile}"

  # Phase 1: preflight
  set +e
  out_pf="$(SOVEREIGN_OS_DRY_RUN=1 "${ORCH}" preflight 2>&1)"
  rc_pf=$?
  set -e
  if [ "${rc_pf}" -eq 0 ] && grep -q "preflight: 4/4 hooks PASSED" <<< "${out_pf}"; then
    ok "${profile}: preflight DRY-RUN passes all 4 hooks"
  else
    ko "${profile}: preflight failed rc=${rc_pf}"
  fi

  # Phase 2: orchestrator run --dry-run
  rm -rf "${SOVEREIGN_OS_STATE_DIR}"
  set +e
  out_run="$("${ORCH}" run --dry-run 2>&1)"
  rc_run=$?
  set -e
  if [ "${rc_run}" -eq 0 ] && grep -q "DRY-RUN complete: all 9 steps present + executable" <<< "${out_run}"; then
    ok "${profile}: 'run --dry-run' validates all 9 steps"
  else
    ko "${profile}: run --dry-run failed rc=${rc_run}"
  fi

  # Phase 3: state.yaml not touched by dry-run
  if [ ! -e "${SOVEREIGN_OS_STATE_DIR}/state.yaml" ]; then
    ok "${profile}: dry-run preserved state (no state.yaml written)"
  else
    ko "${profile}: dry-run leaked state.yaml"
  fi

  # Phase 4: profile validates against schema
  # Capture then grep (pipefail + grep -q SIGPIPE pattern — same one
  # the earlier rounds tripped on)
  validate_out="$("${__REPO_ROOT}/scripts/validate-profiles.sh" 2>&1)"
  if grep -q "PASS ${profile}" <<< "${validate_out}"; then
    ok "${profile}: schema-validates"
  else
    ko "${profile}: schema validation failed"
  fi

  # Phase 5: orchestrator list shows 9 steps for this profile too
  list_out="$("${ORCH}" list 2>&1)"
  step_count="$(echo "${list_out}" | grep -cE '^\s*0[1-9]-')"
  if [ "${step_count}" -eq 9 ]; then
    ok "${profile}: 'list' shows 9 ordered steps"
  else
    ko "${profile}: 'list' shows ${step_count} steps (expected 9)"
  fi

  rm -rf "${tmp}"
  echo
done

# ----------- decommission gates refuse without confirm env (any profile) ---------------

echo "--- decommission gates (cross-profile invariant) ---"
set +e
unset SOVEREIGN_OS_CONFIRM_DESTROY
SOVEREIGN_OS_PROFILE=sain-01 SOVEREIGN_OS_NONINTERACTIVE=1 \
  "${__REPO_ROOT}/scripts/hooks/decommission/zfs-pool-destroy.sh" >/dev/null 2>&1
rc=$?
set -e
if [ "${rc}" -ne 0 ]; then
  ok "decommission zfs-pool-destroy refuses without CONFIRM_DESTROY env"
else
  ko "decommission zfs-pool-destroy executed without confirm — destructive!"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_e2e_dry_run_smoke: ${pass}/${total} passed across $(( ${#PROFILES[@]} )) profiles"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
