#!/usr/bin/env bash
# tests/nspawn/test_onboard.sh
#
# Layer 3 test for scripts/onboard.sh (Round 138; F-08 HIGH closure).
# Verifies the fresh-machine onboarding wrapper produces the right state
# file + the right next-step output, end-to-end, in NONINTERACTIVE mode.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

ONBOARD="${__REPO_ROOT}/scripts/onboard.sh"

echo "tests/nspawn/test_onboard.sh"
echo

# Save + restore in-repo state file
state_file="${__REPO_ROOT}/.sovereign-os/init-state.yaml"
state_backup=""
if [ -f "${state_file}" ]; then
  state_backup="$(mktemp)"
  cp "${state_file}" "${state_backup}"
fi
trap '
  if [ -n "${state_backup}" ] && [ -f "${state_backup}" ]; then
    cp "${state_backup}" "${state_file}"
    rm -f "${state_backup}"
  else
    rm -f "${state_file}"
  fi
' EXIT

# ---------- onboard.sh exists + executable ----------
if [ -x "${ONBOARD}" ]; then
  ok "scripts/onboard.sh present + executable"
else
  ko "onboard.sh missing or not executable"
  exit 1
fi

# ---------- NONINTERACTIVE end-to-end run ----------
rm -f "${state_file}"
set +e
out="$(SOVEREIGN_OS_NONINTERACTIVE=1 \
       SOVEREIGN_OS_ONBOARD_SKIP_PREFLIGHT=1 \
       SOVEREIGN_OS_SETUP_SKIP_SMOKE=1 \
       SOVEREIGN_OS_SETUP_SKIP_HOOKS=1 \
       "${ONBOARD}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "NONINTERACTIVE end-to-end → exit 0"
else
  ko "end-to-end broken (rc=${rc})"
fi

# Three numbered stages surfaced
for stage in "1/3" "2/3" "3/3"; do
  if grep -q "\[${stage}\]" <<< "${out}"; then
    ok "stage ${stage} surfaced"
  else
    ko "stage ${stage} missing"
  fi
done

# init wizard invoked + state file written
if [ -f "${state_file}" ]; then
  ok "state file written by embedded init wizard"
else
  ko "state file NOT written"
fi

# Preflight skip respected
if grep -q "preflight.*SKIPPED" <<< "${out}"; then
  ok "preflight skip honored (SOVEREIGN_OS_ONBOARD_SKIP_PREFLIGHT=1)"
else
  ko "preflight skip not honored"
fi

# Next-steps block present
for next in "run --dry-run" "orchestrate.sh run" "install image --plan"; do
  if grep -q "${next}" <<< "${out}"; then
    ok "next-step: ${next}"
  else
    ko "next-step missing: ${next}"
  fi
done

# USEFUL OPERATOR VERBS section
for verb in "env list" "doctor" "alerts" "audit drift" "orchestrate.sh recover"; do
  if grep -q "${verb}" <<< "${out}"; then
    ok "useful-verbs: ${verb}"
  else
    ko "useful-verbs missing: ${verb}"
  fi
done

# Onboarding-complete marker
if grep -q "onboarding complete" <<< "${out}"; then
  ok "explicit 'onboarding complete' marker"
else
  ko "completion marker missing"
fi

# Idempotency
set +e
SOVEREIGN_OS_NONINTERACTIVE=1 \
  SOVEREIGN_OS_ONBOARD_SKIP_PREFLIGHT=1 \
  SOVEREIGN_OS_SETUP_SKIP_SMOKE=1 \
  SOVEREIGN_OS_SETUP_SKIP_HOOKS=1 \
  "${ONBOARD}" >/dev/null 2>&1
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "second run idempotent (re-runs cleanly)"
else
  ko "idempotency broken (rc=${rc})"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_onboard: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
