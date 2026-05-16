#!/usr/bin/env bash
# tests/nspawn/test_pulse_wasm_aot.sh
#
# Layer 3 test for R153 — scripts/pulse/wasm-aot.sh.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/pulse/wasm-aot.sh"

echo "tests/nspawn/test_pulse_wasm_aot.sh"
echo

if [ -x "${SCRIPT}" ]; then
  ok "wasm-aot.sh present + executable"
else
  ko "missing/not executable"; exit 1
fi

# ---------- DRY-RUN ----------
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 bash "${SCRIPT}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "DRY-RUN exit 0" || ko "DRY-RUN broken (rc=${rc})"

# Master spec § 20 citation in DRY-RUN output
for kw in "master spec § 20" "znver5" "wasmtime compile" "WASMTIME_COMPARE_OPTIONS" "relaxed-simd=true"; do
  if grep -q "${kw}" <<< "${out}"; then
    ok "DRY-RUN surfaces: ${kw}"
  else
    ko "DRY-RUN missing: ${kw}"
  fi
done

# Affinity = 0-11 (master spec § 19.2 CCD0+CCD1 cores 0-9 for Pulse+Weaver concurrent compile)
if grep -q "0-11" <<< "${out}"; then
  ok "DRY-RUN cites CCD pinning 0-11"
else
  ko "CCD pinning missing"
fi

# ---------- env vars honored ----------
set +e
out="$(WASM_TARGET_CPU=znver4 \
       WASM_AFFINITY=2-3 \
       WASM_OPT_LEVEL=size \
       SOVEREIGN_OS_DRY_RUN=1 \
       bash "${SCRIPT}" 2>&1)"
set -e
for kw in "znver4" "2-3" "size"; do
  if grep -q "${kw}" <<< "${out}"; then
    ok "env override honored: ${kw}"
  else
    ko "env override missing: ${kw}"
  fi
done

# ---------- input check ----------
# When WASM_INPUT doesn't exist AND not DRY-RUN, should fail with clear error
set +e
out="$(WASM_INPUT=/tmp/no-such.wasm bash "${SCRIPT}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "input wasm not found" <<< "${out}"; then
  ok "missing WASM_INPUT → fail + clear error"
else
  # wasmtime missing might fire first — accept that path too
  if grep -q "wasmtime not installed" <<< "${out}"; then
    ok "no wasmtime → fail + clear error (alt path)"
  else
    ko "input/wasmtime check broken: rc=${rc} out=${out:0:200}"
  fi
fi

# ---------- master spec citation in header ----------
if grep -q "master spec § 20" "${SCRIPT}"; then
  ok "script header cites master spec § 20"
else
  ko "master spec § 20 citation missing"
fi

# Verbatim master spec § 20.2 invocation present in script
if grep -q "target.cpu=znver5" "${SCRIPT}" || grep -q "target znver5" "${SCRIPT}"; then
  ok "script invokes wasmtime with znver5 target (master spec § 20.2)"
else
  ko "znver5 target missing from script"
fi

# Sample dir + README present
if [ -d "${__REPO_ROOT}/scripts/pulse/sample" ]; then
  ok "scripts/pulse/sample/ dir present"
else
  ko "sample dir missing"
fi
if [ -f "${__REPO_ROOT}/scripts/pulse/sample/README.md" ]; then
  ok "sample/README.md present (operator path)"
  if grep -q "master spec § 20" "${__REPO_ROOT}/scripts/pulse/sample/README.md"; then
    ok "sample README cites master spec § 20"
  else
    ko "sample README missing master spec citation"
  fi
else
  ko "sample/README.md missing"
fi

# Layer B metric emission in DRY-RUN output
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 bash "${SCRIPT}" 2>&1)"
set -e
if grep -q "sovereign_os_pulse_wasm_aot_total" <<< "${out}"; then
  ok "Layer B metric emitted under DRY-RUN"
else
  ko "Layer B metric missing"
fi

echo
total=$((pass + fail))
echo "test_pulse_wasm_aot: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
