#!/usr/bin/env bash
# tests/nspawn/test_posture.sh — R210 hardware-exploit posture mirror.
# Bridges to selfdef SD-R67 by reading the capabilities JSON the
# selfdef daemon emits and rendering the same operator-readable
# posture summary.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/posture.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_posture.sh"
echo

[ -x "${SCRIPT}" ] && ok "posture.py executable" \
  || { ko "missing posture.py"; exit 1; }

grep -q "posture)" "${OSCTL}" \
  && ok "osctl bridges 'bootstrap posture' subverb" \
  || ko "osctl bridge missing"
grep -q "posture \[--caps-path" "${OSCTL}" \
  && ok "osctl help documents posture verb" \
  || ko "osctl help missing posture doc"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# SAIN-01-flavored capabilities JSON (SD-R66 + SD-R64 surfaces).
cat > "${WORK}/sain01.json" <<'JSON'
{
  "schema_version": "1.3.0",
  "probed_at": "2026-05-17T00:00:00Z",
  "cpu": {
    "vendor": "AuthenticAMD",
    "model_name": "AMD Ryzen 9 9900X",
    "avx512vnni": true, "avx512bf16": true,
    "ternary_aot_capable": true,
    "zmm_int8_lane_capacity": 64,
    "recommended_march": "znver5"
  },
  "memory": {"total_bytes": 274877906944},
  "gpu": {"device_count": 2, "device_nodes": [], "devices": []},
  "sain01_match": {"overall": "FullMatch"},
  "wasm_aot": {
    "target_triple": "x86_64-unknown-linux-gnu",
    "target_cpu": "znver5",
    "target_features": "+avx512f,+avx512vnni,+avx512bf16,+avx2,+fma",
    "compile_command_hint": "...",
    "ternary_kernel_hint": "bitnet.cpp/VPDPBUSD: 64×INT8 per ZMM (master spec § 16 hot path)"
  }
}
JSON

# Banner mode
set +e
banner="$(python3 "${SCRIPT}" --caps-path "${WORK}/sain01.json")"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "banner rc=0 on SAIN-01 caps" \
  || ko "expected rc=0 on SAIN-01, got ${rc}"

for needle in \
  "── selfdef hardware-exploit posture" \
  "Sain01 verdict          : FullMatch" \
  "Target CPU (LLVM)       : znver5" \
  "Ternary AOT capable     : yes" \
  "ZMM INT8 lane capacity  : 64 (master spec § 16 reading)" \
  "Kernel hint             : bitnet.cpp/VPDPBUSD"; do
  grep -qF "${needle}" <<< "${banner}" \
    && ok "banner contains: ${needle:0:40}…" \
    || ko "banner missing: ${needle}"
done

# Minimal host (no ternary path)
cat > "${WORK}/minimal.json" <<'JSON'
{
  "schema_version": "1.2.0",
  "cpu": {"vendor": "GenuineIntel", "avx512vnni": false, "avx512bf16": false},
  "memory": {"total_bytes": 8589934592},
  "gpu": {"device_count": 0, "device_nodes": [], "devices": []},
  "sain01_match": {"overall": "NoMatch"},
  "wasm_aot": {
    "target_triple": "x86_64-unknown-linux-gnu",
    "target_cpu": "native",
    "target_features": "",
    "compile_command_hint": ""
  }
}
JSON

set +e
banner_min="$(python3 "${SCRIPT}" --caps-path "${WORK}/minimal.json")"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "banner rc=0 on minimal caps (still informational)" \
  || ko "minimal-host banner rc≠0: ${rc}"
grep -qF "Ternary AOT capable     : no" <<< "${banner_min}" \
  && ok "minimal host renders ternary=no" || ko "wrong ternary line"
grep -qF "(no INT8 SIMD path on this host)" <<< "${banner_min}" \
  && ok "minimal host kernel-hint fallback rendered" \
  || ko "kernel-hint fallback wrong"
grep -qF "Target features         : (none — pre-AVX-512 host)" <<< "${banner_min}" \
  && ok "empty target_features fallback rendered" \
  || ko "target_features fallback wrong"

# JSON mode
set +e
json_out="$(python3 "${SCRIPT}" --caps-path "${WORK}/sain01.json" --json)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--json rc=0" || ko "--json failed (rc=${rc})"
python3 -c "
import json, sys
d = json.loads('''${json_out}''')
assert d['ternary_aot_capable'] is True, d
assert d['zmm_int8_lane_capacity'] == 64, d
assert 'VPDPBUSD' in d['ternary_kernel_hint'], d
assert d['sain01_match'] == 'FullMatch', d
" 2>/dev/null && ok "JSON shape correct" || ko "JSON shape wrong"

# Missing caps file → rc=1
set +e
python3 "${SCRIPT}" --caps-path "${WORK}/does-not-exist.json" >/dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "missing caps → rc=1" \
  || ko "expected rc=1 on missing caps, got ${rc}"

# osctl bridge invocation
set +e
out_osctl="$("${OSCTL}" bootstrap posture --caps-path "${WORK}/sain01.json" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl bootstrap posture rc=0" \
  || ko "osctl bridge failed (rc=${rc})"
grep -qF "Ternary AOT capable" <<< "${out_osctl}" \
  && ok "osctl bridge surfaces posture output" \
  || ko "osctl output unexpected"

echo
total=$((pass + fail))
echo "test_posture: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
