#!/usr/bin/env bash
# tests/nspawn/test_cycle2_status.sh
#
# Layer 3 test for R187 — comprehensive cycle-2 readiness report.
# Aggregates SD-R10..R42 + R170..R186 mirrors in one command.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/cycle2-status.py"

echo "tests/nspawn/test_cycle2_status.sh"
echo

[ -x "${SCRIPT}" ] && ok "cycle2-status.py executable" \
  || { ko "missing"; exit 1; }

grep -q "R187" "${SCRIPT}" \
  && ok "script carries R187 marker" || ko "R187 marker missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
mkdir -p "${WORK}/caps" "${WORK}/modules/alpha" "${WORK}/modules/beta" \
         "${WORK}/host" "${WORK}/models/m1"

cat > "${WORK}/caps/hardware-capabilities.json" <<'JSON'
{
  "schema_version": "1.2.0",
  "probed_at": "2026-05-16T22:50:00Z",
  "cpu": {"model_name": "Test CPU", "avx512vnni": true, "avx512bf16": true,
          "avx512fp16": false},
  "memory": {"total_bytes": 68719476736},
  "gpu": {"device_count": 1, "device_nodes": [],
          "devices": [{"vram_bytes": 25769803776}]},
  "sain01_match": {"overall": "PartialMatch"},
  "wasm_aot": {"target_cpu": "znver5",
               "target_features": "+avx512f,+avx512vnni"}
}
JSON
cat > "${WORK}/modules/alpha/module.toml" <<'TOML'
name = "alpha"
version = "0"
summary = "test"
TOML
cat > "${WORK}/modules/beta/module.toml" <<'TOML'
name = "beta"
version = "0"
summary = "huge mem"
[requires_hardware]
memory_gib_min = 9999
TOML
cat > "${WORK}/host/modules.toml" <<'TOML'
[modules.alpha]
[modules.beta]
TOML
cat > "${WORK}/models/m1/model.toml" <<'TOML'
[model]
name = "model-1"
weight_format = "fp16"
size_bytes = 1000000
TOML

CMD=(python3 "${SCRIPT}"
     --caps-path "${WORK}/caps/hardware-capabilities.json"
     --modules-dir "${WORK}/modules"
     --host-config "${WORK}/host/modules.toml"
     --models-dir "${WORK}/models"
     --schedule-path "${WORK}/no-such.json")

# ---------- human-readable ----------
set +e
out="$("${CMD[@]}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "human report exits 0" || ko "rc=${rc}"
grep -q "Capabilities: ✓" <<< "${out}" && ok "caps section: present" \
  || ko "caps section: ${out}"
grep -q "AVX-512:" <<< "${out}" && ok "AVX-512 line surfaced" \
  || ko "AVX-512 line missing"
grep -q "Sain01:       PartialMatch" <<< "${out}" \
  && ok "sain01 verdict reflected" || ko "sain01 wrong"
grep -q "Wasm-AOT (SD-R30):" <<< "${out}" \
  && ok "wasm-AOT section emitted (has AVX-512)" \
  || ko "wasm-AOT section missing"
grep -q "Modules gate.*1/2 apply" <<< "${out}" \
  && ok "modules gate: 1/2 apply (beta skipped, alpha kept)" \
  || ko "modules count wrong: ${out}"
grep -q "Models gate.*1/1 apply" <<< "${out}" \
  && ok "models gate: 1/1 apply" || ko "models count wrong"
grep -q "BitNet schedule.*absent" <<< "${out}" \
  && ok "bitnet schedule: absent message" || ko "schedule status wrong"

# ---------- --json ----------
set +e
out_json="$("${CMD[@]}" --json 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--json exits 0" || ko "--json rc=${rc}"
if python3 -c "
import json
d = json.loads('''${out_json}''')
assert d['caps_present'] is True
assert d['cpu_avx512']['vnni'] is True
assert d['cpu_avx512']['bf16'] is True
assert d['cpu_avx512']['fp16'] is False
assert d['sain01_verdict'] == 'PartialMatch'
assert d['wasm_aot']['target_cpu'] == 'znver5'
assert d['modules_gate']['total'] == 2
assert d['modules_gate']['kept'] == 1
assert d['modules_gate']['skipped'] == 1
assert d['models_gate']['total'] == 1
assert d['models_gate']['kept'] == 1
assert d['bitnet_schedule_present'] is False
" 2>/dev/null; then
  ok "--json shape complete (caps + gates + sain01 + wasm-AOT)"
else
  ko "--json shape wrong: ${out_json}"
fi

# ---------- absent caps file → graceful ----------
set +e
out_no_caps="$(python3 "${SCRIPT}" \
  --caps-path "${WORK}/no-such.json" \
  --modules-dir "${WORK}/modules" \
  --host-config "${WORK}/host/modules.toml" \
  --models-dir "${WORK}/models" \
  --schedule-path "${WORK}/no-such-schedule.json" --json 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "absent caps → rc=0 (graceful)" || ko "rc=${rc}"
if python3 -c "
import json
d = json.loads('''${out_no_caps}''')
assert d['caps_present'] is False
" 2>/dev/null; then
  ok "absent caps → caps_present=False in JSON"
else
  ko "absent-caps JSON wrong: ${out_no_caps}"
fi

echo
total=$((pass + fail))
echo "test_cycle2_status: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
