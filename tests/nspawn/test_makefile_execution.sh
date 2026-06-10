#!/usr/bin/env bash
# tests/nspawn/test_makefile_execution.sh
#
# Layer 3 test that ACTUALLY runs the Makefile targets end-to-end.
# Layer 1 lint (test_makefile_targets.py) checks shape; this test
# checks the targets actually execute and produce the documented
# outputs.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"
cd "${__REPO_ROOT}"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_makefile_execution.sh"
echo

# ----------- make help ---------------

out="$(make help 2>&1)"
if grep -q "sovereign-os operator Makefile" <<< "${out}"; then
  ok "make help emits banner"
else
  ko "make help banner missing"
fi

# ANSI color codes between target name and description; use grep -F
# for "Show this help" + verify a "help" appears earlier on the same line
if grep -F "Show this help" <<< "${out}" | grep -q "help"; then
  ok "make help lists 'help' target with description"
else
  ko "make help self-reference missing"
fi

# Profile enumeration: should pick up all 5 profiles
for p in sain-01 old-workstation minimal developer headless; do
  if grep -q "${p}" <<< "${out}"; then
    ok "make help enumerates profile: ${p}"
  else
    ko "make help missing profile: ${p}"
  fi
done

# ----------- make validate ---------------

set +e
out="$(make validate 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "PASS (5 profiles)" <<< "${out}"; then
  ok "make validate passes for all 5 profiles"
else
  ko "make validate failed: rc=${rc}"
fi

# ----------- make dry-run ---------------

set +e
out="$(make dry-run 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DRY-RUN complete: all 9 steps present + executable" <<< "${out}"; then
  ok "make dry-run validates all 9 build steps"
else
  ko "make dry-run failed: rc=${rc}"
fi

# ----------- make dry-run PROFILE override ---------------

set +e
out="$(make dry-run PROFILE=minimal 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "loaded profile: minimal" <<< "${out}"; then
  ok "make dry-run PROFILE=minimal honors the override"
else
  ko "PROFILE= override broken: rc=${rc}"
fi

# ----------- make lint ---------------

set +e
out="$(make lint 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -qE "passed" <<< "${out}"; then
  ok "make lint passes Layer 1"
else
  ko "make lint failed"
  # Without this, the only CI evidence is "make lint failed" — surface
  # WHICH tests broke (pytest prints FAILED lines + a summary tail).
  echo "  ---- make lint failure detail (rc=${rc}) ----"
  grep -E "FAILED|ERROR" <<< "${out}" | head -20 | sed 's/^/  | /'
  tail -5 <<< "${out}" | sed 's/^/  | /'
  echo "  ---- end detail ----"
fi

# ----------- make l3-fast (uses test_state_lib etc.) ---------------

set +e
out="$(make l3-fast 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "make l3-fast passes representative L3 sample"
else
  ko "make l3-fast failed"
fi

# ----------- make preflight ---------------

set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 make preflight 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "preflight: 4/4 hooks PASSED" <<< "${out}"; then
  ok "make preflight (DRY_RUN) passes all 4 pre-install hooks"
else
  ko "make preflight failed: rc=${rc}"
fi

# ----------- make help bare goal (default) ---------------

set +e
out="$(make 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "sovereign-os operator Makefile" <<< "${out}"; then
  ok "bare 'make' invokes help (default goal)"
else
  ko "bare make didn't show help (default goal broken)"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_makefile_execution: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
