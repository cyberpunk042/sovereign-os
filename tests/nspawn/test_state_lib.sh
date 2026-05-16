#!/usr/bin/env bash
# tests/nspawn/test_state_lib.sh
#
# Substantive Layer 3 test for scripts/build/lib/state.sh — the
# IaC-bar restart-from-state library. Tests in isolation with a
# tmpdir-backed state file so the real build state is untouched.
#
# Validates:
#   - state_init creates the YAML state file with required keys
#   - state_step_start writes a 'running' entry
#   - state_step_complete updates status: running → completed +
#     adds completed_at timestamp
#   - state_step_fail updates status: running → failed + error
#   - state_step_status returns the right verb for each transition
#   - state_step_should_run returns 0 (run) for pending/different-hash
#     and non-zero (skip) for completed-with-same-hash
#   - state_inputs_hash is deterministic for the same input
#   - state_reset wipes + re-initializes
#   - state_summary produces operator-readable output

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

# Isolate from real build state
export SOVEREIGN_OS_STATE_DIR="$(mktemp -d)"
export SOVEREIGN_OS_STATE_FILE="${SOVEREIGN_OS_STATE_DIR}/state.yaml"
export SOVEREIGN_OS_BUILD_ID="test-$(date -u +%s)"
trap 'rm -rf "${SOVEREIGN_OS_STATE_DIR}"' EXIT

# Source the libs (state + logging needed for log_info etc.)
# shellcheck source=../../scripts/build/lib/logging.sh
. "${__REPO_ROOT}/scripts/build/lib/logging.sh"
# shellcheck source=../../scripts/build/lib/state.sh
. "${__REPO_ROOT}/scripts/build/lib/state.sh"

fail=0
pass=0

ok() {
  echo "  PASS — $1"
  pass=$((pass + 1))
}
ko() {
  echo "  FAIL — $1"
  fail=$((fail + 1))
}

echo "tests/nspawn/test_state_lib.sh"
echo "  state file: ${SOVEREIGN_OS_STATE_FILE}"
echo

# --- state_init ---
state_init
if [ -f "${SOVEREIGN_OS_STATE_FILE}" ]; then
  ok "state_init creates state file"
else
  ko "state_init did not create state file"
fi
grep -q "build_id:" "${SOVEREIGN_OS_STATE_FILE}" && ok "state file has build_id key" || ko "state file missing build_id"
grep -q "steps: {}" "${SOVEREIGN_OS_STATE_FILE}" && ok "state file initializes steps as empty map" || ko "steps not initialized empty"

# --- state_inputs_hash determinism ---
h1="$(state_inputs_hash "${BASH_SOURCE[0]}")"
h2="$(state_inputs_hash "${BASH_SOURCE[0]}")"
if [ "$h1" = "$h2" ] && [ -n "$h1" ]; then
  ok "state_inputs_hash is deterministic"
else
  ko "state_inputs_hash drift: '$h1' vs '$h2'"
fi

# --- state_step_start ---
state_step_start "test-step-1" "deadbeef"
status="$(state_step_status test-step-1)"
if [ "${status}" = "running" ]; then
  ok "state_step_start sets status=running"
else
  ko "after state_step_start, status='${status}' (want 'running')"
fi
grep -q 'inputs_hash: "deadbeef"' "${SOVEREIGN_OS_STATE_FILE}" \
  && ok "state file records inputs_hash" \
  || ko "inputs_hash not recorded"

# --- state_step_should_run: pending → 0; running → 0 (treats running as pending) ---
if state_step_should_run test-step-1 "deadbeef"; then
  ok "should_run returns 0 (run) for running-with-same-hash"
else
  ko "should_run should return 0 for running (not yet completed)"
fi

# Different step (not started) → 0 (run)
if state_step_should_run never-started "abc"; then
  ok "should_run returns 0 (run) for unknown step"
else
  ko "should_run should return 0 for unknown step"
fi

# --- state_step_complete ---
state_step_complete "test-step-1"
status="$(state_step_status test-step-1)"
if [ "${status}" = "completed" ]; then
  ok "state_step_complete transitions status to completed"
else
  ko "after state_step_complete, status='${status}' (want 'completed')"
fi
grep -q "completed_at:" "${SOVEREIGN_OS_STATE_FILE}" \
  && ok "state file records completed_at timestamp" \
  || ko "completed_at not recorded"

# --- should_run after complete with same hash → 1 (skip) ---
if state_step_should_run test-step-1 "deadbeef"; then
  ko "should_run should return 1 (skip) for completed-with-same-hash"
else
  ok "should_run returns 1 (skip) for completed-with-same-hash"
fi

# --- should_run after complete with DIFFERENT hash → 0 (rerun) ---
if state_step_should_run test-step-1 "different-hash"; then
  ok "should_run returns 0 (rerun) when inputs change"
else
  ko "should_run should return 0 when inputs change (force rerun)"
fi

# --- state_step_fail ---
state_step_start "test-step-2" "feedface"
state_step_fail "test-step-2" "synthetic-error-for-test"
status="$(state_step_status test-step-2)"
if [ "${status}" = "failed" ]; then
  ok "state_step_fail transitions status to failed"
else
  ko "after state_step_fail, status='${status}' (want 'failed')"
fi
grep -q "synthetic-error-for-test" "${SOVEREIGN_OS_STATE_FILE}" \
  && ok "state file records error message" \
  || ko "error message not recorded"

# --- state_reset ---
state_reset
status="$(state_step_status test-step-1)"
if [ "${status}" = "pending" ]; then
  ok "state_reset wipes prior step records (test-step-1 back to pending)"
else
  ko "state_reset failed; test-step-1 still '${status}'"
fi
[ -f "${SOVEREIGN_OS_STATE_FILE}" ] \
  && ok "state_reset re-initializes the file (not just deletes)" \
  || ko "state_reset left no state file"

# --- state_summary ---
state_init
state_step_start "demo" "x"
state_step_complete "demo"
summary="$(state_summary)"
if grep -q "Build state at" <<< "${summary}" && grep -q "demo:" <<< "${summary}"; then
  ok "state_summary emits operator-readable output with step entries"
else
  ko "state_summary output unexpected: ${summary}"
fi

echo
total=$((pass + fail))
echo "test_state_lib: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
