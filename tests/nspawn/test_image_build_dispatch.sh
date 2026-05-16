#!/usr/bin/env bash
# tests/nspawn/test_image_build_dispatch.sh
#
# Layer 3 test for step 07-image-build.sh (Round 46 — live-build runner
# added; DRY_RUN moved up; Layer B metric).
#
# Validates dispatch + DRY_RUN + metric emission without actually
# invoking mkosi/lb (neither is in CI).
#
# Asserts:
#   - mkosi DRY_RUN → exits 0 + emits skip metric
#   - live-build DRY_RUN → exits 0 + emits skip metric (Round 46 fix —
#     was 'not-implemented' before)
#   - rpm-ostree → fails with not-implemented marker
#   - unknown substrate → fails

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

STEP="${__REPO_ROOT}/scripts/build/07-image-build.sh"
[ -x "${STEP}" ] || { echo "FAIL: 07-image-build.sh not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_image_build_dispatch.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_STATE_DIR="${tmp}/state"
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_DRY_RUN=1
export SOVEREIGN_OS_METRICS_DIR="${tmp}/metrics"

setup_env_substrate() {
  local substrate="$1" build_out="$2"
  mkdir -p "${SOVEREIGN_OS_STATE_DIR}" "${build_out}"
  cat > "${SOVEREIGN_OS_STATE_DIR}/env-substrate.sh" <<EOF
export SOVEREIGN_OS_SUBSTRATE="${substrate}"
export SOVEREIGN_OS_BUILD_OUT="${build_out}"
EOF
}

# ----------- mkosi DRY_RUN ---------------

setup_env_substrate mkosi "${tmp}/build-mkosi"
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 "${STEP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "skipping 'mkosi build'" <<< "${out}"; then
  ok "mkosi DRY_RUN: exit 0 + 'skipping mkosi build' log"
else
  ko "mkosi DRY_RUN broken: rc=${rc} out=${out:0:300}"
fi

# ----------- live-build DRY_RUN (Round 46 fix) ---------------

rm -rf "${SOVEREIGN_OS_STATE_DIR}"
setup_env_substrate live-build "${tmp}/build-lb"
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 "${STEP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "skipping 'lb build'" <<< "${out}"; then
  ok "live-build DRY_RUN: exit 0 + 'skipping lb build' log (Round 46 — was not-implemented before)"
else
  ko "live-build DRY_RUN broken: rc=${rc} out=${out:0:300}"
fi

# ----------- rpm-ostree → not implemented ---------------

rm -rf "${SOVEREIGN_OS_STATE_DIR}"
setup_env_substrate rpm-ostree "${tmp}/build-rpm"
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 "${STEP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "not yet implemented" <<< "${out}"; then
  ok "rpm-ostree fails with not-implemented marker"
else
  ko "rpm-ostree gate broken: rc=${rc}"
fi

# ----------- unknown substrate ---------------

rm -rf "${SOVEREIGN_OS_STATE_DIR}"
setup_env_substrate bogus "${tmp}/build-bogus"
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 "${STEP}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "unknown substrate" <<< "${out}"; then
  ok "unknown substrate fails with clear error"
else
  ko "unknown-substrate gate broken: rc=${rc}"
fi

# ----------- Layer B metrics — verify emit_metric was invoked ---------------
# Under DRY_RUN, emit_metric logs 'would emit:' instead of writing the
# .prom file (per emit_metric's own DRY_RUN semantics). Run a fresh
# substrate dispatch with DRY_RUN=1 and capture stdout to verify the
# emit call fired.

for combo in "mkosi:skip" "live-build:skip" "rpm-ostree:not-implemented" "bogus:unknown"; do
  substrate="${combo%%:*}"
  result="${combo##*:}"
  rm -rf "${SOVEREIGN_OS_STATE_DIR}"
  setup_env_substrate "${substrate}" "${tmp}/build-${substrate}-m"
  set +e
  out_m="$(SOVEREIGN_OS_PROFILE=sain-01 "${STEP}" 2>&1)"
  set -e
  if grep -qE "would emit:.*sovereign_os_build_step_image_build_total\{[^}]*substrate=\"${substrate}\"[^}]*result=\"${result}\"" <<< "${out_m}"; then
    ok "metric emit called: substrate=${substrate} result=${result}"
  else
    ko "metric emit missing for substrate=${substrate} result=${result}"
  fi
done

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_image_build_dispatch: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
