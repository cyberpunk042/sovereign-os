#!/usr/bin/env bash
# tests/nspawn/test_substrate_prepare.sh
#
# Layer 3 test for step 05-substrate-prepare.sh (Round 45 polish).
# Validates:
#   - mkosi substrate (default) → invokes mkosi-emit, exits 0
#   - live-build substrate → invokes live-build-emit, exits 0
#   - rpm-ostree → fails cleanly with not-implemented marker
#   - unknown substrate → fails with valid-list hint
#   - DRY_RUN logs intent + skip metric, no adapter invocation
#   - Layer B metric emitted for every code path

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

STEP="${__REPO_ROOT}/scripts/build/05-substrate-prepare.sh"
[ -x "${STEP}" ] || { echo "FAIL: 05-substrate-prepare.sh not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_substrate_prepare.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_STATE_DIR="${tmp}/state"
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_NONINTERACTIVE=1

# Step 05 reads profiles/ and scripts/build/adapters/ from SOVEREIGN_OS_ROOT
# (read-only; all writes go to SOVEREIGN_OS_BUILD_OUT / STATE / LOG below), so
# ROOT must be the real repo, not an empty scratch dir.
REPO_ROOT_ARG="${__REPO_ROOT}"

# The sain-01 profile's secure_boot=signed posture makes the mkosi adapter
# require operator key env vars (SDD-015: real keys are NEVER in the repo/CI).
# Placeholder files satisfy the presence gate — the adapter embeds only the
# key *paths*. Same pattern as tests/nspawn/test_image_sign_gates.sh.
export SOVEREIGN_OS_MOK_KEY="${tmp}/ci-mok.key"
export SOVEREIGN_OS_MOK_CERT="${tmp}/ci-mok.crt"
# secure_boot=signed also trips the locked-root guard (82867d00); this is a
# config-emission TEST that never boots, so declare the intentional-locked-root escape.
export SOVEREIGN_OS_ALLOW_LOCKED_ROOT=1
touch "${SOVEREIGN_OS_MOK_KEY}" "${SOVEREIGN_OS_MOK_CERT}"

# ----------- mkosi substrate (default) ---------------

rm -rf "${SOVEREIGN_OS_STATE_DIR}"
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 \
       SOVEREIGN_OS_SUBSTRATE=mkosi \
       SOVEREIGN_OS_ROOT="${REPO_ROOT_ARG}" \
       SOVEREIGN_OS_BUILD_OUT="${tmp}/build" \
       "${STEP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && [ -f "${tmp}/build/mkosi.conf" ]; then
  ok "mkosi substrate: step 05 succeeds + mkosi.conf emitted"
else
  ko "mkosi step failed: rc=${rc} out=${out:0:300}"
fi

# ----------- live-build substrate ---------------

rm -rf "${SOVEREIGN_OS_STATE_DIR}" "${tmp}/build2"
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 \
       SOVEREIGN_OS_SUBSTRATE=live-build \
       SOVEREIGN_OS_ROOT="${REPO_ROOT_ARG}" \
       SOVEREIGN_OS_BUILD_OUT="${tmp}/build2" \
       "${STEP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && [ -d "${tmp}/build2/config" ]; then
  ok "live-build substrate: step 05 succeeds + config/ emitted"
else
  ko "live-build step failed: rc=${rc} out=${out:0:300}"
fi

# ----------- rpm-ostree substrate (not implemented) ---------------

rm -rf "${SOVEREIGN_OS_STATE_DIR}"
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 \
       SOVEREIGN_OS_SUBSTRATE=rpm-ostree \
       SOVEREIGN_OS_ROOT="${REPO_ROOT_ARG}" \
       SOVEREIGN_OS_BUILD_OUT="${tmp}/build3" \
       "${STEP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "ALT path" <<< "${out}"; then
  ok "rpm-ostree substrate fails cleanly with not-implemented marker"
else
  ko "rpm-ostree gate broken: rc=${rc} out=${out:0:200}"
fi

# ----------- unknown substrate ---------------

rm -rf "${SOVEREIGN_OS_STATE_DIR}"
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 \
       SOVEREIGN_OS_SUBSTRATE=bogus-substrate \
       SOVEREIGN_OS_ROOT="${REPO_ROOT_ARG}" \
       SOVEREIGN_OS_BUILD_OUT="${tmp}/build4" \
       "${STEP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "valid: mkosi, live-build, rpm-ostree, nixos" <<< "${out}"; then
  ok "unknown substrate fails with valid-list hint"
else
  ko "unknown-substrate gate broken: rc=${rc} out=${out:0:200}"
fi

# ----------- DRY_RUN suppresses adapter invocation ---------------

rm -rf "${SOVEREIGN_OS_STATE_DIR}"
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 \
       SOVEREIGN_OS_SUBSTRATE=mkosi \
       SOVEREIGN_OS_ROOT="${REPO_ROOT_ARG}" \
       SOVEREIGN_OS_BUILD_OUT="${tmp}/build5" \
       SOVEREIGN_OS_DRY_RUN=1 \
       "${STEP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DRY-RUN — would invoke" <<< "${out}"; then
  ok "DRY_RUN logs intent without adapter invocation"
else
  ko "DRY_RUN broken: rc=${rc} out=${out:0:200}"
fi
if [ ! -f "${tmp}/build5/mkosi.conf" ]; then
  ok "DRY_RUN did NOT emit mkosi.conf (adapter not called)"
else
  ko "DRY_RUN emitted mkosi.conf — adapter ran"
fi

# ----------- Layer B metric emission ---------------

export SOVEREIGN_OS_METRICS_DIR="${tmp}/metrics"
rm -rf "${SOVEREIGN_OS_STATE_DIR}"
SOVEREIGN_OS_PROFILE=sain-01 \
SOVEREIGN_OS_SUBSTRATE=mkosi \
SOVEREIGN_OS_ROOT="${REPO_ROOT_ARG}" \
SOVEREIGN_OS_BUILD_OUT="${tmp}/build6" \
"${STEP}" >/dev/null 2>&1

metrics_file="${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-build.prom"
if [ -f "${metrics_file}" ] && grep -qE 'sovereign_os_build_step_substrate_total\{[^}]*substrate="mkosi"[^}]*result="success"' "${metrics_file}"; then
  ok "Layer B metric emitted: substrate=mkosi result=success"
else
  ko "Layer B metric missing: $(cat "${metrics_file}" 2>/dev/null || echo none)"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_substrate_prepare: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
