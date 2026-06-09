#!/usr/bin/env bash
# tests/nspawn/test_orchestrator_preflight.sh
#
# Layer 3 test for 'orchestrate.sh preflight' — pre-install lifecycle.
# Validates that all hooks in scripts/hooks/pre-install/ enumerate +
# run cleanly under SOVEREIGN_OS_DRY_RUN=1 against both profiles.
#
# Asserts:
#   - preflight discovers 4 hooks (friction-audit-spec + preflight-{network,storage,tpm})
#   - each hook reports PASS or SKIP under dry-run
#   - preflight exit code is 0 on clean dry-run
#   - preflight does not mutate state (no state.yaml written)
#   - preflight-tpm SKIPs on profiles where secure_boot != true
#   - --profile flag overrides env profile

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

ORCH="${__REPO_ROOT}/scripts/build/orchestrate.sh"
[ -x "${ORCH}" ] || { echo "FAIL: orchestrator not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_STATE_DIR="${tmp}/state"
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_DRY_RUN=1
export SOVEREIGN_OS_PROFILE="${1:-sain-01}"

echo "tests/nspawn/test_orchestrator_preflight.sh (profile=${SOVEREIGN_OS_PROFILE})"
echo

out="$("${ORCH}" preflight 2>&1)"
rc=$?

if [ "${rc}" -eq 0 ]; then
  ok "preflight exit code 0 (dry-run, clean)"
else
  ko "preflight exit code: ${rc}"
  echo "${out}" | tail -10
fi

# All 4 expected hooks must enumerate
for hook in friction-audit-spec preflight-network preflight-storage preflight-tpm; do
  if grep -q "→ ${hook}.sh" <<< "${out}"; then
    ok "hook enumerated: ${hook}"
  else
    ko "hook not enumerated: ${hook}"
  fi
done

# Summary line
if grep -qE "preflight: 4/4 hooks PASSED" <<< "${out}"; then
  ok "preflight summary: 4/4 PASSED"
else
  ko "preflight summary missing or wrong"
fi

# State preservation
if [ ! -e "${SOVEREIGN_OS_STATE_DIR}/state.yaml" ]; then
  ok "preflight did NOT create state.yaml (state preserved)"
else
  ko "preflight mutated state.yaml"
fi

# preflight-tpm must RUN its TPM/UEFI readiness checks for the signed/shim
# postures (SDD-015 enum), NOT skip. sain-01 = secure_boot=signed, so the TPM
# checks are required. (The old assertion expected a SKIP because the hook gated
# on the non-existent value 'true' — that pinned the bug where the preflight
# always skipped and secure-boot installs ran with no TPM validation.)
if grep -qE "secure_boot=signed.*TPM|TPM \+ UEFI readiness checks required" <<< "${out}"; then
  ok "preflight-tpm runs TPM+UEFI readiness checks for secure_boot=signed (SDD-015)"
else
  ko "preflight-tpm did not run TPM checks for the signed posture"
fi

# --profile flag override
rm -rf "${SOVEREIGN_OS_STATE_DIR}" "${SOVEREIGN_OS_LOG_DIR}"
other_profile="old-workstation"
[ "${SOVEREIGN_OS_PROFILE}" = "old-workstation" ] && other_profile="sain-01"
out2="$("${ORCH}" preflight --profile "${other_profile}" 2>&1)"
rc2=$?
if [ "${rc2}" -eq 0 ] && grep -q "loaded profile: ${other_profile}" <<< "${out2}"; then
  ok "--profile flag override works (switched to ${other_profile})"
else
  ko "--profile override failed: rc=${rc2}"
fi

# Unknown flag → exit 2
set +e
rm -rf "${SOVEREIGN_OS_STATE_DIR}" "${SOVEREIGN_OS_LOG_DIR}"
"${ORCH}" preflight --bogus-flag >/dev/null 2>&1
rc3=$?
set -e
if [ "${rc3}" -eq 2 ]; then
  ok "unknown preflight flag exits 2"
else
  ko "unknown preflight flag exit code: expected 2, got ${rc3}"
fi

# Help must document the new preflight command
help_out="$("${ORCH}" help 2>&1)"
if grep -q "preflight" <<< "${help_out}"; then
  ok "help documents 'preflight' command"
else
  ko "help missing 'preflight' command"
fi

echo
total=$((pass + fail))
echo "test_orchestrator_preflight: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
