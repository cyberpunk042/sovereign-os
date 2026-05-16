#!/usr/bin/env bash
# tests/nspawn/test_decommission_gates.sh
#
# Layer 3 test for the decommission lifecycle (Q-014 testing scope).
# Decommission scripts are inherently destructive and cannot be run
# safely in CI — but their GATES (require_root, SOVEREIGN_OS_CONFIRM_
# DESTROY=YES, interactive confirm) MUST hold or the operator can
# wipe their disk by accident. This test validates the gates without
# running the destructive code paths.
#
# Per SDD-014 (Q-014 resolution): we test what's testable without
# destruction — gate behavior, dispatch, and refusal modes.
#
# Asserts:
#   - secure-wipe-context.sh blocks when not root
#   - zfs-pool-destroy.sh blocks when not root
#   - zfs-pool-destroy.sh blocks when SOVEREIGN_OS_CONFIRM_DESTROY != YES
#   - secure-wipe.sh blocks when not root
#   - secure-wipe.sh blocks when SOVEREIGN_OS_CONFIRM_DESTROY != YES
#   - secure-wipe.sh blocks when SOVEREIGN_OS_WIPE_DEVICES is unset
#   - 'sovereign-osctl decommission start' aborts on confirm=no
#   - 'sovereign-osctl decommission <unknown>' exits 2
#   - 'sovereign-osctl decommission pool' without confirm aborts cleanly

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

