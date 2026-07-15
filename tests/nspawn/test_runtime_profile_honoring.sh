#!/usr/bin/env bash
# tests/nspawn/test_runtime_profile_honoring.sh
#
# Layer 3 test for R151 — start scripts (start-pulse · start-logic-engine
# · start-oracle-core) honor the active runtime profile (master spec § 18)
# via lib/runtime-profile.sh.

set -euo pipefail

PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3=/usr/bin/python3
  fi
fi

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_runtime_profile_honoring.sh"
echo

# ---------- lib present + sourceable ----------
LIB="${__REPO_ROOT}/scripts/build/lib/runtime-profile.sh"
if [ -f "${LIB}" ]; then
  ok "runtime-profile.sh lib present"
else
  ko "lib missing"
  exit 1
fi

# Source it inside a subshell and verify the functions exist
if bash -c ". '${LIB}'; declare -F runtime_profile_active_file runtime_profile_get_tier_field runtime_profile_override runtime_profile_log_active" >/dev/null 2>&1; then
  ok "lib exports all 4 expected functions"
else
  ko "lib functions missing"
fi

# ---------- runtime_profile_get_tier_field ----------
# Backup any existing active-profile state
ACTIVE_BACKUP=""
if [ -f "${HOME}/.sovereign-os/active-runtime-profile" ]; then
  ACTIVE_BACKUP="$(mktemp)"
  cp "${HOME}/.sovereign-os/active-runtime-profile" "${ACTIVE_BACKUP}"
fi
trap '
  if [ -n "${ACTIVE_BACKUP}" ] && [ -f "${ACTIVE_BACKUP}" ]; then
    mkdir -p "${HOME}/.sovereign-os"
    cp "${ACTIVE_BACKUP}" "${HOME}/.sovereign-os/active-runtime-profile"
    rm -f "${ACTIVE_BACKUP}"
  else
    rm -f "${HOME}/.sovereign-os/active-runtime-profile"
  fi
' EXIT

# Set ultra-sovereign-efficiency as the active profile
mkdir -p "${HOME}/.sovereign-os"
echo "ultra-sovereign-efficiency" > "${HOME}/.sovereign-os/active-runtime-profile"

# Use SOVEREIGN_OS_RUNTIME_PROFILE env override so we're not subject to
# /etc/sovereign-os/active-runtime-profile potentially set by an
# earlier `sovereign-osctl trinity profile switch`. The lib gives env
# precedence over both /etc and ~/.

# get the pulse-tier core_mask
core_mask="$(SOVEREIGN_OS_RUNTIME_PROFILE=ultra-sovereign-efficiency bash -c ". '${LIB}'; runtime_profile_get_tier_field pulse core_mask")"
if [ "${core_mask}" = "0-7" ]; then
  ok "ultra-sovereign-efficiency pulse core_mask resolves to 0-7"
else
  ko "core_mask wrong: '${core_mask}'"
fi

# get the pulse-tier model
model="$(SOVEREIGN_OS_RUNTIME_PROFILE=ultra-sovereign-efficiency bash -c ". '${LIB}'; runtime_profile_get_tier_field pulse model")"
if [ "${model}" = "BitNet-b1.58-3B" ]; then
  ok "ultra-sovereign-efficiency pulse model resolves to BitNet-b1.58-3B"
else
  ko "model wrong: '${model}'"
fi

# Switch to high-concurrency-burst → pulse core_mask should be 0-11
core_mask="$(SOVEREIGN_OS_RUNTIME_PROFILE=high-concurrency-burst bash -c ". '${LIB}'; runtime_profile_get_tier_field pulse core_mask")"
if [ "${core_mask}" = "0-11" ]; then
  ok "high-concurrency-burst pulse core_mask resolves to 0-11"
else
  ko "switched core_mask wrong: '${core_mask}'"
fi

# Logic-tier model on high-concurrency-burst
logic_model="$(SOVEREIGN_OS_RUNTIME_PROFILE=high-concurrency-burst bash -c ". '${LIB}'; runtime_profile_get_tier_field logic model")"
if [ "${logic_model}" = "Qwen-32B-Ternary-Quant" ]; then
  ok "high-concurrency-burst logic model resolves to Qwen-32B-Ternary-Quant"
else
  ko "logic model wrong: '${logic_model}'"
fi

# Oracle-tier model
oracle_model="$(SOVEREIGN_OS_RUNTIME_PROFILE=high-concurrency-burst bash -c ". '${LIB}'; runtime_profile_get_tier_field oracle model")"
if [ "${oracle_model}" = "DeepSeek-R1-Distill-Llama-70B-FP16" ]; then
  ok "high-concurrency-burst oracle model resolves to DeepSeek-R1-..."
else
  ko "oracle model wrong: '${oracle_model}'"
fi

# Tier not present in profile → empty
ghost="$(SOVEREIGN_OS_RUNTIME_PROFILE=high-concurrency-burst bash -c ". '${LIB}'; runtime_profile_get_tier_field synthesizer no_such_field")"
if [ -z "${ghost}" ]; then
  ok "missing tier/field returns empty (no crash)"
else
  ko "ghost field returned non-empty: '${ghost}'"
fi

# ---------- runtime_profile_override behavior ----------
# When env var unset, override picks from active profile
unset MY_TEST_VAR
SOVEREIGN_OS_RUNTIME_PROFILE=high-concurrency-burst bash -c ". '${LIB}'; runtime_profile_override MY_TEST_VAR pulse core_mask; echo \"\${MY_TEST_VAR}\"" > /tmp/test-output-$$ 2>&1
out="$(cat /tmp/test-output-$$)"
rm -f /tmp/test-output-$$
if [ "${out}" = "0-11" ]; then
  ok "override sets unset env var from active profile"
