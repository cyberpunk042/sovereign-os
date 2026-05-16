#!/usr/bin/env bash
# tests/nspawn/test_pulse_wasm_aot_capabilities.sh
#
# Layer 3 test for R167 — scripts/pulse/wasm-aot.sh honoring selfdef
# SDD-017 SD-R10 hardware capabilities JSON.
#
# Validates the cross-repo bridge: when selfdef's hardware probe wrote
# a capabilities file, wasm-aot picks up its recommended_march
# automatically (without operator manually setting WASM_TARGET_CPU).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/pulse/wasm-aot.sh"

echo "tests/nspawn/test_pulse_wasm_aot_capabilities.sh"
echo

[ -x "${SCRIPT}" ] && ok "wasm-aot.sh executable" || { ko "missing"; exit 1; }

grep -q "WASM_CAPABILITIES_FILE" "${SCRIPT}" \
  && ok "script honors WASM_CAPABILITIES_FILE env var" \
  || ko "WASM_CAPABILITIES_FILE knob missing"

grep -q "R167" "${SCRIPT}" \
  && ok "script cites R167 (selfdef SD-R10 bridge)" \
  || ko "R167 citation missing"

# ---------- capabilities file with znver4 → wasm-aot picks it up ----------
TMP_CAP="$(mktemp)"
cat > "${TMP_CAP}" <<'EOF'
{
  "schema_version": "1.0.0",
  "cpu": {
    "recommended_march": "znver4",
    "recommended_compile_flags": ["-mavx512f"]
  }
}
EOF
set +e
out="$(WASM_CAPABILITIES_FILE="${TMP_CAP}" SOVEREIGN_OS_DRY_RUN=1 bash "${SCRIPT}" 2>&1)"
rc=$?
set -e
rm -f "${TMP_CAP}"
[ "${rc}" -eq 0 ] && ok "DRY-RUN with caps file exits 0" || ko "rc=${rc}"
grep -q "R167:" <<< "${out}" && ok "R167 log line surfaces" \
  || ko "R167 log line missing"
grep -q "target CPU:.*znver4" <<< "${out}" && ok "target CPU swapped to znver4 via caps" \
  || ko "target CPU not swapped"

# ---------- recommended_march = native → caps respected but no swap ----------
TMP_CAP="$(mktemp)"
cat > "${TMP_CAP}" <<'EOF'
{"cpu": {"recommended_march": "native"}}
EOF
set +e
out="$(WASM_CAPABILITIES_FILE="${TMP_CAP}" SOVEREIGN_OS_DRY_RUN=1 bash "${SCRIPT}" 2>&1)"
set -e
rm -f "${TMP_CAP}"
# native means "let GCC pick" — wasm-aot.sh leaves the default znver5
# alone (we don't want to downgrade silently).
grep -q "target CPU:.*znver5" <<< "${out}" && ok "native recommendation does NOT downgrade default" \
  || ko "native unexpectedly modified target"

# ---------- explicit WASM_TARGET_CPU override wins over caps file ----------
TMP_CAP="$(mktemp)"
cat > "${TMP_CAP}" <<'EOF'
{"cpu": {"recommended_march": "znver4"}}
EOF
set +e
out="$(WASM_CAPABILITIES_FILE="${TMP_CAP}" WASM_TARGET_CPU=cooperlake SOVEREIGN_OS_DRY_RUN=1 bash "${SCRIPT}" 2>&1)"
set -e
rm -f "${TMP_CAP}"
grep -q "target CPU:.*cooperlake" <<< "${out}" && ok "explicit WASM_TARGET_CPU wins over caps file" \
  || ko "explicit override didn't win"

# ---------- missing caps file → defaults preserved ----------
set +e
out="$(WASM_CAPABILITIES_FILE=/tmp/no-such-caps-file SOVEREIGN_OS_DRY_RUN=1 bash "${SCRIPT}" 2>&1)"
set -e
grep -q "target CPU:.*znver5" <<< "${out}" && ok "missing caps file → znver5 default preserved" \
  || ko "missing caps file: target wrong"
! grep -q "R167:" <<< "${out}" && ok "missing caps file → no R167 log line" \
  || ko "R167 log fired without caps file"

echo
total=$((pass + fail))
echo "test_pulse_wasm_aot_capabilities: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