CTL="${__REPO_ROOT}/scripts/sovereign-osctl"
[ -x "${CTL}" ] || { echo "FAIL: sovereign-osctl not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_decommission_gates.sh"
echo

# Force non-interactive so confirm calls don't hang the test
export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_PROFILE=sain-01

# Isolated log/state dirs (decommission scripts may try to log)
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_STATE_DIR="${tmp}/state"
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"

# Whether we're root — different assertions in each case
IS_ROOT=0
[ "$(id -u)" -eq 0 ] && IS_ROOT=1

# ----------- helper: run a script, capture exit code ---------------

run_rc() {
  set +e
  ( "$@" ) >/dev/null 2>&1
  echo $?
  set -e
}

# ----------- secure-wipe-context.sh ---------------

script="${__REPO_ROOT}/scripts/hooks/decommission/secure-wipe-context.sh"
[ -x "${script}" ] || { ko "secure-wipe-context.sh not executable"; exit 1; }
ok "secure-wipe-context.sh present + executable"

if [ "${IS_ROOT}" -eq 0 ]; then
  # As non-root: must block early at require_root (or at the confirm
  # if require_root is missing). Either way: non-zero exit.
  rc="$(run_rc "${script}")"
  if [ "${rc}" -ne 0 ]; then
    ok "secure-wipe-context.sh blocks when not root (rc=${rc})"
  else
    ko "secure-wipe-context.sh ran with rc=0 as non-root — gate failed"
  fi
else
  # As root: must still refuse without an interactive confirm or
  # with default-no + NONINTERACTIVE.
  rc="$(run_rc "${script}")"
  if [ "${rc}" -ne 0 ]; then
    ok "secure-wipe-context.sh blocks under SOVEREIGN_OS_NONINTERACTIVE (default-no confirm)"
  else
    ko "secure-wipe-context.sh proceeded under NONINTERACTIVE — destructive!"
  fi
fi

# ----------- zfs-pool-destroy.sh ---------------

script="${__REPO_ROOT}/scripts/hooks/decommission/zfs-pool-destroy.sh"
[ -x "${script}" ] || { ko "zfs-pool-destroy.sh not executable"; exit 1; }
ok "zfs-pool-destroy.sh present + executable"

if [ "${IS_ROOT}" -eq 0 ]; then
  rc="$(run_rc "${script}")"
  if [ "${rc}" -ne 0 ]; then
    ok "zfs-pool-destroy.sh blocks when not root"
  else
    ko "zfs-pool-destroy.sh ran as non-root — gate failed"
  fi
else
  # As root: must refuse without SOVEREIGN_OS_CONFIRM_DESTROY=YES
  unset SOVEREIGN_OS_CONFIRM_DESTROY
  rc="$(run_rc "${script}")"
  if [ "${rc}" -ne 0 ]; then
    ok "zfs-pool-destroy.sh refuses without SOVEREIGN_OS_CONFIRM_DESTROY=YES"
  else
    ko "zfs-pool-destroy.sh ran without confirm env-gate — destructive!"
  fi
fi

# ----------- secure-wipe.sh ---------------

script="${__REPO_ROOT}/scripts/hooks/decommission/secure-wipe.sh"
[ -x "${script}" ] || { ko "secure-wipe.sh not executable"; exit 1; }
ok "secure-wipe.sh present + executable"

if [ "${IS_ROOT}" -eq 0 ]; then
  rc="$(run_rc "${script}")"
  if [ "${rc}" -ne 0 ]; then
    ok "secure-wipe.sh blocks when not root"
  else
    ko "secure-wipe.sh ran as non-root — gate failed"
  fi
else
  # Refuse without confirm env
  unset SOVEREIGN_OS_CONFIRM_DESTROY
  rc="$(run_rc "${script}")"
  if [ "${rc}" -ne 0 ]; then
    ok "secure-wipe.sh refuses without SOVEREIGN_OS_CONFIRM_DESTROY=YES"
  else
    ko "secure-wipe.sh ran without confirm env-gate — destructive!"
  fi

  # Refuse without WIPE_DEVICES set
  export SOVEREIGN_OS_CONFIRM_DESTROY=YES
  unset SOVEREIGN_OS_WIPE_DEVICES
  rc="$(run_rc "${script}")"
  if [ "${rc}" -ne 0 ]; then
    ok "secure-wipe.sh refuses without SOVEREIGN_OS_WIPE_DEVICES set"
  else
    ko "secure-wipe.sh ran without WIPE_DEVICES — would wipe nothing or worse"
  fi
  unset SOVEREIGN_OS_CONFIRM_DESTROY
fi

# ----------- sovereign-osctl decommission dispatch ---------------

# Unknown subcommand → exit 2
set +e
"${CTL}" decommission definitely-not-a-real-subcommand >/dev/null 2>&1
rc=$?
set -e
if [ "${rc}" -eq 2 ]; then
  ok "'sovereign-osctl decommission <unknown>' exits 2"
else
  ko "'sovereign-osctl decommission <unknown>' exit code: expected 2, got ${rc}"
fi

# 'start' with default-no confirm in non-interactive mode must abort
# without running the wipe-context script. Whether it's blocked by
# require_root or by confirm doesn't matter — the outcome is the same:
# nothing destructive happened.
set +e
out="$("${CTL}" decommission start 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] || grep -qE "aborted|wipe aborted" <<< "${out}"; then
  ok "'sovereign-osctl decommission start' aborts gracefully under NONINTERACTIVE"
else
  ko "decommission start did NOT abort: rc=${rc} out=${out:0:200}"
fi

# 'pool' without confirm must not destroy anything
set +e
out="$("${CTL}" decommission pool 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ]; then
  ok "'sovereign-osctl decommission pool' refuses without confirm env"
else
  ko "decommission pool ran without confirm — destructive!"
fi

# 'wipe' without confirm or devices must refuse
set +e
unset SOVEREIGN_OS_WIPE_DEVICES SOVEREIGN_OS_CONFIRM_DESTROY
"${CTL}" decommission wipe >/dev/null 2>&1
rc=$?
set -e
if [ "${rc}" -ne 0 ]; then
  ok "'sovereign-osctl decommission wipe' refuses without env-gates"
else
  ko "decommission wipe ran without gates"
fi

# ----------- help documents decommission ---------------

if "${CTL}" help 2>&1 | grep -q "decommission"; then
  ok "help documents 'decommission' command"
else
  ko "help missing 'decommission'"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_decommission_gates: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
