#!/usr/bin/env bash
# tests/nspawn/test_selfdef_tune_lib.sh
#
# Layer 3 test for R173 — scripts/build/lib/selfdef-tune.sh, the
# sovereign-os bridge to selfdef SD-R19 host-tuned compile flags.
#
# The bridge has 3 source-of-truth paths in preference order:
#   1. selfdefctl on PATH
#   2. /var/lib/selfdef/hardware-capabilities.json (SD-R10)
#   3. native fallback (every build host gets SOMETHING)
#
# This test pins all 3 paths + idempotency + per-var caller-precedence.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

LIB="${__REPO_ROOT}/scripts/build/lib/selfdef-tune.sh"

echo "tests/nspawn/test_selfdef_tune_lib.sh"
echo

[ -f "${LIB}" ] && ok "selfdef-tune.sh library exists" || { ko "missing"; exit 1; }
grep -q "SD-R19" "${LIB}" \
  && ok "cites selfdef SD-R19 (cross-repo provenance)" \
  || ko "SD-R19 citation missing"
grep -q "SD-R10" "${LIB}" \
  && ok "cites SD-R10 fallback (capabilities JSON)" \
  || ko "SD-R10 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ---------- 1) capabilities-JSON fallback path ----------
cat > "${WORK}/caps.json" <<'JSON'
{
  "schema_version": "1",
  "cpu": {
    "recommended_march": "znver5",
    "recommended_compile_flags": [
      "-msse4.2", "-mavx", "-mavx2", "-mavx512f",
      "-mavx512vnni", "-mavx512bf16"
    ],
    "avx512vnni": true,
    "avx512bf16": true,
    "avx512f": true
  }
}
JSON

run_lib() {
  # Run the lib in a clean subshell with controlled PATH/env so the
  # 3 paths can be exercised independently.
  local script="${WORK}/runner.sh"
  cat > "${script}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
. "${LIB}"
selfdef_tune_load
printf 'march=%s\n'  "\${SELFDEF_HARDWARE_MARCH}"
printf 'cflags=%s\n' "\${SELFDEF_HARDWARE_CFLAGS}"
printf 'vnni=%s\n'   "\${SELFDEF_HARDWARE_AVX512_VNNI}"
printf 'bf16=%s\n'   "\${SELFDEF_HARDWARE_AVX512_BF16}"
printf 'src=%s\n'    "\${SELFDEF_HARDWARE_TUNE_SOURCE}"
EOF
  chmod +x "${script}"
  "${script}"
}

set +e
out_json="$(PATH=/usr/bin:/bin \
  SELFDEF_CAPABILITIES_FILE="${WORK}/caps.json" \
  run_lib 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "lib loads against capabilities JSON" \
  || ko "lib rc=${rc}: ${out_json}"
grep -q "march=znver5" <<< "${out_json}" \
  && ok "JSON path: march=znver5" \
  || ko "march missing/wrong: ${out_json}"
grep -q "mprefer-vector-width=512" <<< "${out_json}" \
  && ok "JSON path: ZMM hint present (-mprefer-vector-width=512)" \
  || ko "ZMM hint missing"
grep -q "vnni=true" <<< "${out_json}" \
  && grep -q "bf16=true" <<< "${out_json}" \
  && ok "JSON path: AVX-512 VNNI + BF16 surfaced" \
  || ko "AVX-512 flags missing"
grep -q "src=capabilities_json" <<< "${out_json}" \
  && ok "JSON path: SELFDEF_HARDWARE_TUNE_SOURCE = capabilities_json" \
  || ko "source label wrong"

# ---------- 2) native fallback (no selfdefctl, no JSON) ----------
set +e
out_fb="$(PATH=/usr/bin:/bin \
  SELFDEF_CAPABILITIES_FILE="${WORK}/nope.json" \
  run_lib 2>&1)"
fb_rc=$?
set -e
[ "${fb_rc}" -eq 0 ] && ok "fallback rc=0" || ko "fallback rc=${fb_rc}"
grep -q "march=native" <<< "${out_fb}" \
  && ok "fallback: march=native" || ko "fallback march wrong"
grep -q "vnni=false" <<< "${out_fb}" \
  && ok "fallback: AVX-512 bools default to false" \
  || ko "fallback AVX-512 flags wrong"
grep -q "src=fallback_native" <<< "${out_fb}" \
  && ok "fallback: source label = fallback_native" \
  || ko "fallback source label wrong"

# ---------- 3) idempotency (caller-precedence) ----------
set +e
out_idem="$(PATH=/usr/bin:/bin \
  SELFDEF_HARDWARE_MARCH="operator-set" \
  SELFDEF_HARDWARE_TUNE_SOURCE="operator-set" \
  SELFDEF_CAPABILITIES_FILE="${WORK}/caps.json" \
  run_lib 2>&1)"
set -e
grep -q "march=operator-set" <<< "${out_idem}" \
  && ok "idempotent: caller-set MARCH preserved" \
  || ko "caller MARCH was overwritten"
grep -q "src=operator-set" <<< "${out_idem}" \
  && ok "idempotent: TUNE_SOURCE preserved" \
  || ko "TUNE_SOURCE was overwritten"

# ---------- 4) JSON path tolerates partial/old shapes ----------
cat > "${WORK}/caps-partial.json" <<'JSON'
{
  "cpu": {
    "recommended_march": "x86-64-v4",
    "recommended_compile_flags": ["-msse4.2"],
    "avx512vnni": false,
    "avx512bf16": false,
    "avx512f": false
  }
}
JSON
set +e
out_partial="$(PATH=/usr/bin:/bin \
  SELFDEF_CAPABILITIES_FILE="${WORK}/caps-partial.json" \
  run_lib 2>&1)"
set -e
grep -q "march=x86-64-v4" <<< "${out_partial}" \
  && ok "partial JSON: march read" || ko "partial JSON broken"
# No avx512f → no ZMM hint.
grep -q "mprefer-vector-width=512" <<< "${out_partial}" \
  && ko "ZMM hint should NOT fire on non-AVX-512 host" \
  || ok "non-AVX-512 host: no ZMM hint"

# ---------- 5) Malformed JSON → fallback, not crash ----------
echo "{ not valid json" > "${WORK}/bad.json"
set +e
out_bad="$(PATH=/usr/bin:/bin \
  SELFDEF_CAPABILITIES_FILE="${WORK}/bad.json" \
  run_lib 2>&1)"
bad_rc=$?
set -e
[ "${bad_rc}" -eq 0 ] && ok "malformed JSON → graceful fallback (rc=0)" \
  || ko "malformed JSON crashed: rc=${bad_rc}"
grep -q "src=fallback_native" <<< "${out_bad}" \
  && ok "malformed JSON: fell back to native, not capabilities_json" \
  || ko "malformed JSON: fell through wrong path"

echo
total=$((pass + fail))
echo "test_selfdef_tune_lib: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