else
  ko "override broken: got '${out}'"
fi

# When env var already set, override does NOT clobber
export MY_TEST_VAR="operator-explicit-value"
SOVEREIGN_OS_RUNTIME_PROFILE=high-concurrency-burst bash -c "MY_TEST_VAR='operator-explicit-value'; . '${LIB}'; runtime_profile_override MY_TEST_VAR pulse core_mask; echo \"\${MY_TEST_VAR}\"" > /tmp/test-output-$$ 2>&1
out="$(cat /tmp/test-output-$$)"
rm -f /tmp/test-output-$$
if [ "${out}" = "operator-explicit-value" ]; then
  ok "override respects operator-set env var (does NOT clobber)"
else
  ko "override clobbered operator value: '${out}'"
fi

# ---------- runtime_profile_active_file ----------
yaml_path="$(SOVEREIGN_OS_RUNTIME_PROFILE=high-concurrency-burst bash -c ". '${LIB}'; runtime_profile_active_file")"
if [ "${yaml_path}" = "${__REPO_ROOT}/profiles/runtime/high-concurrency-burst.yaml" ]; then
  ok "active_file resolves to the correct yaml path"
else
  ko "active_file wrong: '${yaml_path}'"
fi

# No active profile → exit non-zero
# Bypass /etc/sovereign-os and ~/.sovereign-os by setting env to a
# definitely-missing id (the lib still checks the YAML exists; missing → fail)
rm -f "${HOME}/.sovereign-os/active-runtime-profile"
set +e
yaml_path="$(SOVEREIGN_OS_RUNTIME_PROFILE=no-such-profile-xyz-9999 bash -c ". '${LIB}'; runtime_profile_active_file" 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && [ -z "${yaml_path}" ]; then
  ok "no active profile → empty output + non-zero rc"
else
  ko "no-active-profile broken: rc=${rc} out='${yaml_path}'"
fi

# ---------- start-pulse honors the runtime profile under DRY_RUN ----------
# In sandbox bitnet-cli isn't installed; the script logs "missing required
# command" and exits 1. We don't care about the exec — we care that
# (a) the affinity log line was emitted with the profile-resolved value
# and (b) the runtime-profile log header fired.

set +e
out="$(SOVEREIGN_OS_RUNTIME_PROFILE=ultra-sovereign-efficiency \
       PULSE_AFFINITY= \
       bash "${__REPO_ROOT}/scripts/inference/start-pulse.sh" 2>&1)"
set -e
if grep -q "CCD 0 cores 0-7" <<< "${out}" || grep -q "affinity: 0-7" <<< "${out}"; then
  ok "start-pulse picks PULSE_AFFINITY=0-7 from ultra-sovereign-efficiency"
else
  ko "start-pulse didn't honor profile: out=${out:0:300}"
fi
if grep -q "runtime profile:  ultra-sovereign-efficiency" <<< "${out}"; then
  ok "start-pulse logs active runtime profile in header"
else
  ko "start-pulse header missing runtime-profile log line; out=${out:0:200}"
fi

# Switch to high-concurrency-burst (pulse core_mask=0-11)
set +e
out="$(SOVEREIGN_OS_RUNTIME_PROFILE=high-concurrency-burst \
       PULSE_AFFINITY= \
       bash "${__REPO_ROOT}/scripts/inference/start-pulse.sh" 2>&1)"
set -e
if grep -q "0-11" <<< "${out}"; then
  ok "start-pulse re-resolves to 0-11 on profile switch"
else
  ko "start-pulse didn't pick up switched profile"
fi

# Operator-set env var wins over runtime profile
set +e
out="$(SOVEREIGN_OS_RUNTIME_PROFILE=high-concurrency-burst \
       PULSE_AFFINITY=2-3 \
       bash "${__REPO_ROOT}/scripts/inference/start-pulse.sh" 2>&1)"
set -e
if grep -q "2-3" <<< "${out}"; then
  ok "operator-set PULSE_AFFINITY wins over active runtime profile"
else
  ko "operator override didn't win"
fi

# ---------- SDD-043: tier_intent resolves to a concrete model at launch ----------
# A generated (intent-driven) profile has no literal `model`; the lib must
# resolve it via scripts/models/select-by-intent.py so start scripts work.
GEN="${__REPO_ROOT}/scripts/operator/generate-runtime-profile.py"
INTENT_YAML="${__REPO_ROOT}/profiles/runtime/_test_intent_honoring.yaml"
if [ -x "${GEN}" ]; then
  "${PYTHON3}" "${GEN}" --hardware sain-01 --strategy high-concurrency \
    --out "${INTENT_YAML}" --no-validate >/dev/null 2>&1 || true
  sed -i 's/^  id: .*/  id: _test_intent_honoring/' "${INTENT_YAML}" 2>/dev/null || true
  set +e
  resolved="$(bash -c ". '${LIB}'; SOVEREIGN_OS_RUNTIME_PROFILE=_test_intent_honoring \
    runtime_profile_get_tier_field oracle model" 2>/dev/null)"
  set -e
  rm -f "${INTENT_YAML}"
  if [ -n "${resolved}" ] && [[ "${resolved}" != *tier_intent* ]]; then
    ok "tier_intent oracle resolved to a concrete model at launch (${resolved})"
  else
    ko "tier_intent did not resolve to a model (got: '${resolved}')"
  fi
else
  ok "generator absent — tier_intent resolution test skipped"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_runtime_profile_honoring: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
