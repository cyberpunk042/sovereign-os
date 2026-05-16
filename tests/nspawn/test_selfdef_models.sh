#!/usr/bin/env bash
# tests/nspawn/test_selfdef_models.sh
#
# Layer 3 test for R182 — sovereign-os mirror of selfdef SD-R34
# model registry (`selfdefctl models check-hardware`). The two
# implementations must agree on identical inputs.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/models/selfdef-models.py"

echo "tests/nspawn/test_selfdef_models.sh"
echo

[ -x "${SCRIPT}" ] && ok "selfdef-models.py executable" \
  || { ko "missing"; exit 1; }
grep -q "SD-R34" "${SCRIPT}" \
  && ok "cites selfdef SD-R34 (cross-repo provenance)" \
  || ko "SD-R34 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

mkdir -p "${WORK}/registry/bitnet-2b" "${WORK}/registry/llama-8b" \
         "${WORK}/registry/qwen-30b" "${WORK}/caps"

# Fixture: 3 models — bitnet on AVX-512 VNNI, llama on small GPU,
# qwen on 30+GiB GPU.
cat > "${WORK}/registry/bitnet-2b/model.toml" <<'TOML'
[model]
name = "bitnet-b1.58-2B-4T"
summary = "BitNet 1.58-bit ternary"
size_bytes = 1700000000
weight_format = "ternary"
[hardware]
avx512_vnni = true
memory_gib_min = 4
TOML

cat > "${WORK}/registry/llama-8b/model.toml" <<'TOML'
[model]
name = "llama-3-8b-q4"
summary = "Llama 3 INT4"
size_bytes = 5400000000
weight_format = "q4_k_m"
[hardware]
gpu_count_min = 1
gpu_vram_gib_min = 6
TOML

cat > "${WORK}/registry/qwen-30b/model.toml" <<'TOML'
[model]
name = "qwen3-30b-fp16"
summary = "Qwen 3 30B FP16"
size_bytes = 60000000000
weight_format = "fp16"
[hardware]
gpu_count_min = 1
gpu_vram_gib_min = 40
TOML

# SAIN-01-shaped caps (RTX PRO 6000 + RTX 3090)
cat > "${WORK}/caps/hardware-capabilities.json" <<'JSON'
{
  "schema_version": "1.2.0",
  "cpu": {"avx512vnni": true, "avx512bf16": true},
  "memory": {"total_bytes": 274877906944},
  "gpu": {"device_count": 2, "device_nodes": [], "devices": [
    {"vram_bytes": 105226698752},
    {"vram_bytes": 25769803776}
  ]},
  "sain01_match": {"overall": "FullMatch"},
  "wasm_aot": {"target_features": "+avx512f,+avx512vnni,+avx512bf16"}
}
JSON

# ---------- list ----------
set +e
out="$(python3 "${SCRIPT}" list --dir "${WORK}/registry" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "list exits 0" || ko "rc=${rc}"
grep -q "bitnet-2b" <<< "${out}" && grep -q "llama-8b" <<< "${out}" \
  && grep -q "qwen-30b" <<< "${out}" \
  && ok "list emits all 3 registered models" \
  || ko "list output incomplete: ${out}"
grep -q "ternary" <<< "${out}" \
  && ok "list shows weight_format column" \
  || ko "weight_format missing"

# ---------- check-hardware on SAIN-01 caps ----------
set +e
out="$(python3 "${SCRIPT}" check-hardware \
  --dir "${WORK}/registry" \
  --caps-path "${WORK}/caps/hardware-capabilities.json" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "check-hardware exits 0" || ko "rc=${rc}"
grep -q "WOULD APPLY (3)" <<< "${out}" \
  && ok "SAIN-01 caps: all 3 models pass" \
  || ko "expected 3 kept: ${out}"
! grep -q "WOULD SKIP" <<< "${out}" \
  && ok "SAIN-01 caps: no models skipped" \
  || ko "unexpected skip on SAIN-01"

# ---------- check-hardware with --json ----------
set +e
out_json="$(python3 "${SCRIPT}" check-hardware \
  --dir "${WORK}/registry" \
  --caps-path "${WORK}/caps/hardware-capabilities.json" --json 2>&1)"
set -e
if python3 -c "
import json
d = json.loads('''${out_json}''')
assert d['probe_ok'] is True
assert d['total'] == 3
assert len(d['kept']) == 3
assert d['skipped'] == []
assert d['kept'][0]['weight_format'] in ('ternary','q4_k_m','fp16')
" 2>/dev/null; then
  ok "--json carries probe_ok=True, total=3, weight_format propagated"
else
  ko "--json shape wrong: ${out_json}"
fi

# ---------- check-hardware on minimal host (caps missing → fallback) ----------
cat > "${WORK}/caps/minimal.json" <<'JSON'
{
  "schema_version": "1.2.0",
  "cpu": {"avx512vnni": false, "avx512bf16": false},
  "memory": {"total_bytes": 8589934592},
  "gpu": {"device_count": 0, "device_nodes": [], "devices": []},
  "sain01_match": {"overall": "NoMatch"},
  "wasm_aot": {"target_features": ""}
}
JSON
set +e
out_min="$(python3 "${SCRIPT}" check-hardware \
  --dir "${WORK}/registry" \
  --caps-path "${WORK}/caps/minimal.json" 2>&1)"
set -e
grep -q "WOULD SKIP (3)" <<< "${out_min}" \
  && ok "minimal host: all 3 models skip" \
  || ko "expected 3 skipped: ${out_min}"
grep -q "avx512_vnni required" <<< "${out_min}" \
  && ok "bitnet skip: avx512_vnni cited" \
  || ko "missing vnni reason"
grep -q "gpu_count_min = 1" <<< "${out_min}" \
  && ok "llama+qwen skip: gpu_count_min cited" \
  || ko "missing gpu_count_min reason"

# ---------- empty registry ----------
mkdir -p "${WORK}/empty"
set +e
out_empty="$(python3 "${SCRIPT}" list --dir "${WORK}/empty" 2>&1)"
set -e
grep -q "no models registered" <<< "${out_empty}" \
  && ok "empty registry: friendly message" \
  || ko "empty path wrong: ${out_empty}"

echo
total=$((pass + fail))
echo "test_selfdef_models: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
