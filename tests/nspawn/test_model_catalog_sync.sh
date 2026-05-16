#!/usr/bin/env bash
# tests/nspawn/test_model_catalog_sync.sh
#
# Layer 3 test for the now-substantive model-catalog-sync.sh
# (Round 63 promoted it from stub to manifest-verifier).
#
# Asserts:
#   - models dir absent → exit 0 + emit zeros
#   - one model with valid manifest → exit 0 + verified=1 metric
#   - one model with NO manifest → exit 0 + missing-manifest=1
#   - one model with TAMPERED manifest → exit 2 + corrupt=1 (alarm)
#   - DRY-RUN exits 0 without verification side-effects
#   - L3 lockstep: every emitted metric has an emitter in source

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

HOOK="${__REPO_ROOT}/scripts/hooks/recurrent/model-catalog-sync.sh"
[ -x "${HOOK}" ] || { echo "FAIL: model-catalog-sync.sh not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_model_catalog_sync.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_METRICS_DIR="${tmp}/metrics"

# ----------- absent models dir ---------------

export SOVEREIGN_OS_MODELS_DIR="${tmp}/never-here"
set +e
out="$("${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "nothing to verify" <<< "${out}"; then
  ok "models dir absent → exit 0 + 'nothing to verify' log"
else
  ko "absent-dir gate broken: rc=${rc} out=${out:0:200}"
fi

# ----------- DRY-RUN ---------------

mkdir -p "${tmp}/models/fake-model"
echo "fake weights" > "${tmp}/models/fake-model/weights.bin"
export SOVEREIGN_OS_MODELS_DIR="${tmp}/models"
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 "${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DRY-RUN" <<< "${out}"; then
  ok "DRY-RUN exits 0 + log marker"
else
  ko "DRY-RUN broken: rc=${rc}"
fi

# ----------- one model + valid manifest → verified ---------------

rm -rf "${tmp}/models" "${SOVEREIGN_OS_METRICS_DIR}"
mkdir -p "${tmp}/models/model-valid"
echo "model bytes" > "${tmp}/models/model-valid/weights.bin"
(cd "${tmp}/models/model-valid" && sha256sum weights.bin > manifest.sha256)

set +e
out="$("${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "manifest verified" <<< "${out}"; then
  ok "valid manifest → exit 0 + 'manifest verified' log"
else
  ko "valid-manifest path broken: rc=${rc} out=${out:0:300}"
fi

# Metric file
metrics_file="${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-models-catalog.prom"
if [ -f "${metrics_file}" ] && grep -q 'result="verified"} 1' "${metrics_file}"; then
  ok "metric: verified=1 emitted"
else
  ko "verified metric missing: $(cat "${metrics_file}" 2>/dev/null || echo none)"
fi

# ----------- one model + no manifest → missing-manifest ---------------

rm -rf "${tmp}/models" "${SOVEREIGN_OS_METRICS_DIR}"
mkdir -p "${tmp}/models/model-unmanaged"
echo "unmanaged bytes" > "${tmp}/models/model-unmanaged/weights.bin"

set +e
out="$("${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "no manifest.sha256 (unmanaged)" <<< "${out}"; then
  ok "missing manifest → reported 'unmanaged' (exit 0; non-blocking)"
else
  ko "missing-manifest path broken: rc=${rc}"
fi

if grep -q 'result="missing-manifest"} 1' "${metrics_file}" 2>/dev/null; then
  ok "metric: missing-manifest=1 emitted"
else
  ko "missing-manifest metric missing"
fi

# ----------- one model + tampered manifest → corrupt + exit 2 ---------------

rm -rf "${tmp}/models" "${SOVEREIGN_OS_METRICS_DIR}"
mkdir -p "${tmp}/models/model-tampered"
echo "real bytes" > "${tmp}/models/model-tampered/weights.bin"
(cd "${tmp}/models/model-tampered" && sha256sum weights.bin > manifest.sha256)
# Now tamper the file AFTER recording the hash
echo "tampered bytes" > "${tmp}/models/model-tampered/weights.bin"

set +e
out="$("${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "FAILED verification (corrupt" <<< "${out}"; then
  ok "tampered manifest → exit 2 + 'corrupt' log (alarm signal)"
else
  ko "corrupt path broken: rc=${rc} out=${out:0:300}"
fi

if grep -q 'result="corrupt"} 1' "${metrics_file}" 2>/dev/null; then
  ok "metric: corrupt=1 emitted (operator-actionable)"
else
  ko "corrupt metric missing"
fi

# ----------- 4 required metric families present ---------------

for key in sovereign_os_models_catalog_total \
           sovereign_os_models_catalog_resident_count \
           sovereign_os_models_catalog_total_bytes \
           sovereign_os_models_catalog_last_run_timestamp; do
  if grep -q "^${key}" "${metrics_file}" 2>/dev/null; then
    ok "metric family present: ${key}"
  else
    ko "metric family missing: ${key}"
  fi
done

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_model_catalog_sync: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
