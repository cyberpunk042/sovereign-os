#!/usr/bin/env bash
# tests/nspawn/test_models_suggest.sh — R214 profile-aware suggester.
# Cross-references runtime-profile allocations against the R212 catalog
# and produces operator-actionable advice. The flagged-allocation scenario
# runs on a synthetic fixture profile (the §18 trio — whose flagged
# allocations this test used — was retired 2026-10-08).

set -euo pipefail
PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3=/usr/bin/python3
  fi
fi


__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/models/suggest-by-profile.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_models_suggest.sh"
echo

[ -x "${SCRIPT}" ] && ok "suggest-by-profile.py executable" \
  || { ko "missing suggest-by-profile.py"; exit 1; }
grep -q "suggest)" "${OSCTL}" \
  && ok "osctl bridges 'models suggest'" \
  || ko "osctl bridge missing"
grep -q "models suggest --runtime-profile" "${OSCTL}" \
  && ok "osctl help documents 'models suggest'" \
  || ko "osctl help missing"

# --- --list ---
set +e
list_out="$("${PYTHON3}" "${SCRIPT}" --list)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--list rc=0" || ko "--list rc=${rc}"
grep -qF "ultra-sovereign-efficiency" <<< "${list_out}" \
  && ko "list still carries retired §18 id" \
  || ok "list no longer carries the retired §18 ids"

# --- fixture profile with known flagged allocations ---
WORK="$(mktemp -d)"
FLAG="${__REPO_ROOT}/profiles/runtime/_test_suggest_flagged.yaml"
trap 'rm -rf "${WORK}"; rm -f "${FLAG}"' EXIT
cat > "${FLAG}" <<'FIXTURE'
schema_version: "1.0.0"
runtime_profile:
  id: _test_suggest_flagged
  name: "Test fixture — flagged allocations"
  description: >-
    Suggester test fixture: carries the aspirational + VRAM-overrun
    allocations the retired §18 trio exercised.
  hardware_profile_compat: [sain-01]
  allocations:
    - agent_id: conductor_01
      tier: pulse
      target_hardware: cpu
      core_mask: "0-11"
      engine: bitnet.cpp
      model: BitNet-b1.58-13B
    - agent_id: deep_reasoner_01
      tier: oracle
      target_hardware: cuda:0
      vram_limit_bytes: 94489280512   # 88 GiB
      engine: llama.cpp
      model: DeepSeek-R1-Distill-Llama-70B-FP16
    - agent_id: translator_01
      tier: logic
      target_hardware: cuda:1
      engine: vllm
      model: Qwen-32B-Ternary-Quant
FIXTURE
set +e
"${PYTHON3}" "${SCRIPT}" --runtime-profile _test_suggest_flagged > "${WORK}/hcb.txt"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "fixture profile rc=1 (flagged allocations)" \
  || ko "expected rc=1 on flagged profile, got ${rc}"
grep -q "R214 model suggester" "${WORK}/hcb.txt" \
  && ok "banner cites R214" || ko "no R214 banner"

# Allocations enumerated with declared models
for needle in "Agent: conductor_01" "Agent: deep_reasoner_01"; do
  grep -qF "${needle}" "${WORK}/hcb.txt" && ok "row present: ${needle}" \
    || ko "missing row: ${needle}"
done

# Aspirational flag on conductor (BitNet-b1.58-13B is aspirational)
grep -q "aspirational entry" "${WORK}/hcb.txt" \
  && ok "aspirational flag surfaced" || ko "missing aspirational flag"

# VRAM overrun flag on deep_reasoner (140 GiB > 88 GiB)
grep -q "VRAM requirement 140 GiB exceeds allocation limit 88.0 GiB" "${WORK}/hcb.txt" \
  && ok "VRAM overrun flag surfaced (140 vs 88)" || ko "missing VRAM overrun"

# Smaller-quant alternative offered for deep_reasoner
grep -q "DeepSeek-R1-Distill-Llama-70B-Q4_K_M" "${WORK}/hcb.txt" \
  && ok "smaller-quant Q4_K_M alternative surfaced" \
  || ko "no Q4_K_M alternative"

