#!/usr/bin/env bash
# tests/nspawn/test_osctl_models_registry.sh
#
# Layer 3 test for R183 — `sovereign-osctl models {registered,
# check-hardware}` bridges to the R182 selfdef SD-R34 model registry.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_osctl_models_registry.sh"
echo

[ -x "${OSCTL}" ] && ok "sovereign-osctl executable" \
  || { ko "missing"; exit 1; }

grep -q "registered)" "${OSCTL}" \
  && ok "osctl carries R183 'registered' dispatch" \
  || ko "registered subcommand missing"
grep -q "check-hardware)" "${OSCTL}" \
  && ok "osctl carries R183 'check-hardware' dispatch" \
  || ko "check-hardware subcommand missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

mkdir -p "${WORK}/reg/bitnet-2b" "${WORK}/caps"
cat > "${WORK}/reg/bitnet-2b/model.toml" <<'TOML'
[model]
name = "bitnet-b1.58-2B-4T"
summary = "BitNet 1.58-bit ternary"
size_bytes = 1700000000
weight_format = "ternary"
[hardware]
avx512_vnni = true
TOML

cat > "${WORK}/caps/hardware-capabilities.json" <<'JSON'
{"schema_version": "1.2.0",
 "cpu": {"avx512vnni": true, "avx512bf16": true},
 "memory": {"total_bytes": 274877906944},
 "gpu": {"device_count": 0, "device_nodes": [], "devices": []},
 "sain01_match": {"overall": "PartialMatch"},
 "wasm_aot": {"target_features": "+avx512f,+avx512vnni"}}
JSON

# ---------- osctl models registered (passes through to R182) ----------
set +e
out="$("${OSCTL}" models registered --dir "${WORK}/reg" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl models registered → rc=0" \
  || ko "rc=${rc}: ${out}"
grep -q "bitnet-2b" <<< "${out}" \
  && ok "registered output passes through to R182 (model listed)" \
  || ko "model not listed: ${out}"

# ---------- osctl models check-hardware ----------
set +e
out="$("${OSCTL}" models check-hardware \
  --dir "${WORK}/reg" \
  --caps-path "${WORK}/caps/hardware-capabilities.json" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl models check-hardware → rc=0" \
  || ko "rc=${rc}: ${out}"
grep -q "WOULD APPLY" <<< "${out}" \
  && ok "check-hardware output includes dry-run banner" \
  || ko "no dry-run banner: ${out}"
grep -q "bitnet-2b" <<< "${out}" \
  && ok "bitnet-2b → kept on AVX-512-VNNI host" \
  || ko "expected bitnet kept: ${out}"

# ---------- --json passthrough ----------
set +e
out_json="$("${OSCTL}" models check-hardware \
  --dir "${WORK}/reg" \
  --caps-path "${WORK}/caps/hardware-capabilities.json" --json 2>&1)"
set -e
if python3 -c "import json; d=json.loads('''${out_json}'''); assert d['total']==1; assert len(d['kept'])==1" 2>/dev/null; then
  ok "--json passthrough: total=1, kept=1"
else
  ko "--json broken: ${out_json}"
fi

# ---------- R196: fetch + verify-checksum subcommand dispatch ----------
grep -q "fetch)" "${OSCTL}" \
  && ok "osctl carries R196 'fetch' dispatch" \
  || ko "fetch subcommand missing"
grep -q "verify-checksum)" "${OSCTL}" \
  && ok "osctl carries R196 'verify-checksum' dispatch" \
  || ko "verify-checksum subcommand missing"

# fetch without selfdefctl on PATH → rc≠0 + clear error
set +e
out_fetch="$(PATH=/usr/bin:/bin "${OSCTL}" models fetch fake-slug --to /tmp/x 2>&1)"
fetch_rc=$?
set -e
[ "${fetch_rc}" -ne 0 ] && ok "fetch without selfdefctl → rc≠0" \
  || ko "fetch should fail when selfdefctl absent"
grep -q "selfdefctl not on PATH" <<< "${out_fetch}" \
  && ok "fetch error cites missing selfdefctl" \
  || ko "missing error message: ${out_fetch}"

# verify-checksum bridge: stage a manifest with mismatched sha → rc=1
WORK_VC="$(mktemp -d)"
trap 'rm -rf "${WORK}" "${WORK_VC}"' EXIT
echo "test" > "${WORK_VC}/artifact.bin"
cat > "${WORK_VC}/model.toml" <<'TOML'
[model]
name = "test"
artifact_sha256 = "deadbeef0000000000000000000000000000000000000000000000000000beef"
TOML
set +e
"${OSCTL}" models verify-checksum \
  --manifest "${WORK_VC}/model.toml" \
  --artifact "${WORK_VC}/artifact.bin" --quiet 2>/dev/null
vc_rc=$?
set -e
[ "${vc_rc}" -eq 1 ] && ok "verify-checksum bridge: mismatched sha → rc=1" \
  || ko "verify-checksum bridge rc=${vc_rc}"

echo
total=$((pass + fail))
echo "test_osctl_models_registry: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
