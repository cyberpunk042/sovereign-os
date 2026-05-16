#!/usr/bin/env bash
# tests/nspawn/test_kernel_step_short_circuit.sh
#
# Layer 3 test for Q18-A — steps 02/03/04 short-circuit when
# profile.kernel.source is substrate-default. Verifies:
#   - all 3 substrate-default profiles (old-workstation/minimal/
#     developer/headless) cause steps 02/03/04 to exit 0 with a
#     "skipping (substrate-default)" log message
#   - sain-01 (kernel.source=kernel.org-stable) progresses past the
#     short-circuit guard (and then fails on require_dir / require_command
#     in CI — that's expected and the gate's correct fall-through)
#
# Catches a regression where a substrate-default profile would
# accidentally try to clone kernel.org / compile a kernel.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_kernel_step_short_circuit.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_STATE_DIR="${tmp}/state"
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_NONINTERACTIVE=1

run_capture() {
  set +e
  out="$( ( "$@" ) 2>&1 )"
  rc=$?
  set -e
  printf '%s\n' "${out}"
  return "${rc}"
}

for step in 02-kernel-fetch 03-kernel-config 04-kernel-compile; do
  script="${__REPO_ROOT}/scripts/build/${step}.sh"
  [ -x "${script}" ] || { ko "${step}.sh not executable"; continue; }

  for profile in old-workstation minimal developer headless; do
    set +e
    out="$(SOVEREIGN_OS_PROFILE="${profile}" "${script}" 2>&1)"
    rc=$?
    set -e
    if [ "${rc}" -eq 0 ] && grep -q "substrate-default" <<< "${out}"; then
      ok "${step} short-circuits cleanly for ${profile} (kernel.source=substrate-default)"
    else
      ko "${step} did NOT short-circuit for ${profile}: rc=${rc} out=${out:0:200}"
    fi
  done

  # sain-01 has kernel.source=kernel.org-stable — must NOT short-circuit.
  # In CI we expect it to advance past the guard and then fail on
  # missing forge dir / tooling — that's the correct behavior.
  set +e
  out="$(SOVEREIGN_OS_PROFILE=sain-01 "${script}" 2>&1)"
  rc=$?
  set -e
  if grep -q "substrate-default" <<< "${out}"; then
    ko "${step} incorrectly short-circuited for sain-01 (kernel.org-stable)"
  else
    ok "${step} progresses past short-circuit for sain-01 (kernel.org-stable)"
  fi
done

echo
total=$((pass + fail))
echo "test_kernel_step_short_circuit: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
