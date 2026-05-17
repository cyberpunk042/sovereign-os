#!/usr/bin/env bash
# tests/nspawn/test_cycle2_fleet_aggregate.sh
#
# Layer 3 test for R199 — fleet rollup of per-host R187 cycle2-status
# JSON. Closes SDD-021 W-3 (file-based variant; SSH-based fleet pull
# deferred to a future round).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/cycle2-fleet-aggregate.py"

echo "tests/nspawn/test_cycle2_fleet_aggregate.sh"
echo

[ -x "${SCRIPT}" ] && ok "cycle2-fleet-aggregate.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R199" "${SCRIPT}" \
  && ok "carries R199 marker" || ko "R199 missing"
grep -q "SDD-021 W-3" "${SCRIPT}" \
  && ok "cites SDD-021 W-3 (provenance)" || ko "W-3 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# 3-host fixture
cat > "${WORK}/prod-01.json" <<'JSON'
{"schema_version":"1.0.0","caps_present":true,"sain01_verdict":"FullMatch",
 "modules_gate":{"available":true,"total":4,"kept":4,"skipped":0},
 "models_gate":{"available":true,"total":3,"kept":3,"skipped":0},
 "bitnet_schedule_present":true,
 "wasm_aot_cache":{"present":true,"cwasm_count":5,"path":"/var/lib/selfdef/wasm-aot"},
 "override_audit":{"count":2,"by_category":{"selfdef.modules.override":2}}}
JSON
cat > "${WORK}/prod-02.json" <<'JSON'
{"schema_version":"1.0.0","caps_present":true,"sain01_verdict":"PartialMatch",
 "modules_gate":{"available":true,"total":4,"kept":3,"skipped":1},
 "models_gate":{"available":true,"total":3,"kept":2,"skipped":1},
 "bitnet_schedule_present":false,
 "wasm_aot_cache":{"present":false,"cwasm_count":0,"path":""},
 "override_audit":{"count":1,"by_category":{"selfdef.modules.skip-strict":1}}}
JSON
cat > "${WORK}/dev-01.json" <<'JSON'
{"schema_version":"1.0.0","caps_present":false,"sain01_verdict":"NoMatch",
 "modules_gate":{"available":false},
 "models_gate":{"available":false},
 "bitnet_schedule_present":false,
 "wasm_aot_cache":{"present":false,"cwasm_count":0,"path":""},
 "override_audit":{"count":0,"by_category":{}}}
JSON

# Human rollup
set +e
out="$("${SCRIPT}" --dir "${WORK}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "rc=0 on valid fleet" || ko "rc=${rc}"
grep -q "fleet rollup — 3 host" <<< "${out}" \
  && ok "human: 3 hosts counted" || ko "host count wrong"
grep -q "caps present:.*2/3" <<< "${out}" \
  && ok "human: caps_present rollup correct" || ko "caps rollup wrong"
grep -q "sain01 FullMatch:.*1/3" <<< "${out}" \
  && ok "human: full-match rollup correct" || ko "full-match wrong"
grep -q "2× --ignore-hardware" <<< "${out}" \
  && ok "human: override category labels rendered" || ko "override label missing"

# JSON rollup
set +e
out_json="$("${SCRIPT}" --dir "${WORK}" --json 2>&1)"
set -e
if python3 -c "
import json
d = json.loads('''${out_json}''')
assert d['schema_version'] == '1.0.0'
assert d['host_count'] == 3
r = d['rollups']
assert r['caps_present']['hosts'] == 2
assert r['sain01_full_match']['hosts'] == 1
assert r['bitnet_schedule_present']['hosts'] == 1
assert r['wasm_aot_cache_present']['hosts'] == 1
assert r['override_audit_total'] == 3
assert r['override_audit_by_category']['selfdef.modules.override'] == 2
assert r['override_audit_by_category']['selfdef.modules.skip-strict'] == 1
# Pass-rate averages: prod-01 = 4/4 = 1.0; prod-02 = 3/4 = 0.75; dev unavailable
# avg(1.0, 0.75) = 0.875
assert abs(r['modules_gate_pass_rate_avg'] - 0.875) < 0.01
" 2>/dev/null; then
  ok "--json rollup: every field correct"
else
  ko "--json shape wrong: ${out_json}"
fi

# Missing --dir → rc=2
set +e
"${SCRIPT}" --dir "${WORK}/no-such" 2>/dev/null
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "missing --dir → rc=2" || ko "rc=${rc}"

# Empty dir → host_count=0
EMPTY="$(mktemp -d)"
trap 'rm -rf "${WORK}" "${EMPTY}"' EXIT
set +e
out_empty="$("${SCRIPT}" --dir "${EMPTY}" 2>&1)"
set -e
grep -q "0 host(s)" <<< "${out_empty}" \
  && ok "empty dir → graceful '0 host(s)' message" \
  || ko "empty-dir message missing: ${out_empty}"

echo
total=$((pass + fail))
echo "test_cycle2_fleet_aggregate: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
