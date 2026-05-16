#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_assistant.sh
#
# Layer 3 test for `sovereign-osctl assistant` (Round 67 — expanded
# from single-verb 'full' to 4-subverb surface).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

CTL="${__REPO_ROOT}/scripts/sovereign-osctl"
[ -x "${CTL}" ] || { echo "FAIL: sovereign-osctl not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_sovereign_osctl_assistant.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_PROFILE=sain-01
export SOVEREIGN_OS_ASSISTANT_STATE_DIR="${tmp}/assistant"
export SOVEREIGN_OS_STATE_DIR="${tmp}/state"
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"

# ----------- assistant list ---------------

out="$("${CTL}" assistant list 2>&1)"
for v in full status reset list; do
  if grep -qE "^\s+${v}\s" <<< "${out}"; then
    ok "assistant list documents: ${v}"
  else
    ko "assistant list missing: ${v}"
  fi
done

# ----------- assistant status — not yet run ---------------

out="$("${CTL}" assistant status 2>&1)"
if grep -q "has not been run yet" <<< "${out}"; then
  ok "assistant status reports 'not yet run' when state absent"
else
  ko "assistant status fresh-state output unexpected: ${out:0:200}"
fi

# ----------- assistant full → runs the underlying flow ---------------

set +e
out="$("${CTL}" assistant full 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "Welcome to sovereign-os" <<< "${out}"; then
  ok "assistant full invokes the first-login flow (sees welcome banner)"
else
  ko "assistant full broken: rc=${rc} out=${out:0:300}"
fi

# ----------- assistant status — after run ---------------

if [ -f "${SOVEREIGN_OS_ASSISTANT_STATE_DIR}/state.yaml" ]; then
  ok "first-login flow wrote state.yaml"
else
  ko "first-login flow did not write state"
fi

out="$("${CTL}" assistant status 2>&1)"
if grep -q "completed: true" <<< "${out}"; then
  ok "assistant status shows completed: true"
else
  ko "assistant status didn't surface state: ${out:0:200}"
fi

# ----------- assistant reset (ASSUME_YES) ---------------

set +e
out="$(SOVEREIGN_OS_ASSUME_YES=1 "${CTL}" assistant reset 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "assistant state cleared" <<< "${out}"; then
  ok "assistant reset (ASSUME_YES) clears state"
else
  ko "assistant reset broken: rc=${rc}"
fi

if [ ! -f "${SOVEREIGN_OS_ASSISTANT_STATE_DIR}/state.yaml" ]; then
  ok "state.yaml absent after reset"
else
  ko "state.yaml still present after reset"
fi

# ----------- assistant reset (no confirm under NONINTERACTIVE) ---------------
# Re-create state, then attempt reset WITHOUT ASSUME_YES
touch "${SOVEREIGN_OS_ASSISTANT_STATE_DIR}/state.yaml"

set +e
out="$("${CTL}" assistant reset 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "reset cancelled" <<< "${out}"; then
  ok "assistant reset without ASSUME_YES refuses cleanly under NONINTERACTIVE"
else
  ko "assistant reset no-confirm path broken: rc=${rc}"
fi

[ -f "${SOVEREIGN_OS_ASSISTANT_STATE_DIR}/state.yaml" ] \
  && ok "assistant reset refusal preserved state.yaml" \
  || ko "assistant reset destroyed state despite refusal"

# ----------- unknown subverb ---------------

set +e
"${CTL}" assistant totally-bogus >/dev/null 2>&1
rc=$?
set -e
if [ "${rc}" -eq 2 ]; then
  ok "unknown assistant subverb exits 2"
else
  ko "unknown subverb exit ${rc}"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_sovereign_osctl_assistant: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
