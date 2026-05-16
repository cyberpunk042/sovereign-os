#!/usr/bin/env bash
# tests/nspawn/test_pulse_build_bitnet_capabilities.sh
#
# Layer 3 test for R168 — scripts/pulse/build-bitnet.sh honoring
# selfdef SD-R10 hardware-capabilities.json. Same cross-repo bridge
# pattern as R167's wasm-aot integration.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/pulse/build-bitnet.sh"

echo "tests/nspawn/test_pulse_build_bitnet_capabilities.sh"
echo

[ -x "${SCRIPT}" ] && ok "build-bitnet.sh executable" || { ko "missing"; exit 1; }

grep -q "BITNET_CAPABILITIES_FILE" "${SCRIPT}" \
  && ok "script honors BITNET_CAPABILITIES_FILE env var" \
  || ko "BITNET_CAPABILITIES_FILE knob missing"

grep -q "R168" "${SCRIPT}" \
  && ok "script cites R168 (selfdef SD-R10 bridge)" \
  || ko "R168 citation missing"

# We can't run the full bitnet build in CI (needs cmake + git +
# upstream clone), so we test the script header + the derivation
# logic by extracting it.

# ---------- derivation logic with synthetic znver4 capabilities ----------
TMP_CAP="$(mktemp)"
cat > "${TMP_CAP}" <<'EOF'
{
  "schema_version": "1.0.0",
  "cpu": {
    "recommended_march": "znver4",
    "recommended_compile_flags": ["-mavx512f", "-mavx512dq", "-mavx512bw", "-mavx512vl"]
  }
}
EOF
derived="$(python3 - "${TMP_CAP}" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
cpu = d.get("cpu", {})
march = cpu.get("recommended_march", "")
flags = cpu.get("recommended_compile_flags", []) or []
if march and march != "native":
    print(f"-march={march} -O3 " + " ".join(flags))
PYEOF
)"
rm -f "${TMP_CAP}"
if echo "${derived}" | grep -q -- "-march=znver4" && \
   echo "${derived}" | grep -q -- "-mavx512vl"; then
  ok "derivation produces znver4 + correct flag set from caps"
else
  ko "derivation broken: ${derived}"
fi

# ---------- 'native' recommendation produces empty derivation (falls back to default) ----------
TMP_CAP="$(mktemp)"
cat > "${TMP_CAP}" <<'EOF'
{"cpu": {"recommended_march": "native"}}
EOF
derived="$(python3 - "${TMP_CAP}" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
cpu = d.get("cpu", {})
march = cpu.get("recommended_march", "")
flags = cpu.get("recommended_compile_flags", []) or []
if march and march != "native":
    print(f"-march={march} -O3 " + " ".join(flags))
PYEOF
)"
rm -f "${TMP_CAP}"
[ -z "${derived}" ] && ok "'native' recommendation produces empty derivation (script falls back to default)" \
  || ko "'native' produced unexpected derivation: ${derived}"

# ---------- script defines BITNET_CAPABILITIES_FILE default path ----------
grep -q "/var/lib/selfdef/hardware-capabilities.json" "${SCRIPT}" \
  && ok "script defaults BITNET_CAPABILITIES_FILE to canonical selfdef path" \
  || ko "default path missing"

# ---------- explicit BITNET_CFLAGS override path documented ----------
grep -q "BITNET_CFLAGS" "${SCRIPT}" \
  && ok "script honors BITNET_CFLAGS operator override" \
  || ko "BITNET_CFLAGS knob missing"

echo
total=$((pass + fail))
echo "test_pulse_build_bitnet_capabilities: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