# Closing flagged banner
grep -q "At least one allocation flagged" "${WORK}/hcb.txt" \
  && ok "closing flagged banner present" || ko "no closing banner"

# --- JSON mode ---
set +e
"${PYTHON3}" "${SCRIPT}" --runtime-profile _test_suggest_flagged --json > "${WORK}/hcb.json"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "--json rc=1 on flagged profile" || ko "--json rc=${rc}"
"${PYTHON3}" - "${WORK}/hcb.json" <<'PY' 2>/dev/null \
  && ok "JSON shape correct + any_flagged=True + 2 allocations" \
  || ko "JSON shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["profile_id"] == "_test_suggest_flagged"
assert d["any_flagged"] is True
assert len(d["allocations"]) == 3  # conductor + deep_reasoner + translator (R216 reuses this fixture)
# deep_reasoner_01 must carry alternatives
deep = next(a for a in d["allocations"] if a["agent_id"] == "deep_reasoner_01")
assert any("Q4_K_M" in alt["id"] for alt in deep["alternatives"]), deep["alternatives"]
PY

# --- unknown profile → rc=2 ---
set +e
"${PYTHON3}" "${SCRIPT}" --runtime-profile does-not-exist >/dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown profile → rc=2" \
  || ko "expected rc=2 on unknown profile, got ${rc}"

# --- usage error (no flag) → rc=2 ---
set +e
"${PYTHON3}" "${SCRIPT}" >/dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "missing flag → rc=2" \
  || ko "expected rc=2 on missing flag, got ${rc}"

# --- osctl bridge ---
set +e
out_osctl="$("${OSCTL}" models suggest --list 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl models suggest --list rc=0" \
  || ko "osctl bridge failed (rc=${rc})"
grep -qF "_test_suggest_flagged" <<< "${out_osctl}" \
  && ok "osctl --list surfaces profiles" || ko "osctl --list wrong"

# --- R216: --gpu-vram-gib host budget override ---
set +e
"${PYTHON3}" "${SCRIPT}" --runtime-profile _test_suggest_flagged \
  --gpu-vram-gib 8,8 > "${WORK}/r216.txt"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "--gpu-vram-gib 8,8 rc=1 (everything overflows tiny budget)" \
  || ko "R216 expected rc=1, got ${rc}"
grep -q "R216 host-budget override active" "${WORK}/r216.txt" \
  && ok "R216 override banner rendered" || ko "no R216 banner"
grep -q "8.0 GiB, 8.0 GiB" "${WORK}/r216.txt" \
  && ok "R216 budgets shown in banner" || ko "no budget values"

# Translator allocation default is 21 GiB (4090); 8-GiB override
# should now flag VRAM overrun on the translator too.
grep -q "VRAM requirement 24 GiB exceeds allocation limit 8.0 GiB" "${WORK}/r216.txt" \
  && ok "R216 overrides translator default limit (21→8 GiB)" \
  || ko "R216 override not honored on translator allocation"

# JSON shape carries host_gpu_vram_gib echo
set +e
"${PYTHON3}" "${SCRIPT}" --runtime-profile _test_suggest_flagged \
  --gpu-vram-gib 24,96 --json > "${WORK}/r216.json"
set -e
"${PYTHON3}" - "${WORK}/r216.json" <<'PY' 2>/dev/null \
  && ok "R216 JSON carries host_gpu_vram_gib echo + matches input" \
  || ko "R216 JSON shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d.get("host_gpu_vram_gib") == [24.0, 96.0], d.get("host_gpu_vram_gib")
PY

# Bad budget → rc=2
set +e
"${PYTHON3}" "${SCRIPT}" --runtime-profile _test_suggest_flagged \
  --gpu-vram-gib "junk" >/dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "malformed --gpu-vram-gib → rc=2" \
  || ko "expected rc=2 on bad budget, got ${rc}"

echo
total=$((pass + fail))
echo "test_models_suggest: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
