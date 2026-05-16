#!/usr/bin/env bash
# tests/nspawn/test_orchestrator_rewind_skip.sh
#
# Layer 3 test for Round 51 — orchestrator 'rewind' + 'skip' commands.
# Previously placeholder; now implemented.
#
# Asserts:
#   - rewind without arg → exit 2 + usage hint
#   - rewind with unknown step → exit 2 + valid list
#   - rewind with valid step → marks step + later steps pending
#     (state.yaml entries removed)
#   - skip without arg → exit 2 + usage hint
#   - skip with unknown step → exit 2 + valid list
#   - skip with valid step → marks step as completed without running

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

ORCH="${__REPO_ROOT}/scripts/build/orchestrate.sh"
[ -x "${ORCH}" ] || { echo "FAIL: orchestrator not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_orchestrator_rewind_skip.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_STATE_DIR="${tmp}/state"
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_PROFILE=sain-01

# ----------- rewind argument validation ---------------

set +e
out="$("${ORCH}" rewind 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage: orchestrate.sh rewind" <<< "${out}"; then
  ok "rewind without arg → exit 2 + usage hint"
else
  ko "rewind no-arg gate broken: rc=${rc} out=${out:0:200}"
fi

set +e
out="$("${ORCH}" rewind bogus-step 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown step: bogus-step" <<< "${out}"; then
  ok "rewind unknown-step → exit 2 + valid list"
else
  ko "rewind unknown-step gate broken: ${out:0:200}"
fi

# ----------- rewind valid step ---------------
# Pre-seed state.yaml with all 9 steps completed (simulate a real build)
mkdir -p "${SOVEREIGN_OS_STATE_DIR}"
state_file="${SOVEREIGN_OS_STATE_DIR}/state.yaml"
cat > "${state_file}" <<'EOF'
# sovereign-os build state
steps:
  01-bootstrap-forge:
    status: completed
    inputs_hash: "h01"
  02-kernel-fetch:
    status: completed
    inputs_hash: "h02"
  03-kernel-config:
    status: completed
    inputs_hash: "h03"
  04-kernel-compile:
    status: completed
    inputs_hash: "h04"
  05-substrate-prepare:
    status: completed
    inputs_hash: "h05"
  06-whitelabel-render:
    status: completed
    inputs_hash: "h06"
  07-image-build:
    status: completed
    inputs_hash: "h07"
  08-image-sign:
    status: completed
    inputs_hash: "h08"
  09-image-verify:
    status: completed
    inputs_hash: "h09"
EOF

set +e
out="$(SOVEREIGN_OS_ASSUME_YES=1 "${ORCH}" rewind 04-kernel-compile 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "rewound: 04-kernel-compile" <<< "${out}"; then
  ok "rewind 04-kernel-compile → marks step + later as pending"
else
  ko "rewind valid-step failed: rc=${rc} out=${out:0:300}"
fi

# Verify state — 01/02/03 still there; 04 through 09 removed
for kept in 01-bootstrap-forge 02-kernel-fetch 03-kernel-config; do
  if grep -q "^  ${kept}:" "${state_file}"; then
    ok "rewind: kept earlier step ${kept}"
  else
    ko "rewind: incorrectly removed ${kept}"
  fi
done

for removed in 04-kernel-compile 05-substrate-prepare 09-image-verify; do
  if ! grep -q "^  ${removed}:" "${state_file}"; then
    ok "rewind: removed step ${removed} (will re-run)"
  else
    ko "rewind: did NOT remove ${removed}"
  fi
done

# ----------- skip argument validation ---------------

set +e
out="$("${ORCH}" skip 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage: orchestrate.sh skip" <<< "${out}"; then
  ok "skip without arg → exit 2 + usage hint"
else
  ko "skip no-arg gate broken: ${out:0:200}"
fi

set +e
out="$("${ORCH}" skip bogus-step 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown step: bogus-step" <<< "${out}"; then
  ok "skip unknown-step → exit 2 + valid list"
else
  ko "skip unknown-step gate broken: ${out:0:200}"
fi

# ----------- skip valid step ---------------
# After rewind above, 04 onwards are pending. Skip 04.

set +e
out="$(SOVEREIGN_OS_ASSUME_YES=1 "${ORCH}" skip 04-kernel-compile 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "04-kernel-compile marked completed (skipped" <<< "${out}"; then
  ok "skip 04-kernel-compile → marks completed without running"
else
  ko "skip valid-step failed: rc=${rc} out=${out:0:300}"
fi

if grep -q "^  04-kernel-compile:" "${state_file}" \
   && grep -A2 "^  04-kernel-compile:" "${state_file}" | grep -q "status: completed"; then
  ok "skip: state.yaml shows 04 as completed"
else
  ko "skip: 04 state not completed: $(grep -A2 04-kernel-compile "${state_file}" 2>/dev/null)"
fi

if grep -A3 "^  04-kernel-compile:" "${state_file}" | grep -q "skipped-by-operator"; then
  ok "skip: sentinel inputs_hash 'skipped-by-operator' recorded"
else
  ko "skip: no sentinel inputs_hash"
fi

# ----------- help documents the new commands ---------------

help_out="$("${ORCH}" help 2>&1)"
if grep -q "rewind <step>" <<< "${help_out}" && grep -q "skip <step>" <<< "${help_out}"; then
  ok "help documents rewind + skip"
else
  ko "help missing rewind or skip"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_orchestrator_rewind_skip: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
