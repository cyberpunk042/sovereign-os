#!/usr/bin/env bash
# tests/nspawn/test_zmm_ternary_probe.sh — R280 (E1.M18).
# 1-bit/ternary ZMM utilization probe (capability + toolchain).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/zmm-ternary-probe.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_zmm_ternary_probe.sh"
echo

[ -x "${SCRIPT}" ] && ok "zmm-ternary-probe.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R280\|E1.M18" "${SCRIPT}" && ok "script cites R280/E1.M18" \
  || ko "R280 missing"
grep -q "raw-dump\|master spec" "${SCRIPT}" \
  && ok "script cites raw-dump master-spec anchor" || ko "anchor missing"
grep -q "^  zmm-ternary)" "${OSCTL}" \
  && ok "osctl bridges 'zmm-ternary'" || ko "osctl dispatch missing"

# ---- status --json: shape ----
set +e
out="$(python3 "${SCRIPT}" status --json 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "status --json rc ∈ {0,1} (got ${rc})"
else
  ko "rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R280', d
for f in ('capability','toolchain','workload_fit','raw_dump_anchor'):
    assert f in d, f'missing {f}'
cap = d['capability']
for k in ('has_required_flags','zmm_512_supported','vnni_int8_dot_product_supported',
         'bf16_fma_supported','flags_present'):
    assert k in cap, f'cap missing {k}'
assert d['workload_fit']['fit'] in ('ready','partial','not-supported'), d
" \
  && ok "status --json: capability + toolchain + workload_fit enum constrained" \
  || ko "status shape wrong"

# ---- perf-cmd --json: emits command list + shell string ----
out="$(python3 "${SCRIPT}" perf-cmd --duration 7 --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R280', d
assert isinstance(d['command'], list)
assert d['command'][0] == 'perf'
assert 'stat' in d['command']
assert 'instructions' in d['command']
assert 'cycles' in d['command']
assert d['command'][-1] == '7'  # operator-set duration surfaces
assert 'avx512' in d['notes'].lower() or 'vnni' in d['notes'].lower()
" \
  && ok "perf-cmd --json: builds perf-stat invocation with operator duration" \
  || ko "perf-cmd shape wrong"

# ---- perf-cmd --target PID variant ----
out="$(python3 "${SCRIPT}" perf-cmd --target 12345 --duration 5 --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert '-p' in d['command'], d
assert '12345' in d['command'], d
" \
  && ok "perf-cmd --target wires -p <PID>" \
  || ko "perf-cmd target wiring wrong"

# ---- advisory --json: shape + fit enum ----
out="$(python3 "${SCRIPT}" advisory --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R280', d
assert d['fit'] in ('ready','partial','not-supported'), d
assert isinstance(d['advisories'], list)
" \
  && ok "advisory --json shape" \
  || ko "advisory shape wrong"

# ---- in-process: capability derivation ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('zt','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Full-capable host
flags = ['avx512f','avx512_vnni','avx512_bf16','avx512_vbmi','avx512vl']
cap = m.derive_capability(flags)
assert cap['has_required_flags'] is True
assert cap['has_all_nice_to_have'] is True
assert cap['zmm_512_supported'] is True
assert cap['vnni_int8_dot_product_supported'] is True
# Missing VNNI
flags2 = ['avx512f','avx512_bf16']
cap = m.derive_capability(flags2)
assert cap['has_required_flags'] is False
assert cap['vnni_int8_dot_product_supported'] is False
" \
  && ok "derive_capability: full-set + missing-VNNI cases" \
  || ko "capability logic wrong"

# ---- in-process: workload-fit verdict ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('zt','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# No VNNI → not-supported
cap_no_vnni = {'has_required_flags': False}
tc = {'bitnet_cli': None, 'bitnet_cpp_binary': None, 'llama_bitnet': None,
      'tmac': None, 'transformers_bitnet': None}
v = m.derive_workload_fit(cap_no_vnni, tc)
assert v['fit'] == 'not-supported', v
# VNNI yes, no toolchain → partial
cap_ok = {'has_required_flags': True}
v = m.derive_workload_fit(cap_ok, tc)
assert v['fit'] == 'partial', v
# VNNI + bitnet-cli → ready
tc_ok = {'bitnet_cli': '/usr/bin/bitnet-cli', 'bitnet_cpp_binary': None,
         'llama_bitnet': None, 'tmac': None, 'transformers_bitnet': None}
v = m.derive_workload_fit(cap_ok, tc_ok)
assert v['fit'] == 'ready', v
assert 'VPDPBUSD' in v['reason']
" \
  && ok "workload_fit: not-supported / partial / ready trichotomy" \
  || ko "workload_fit logic wrong"

# ---- advisory carries actionable bitnet.cpp install hint when toolchain missing ----
python3 -c "
import importlib.util, argparse, io, contextlib, json as j
spec = importlib.util.spec_from_file_location('zt','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Live host: capability ok, toolchain missing → partial advisory.
args = argparse.Namespace(json=True)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = m.cmd_advisory(args)
d = j.loads(buf.getvalue())
# If host VNNI present + no bitnet installed, expect actionable hint.
if d['fit'] == 'partial':
    joined = ' '.join(d['advisories'])
    assert 'bitnet.cpp' in joined or 'BitNet' in joined, joined
" \
  && ok "advisory: partial → bitnet.cpp install hint surfaces" \
  || ko "advisory missing install hint"

# ---- human render: banner + sections ----
out_h="$(python3 "${SCRIPT}" status 2>&1 || true)"
echo "${out_h}" | grep -q "R280 sovereign-os zmm-ternary-probe" \
  && ok "human banner present" || ko "banner missing"
echo "${out_h}" | grep -q "CAPABILITY" \
  && ok "human render shows CAPABILITY section" || ko "section missing"
echo "${out_h}" | grep -q "TOOLCHAIN" \
  && ok "human render shows TOOLCHAIN section" || ko "section missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r280.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" zmm-ternary status --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl zmm-ternary status rc ∈ {0,1}"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R280', d
" \
  && ok "osctl bridge surfaces R280 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" zmm-ternary nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown zmm-ternary subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_zmm_ternary_probe: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
