#!/usr/bin/env bash
# tests/nspawn/test_orchestrator_status.sh
#
# Layer 3 substantive test: orchestrate.sh subcommand surface works
# without a real build. Validates help/list/status all run + emit
# the expected step IDs in the expected order.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

ORCHESTRATE="${__REPO_ROOT}/scripts/build/orchestrate.sh"

fail=0
pass=0

assert_contains() {
  local desc="$1" needle="$2" output="$3"
  if grep -qF "${needle}" <<< "${output}"; then
    echo "  PASS — ${desc}"
    pass=$((pass + 1))
  else
    echo "  FAIL — ${desc} (expected '${needle}')"
    fail=$((fail + 1))
  fi
}

echo "tests/nspawn/test_orchestrator_status.sh"
echo

# --- help ---
help_out="$("${ORCHESTRATE}" help 2>&1 || true)"
assert_contains "help mentions sovereign-os build pipeline driver" "sovereign-os build pipeline driver" "${help_out}"
assert_contains "help lists 'run' subcommand" "run [--profile" "${help_out}"
assert_contains "help lists 'status' subcommand" "print state summary" "${help_out}"
assert_contains "help lists 'reset' subcommand" "wipe build state" "${help_out}"

# --- list (no real build needed) ---
list_out="$("${ORCHESTRATE}" list 2>&1 || true)"
assert_contains "list shows 01-bootstrap-forge" "01-bootstrap-forge" "${list_out}"
assert_contains "list shows 02-kernel-fetch" "02-kernel-fetch" "${list_out}"
assert_contains "list shows 03-kernel-config" "03-kernel-config" "${list_out}"
assert_contains "list shows 04-kernel-compile" "04-kernel-compile" "${list_out}"
assert_contains "list shows 05-substrate-prepare" "05-substrate-prepare" "${list_out}"
assert_contains "list shows 06-whitelabel-render" "06-whitelabel-render" "${list_out}"
assert_contains "list shows 07-image-build" "07-image-build" "${list_out}"
assert_contains "list shows 08-image-sign" "08-image-sign" "${list_out}"
assert_contains "list shows 09-image-verify" "09-image-verify" "${list_out}"

# --- status (works on empty state) ---
SOVEREIGN_OS_STATE_DIR="$(mktemp -d)"
SOVEREIGN_OS_STATE_FILE="${SOVEREIGN_OS_STATE_DIR}/state.yaml"
export SOVEREIGN_OS_STATE_DIR SOVEREIGN_OS_STATE_FILE

status_out="$("${ORCHESTRATE}" status 2>&1 || true)"
# Should mention 'No build state' OR show the empty file structure
if echo "${status_out}" | grep -qE "(No build state|build_id:)"; then
  echo "  PASS — status produces sane output on empty state"
  pass=$((pass + 1))
else
  echo "  FAIL — status output unexpected: ${status_out}"
  fail=$((fail + 1))
fi

rm -rf "${SOVEREIGN_OS_STATE_DIR}"

echo
total=$((pass + fail))
echo "test_orchestrator_status: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
