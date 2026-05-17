#!/usr/bin/env bash
# tests/nspawn/test_avx512_advisor.sh — R272 (E1.M14).
# AVX-512 extension probe + workload-fit advisor.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/avx512-advisor.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_avx512_advisor.sh"
echo

[ -x "${SCRIPT}" ] && ok "avx512-advisor.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R272\|E1.M14" "${SCRIPT}" && ok "script cites R272/E1.M14" \
  || ko "R272 missing"
grep -q "^  avx512-advisor)" "${OSCTL}" \
  && ok "osctl bridges 'avx512-advisor'" || ko "osctl dispatch missing"

# ---- probe --json: 16 extensions + flag map ----
out="$(python3 "${SCRIPT}" probe --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R272', d
assert 'avx512_supported' in d, d
assert d['extension_counts']['total'] == 16, d
# Required keys per extension
for e in d['extensions']:
    for k in ('flag','cpuinfo_flag','present','summary'):
        assert k in e, f'missing {k} in {e}'
# Critical extensions must be in the map
flag_names = {e['flag'] for e in d['extensions']}
for needed in ('F','VL','BW','DQ','VNNI','BF16','FP16','IFMA','VBMI','CD'):
    assert needed in flag_names, f'missing extension {needed}'
" \
  && ok "probe --json: 16 extensions including F/VL/BW/DQ/VNNI/BF16/FP16/IFMA/VBMI/CD" \
  || ko "probe shape wrong"

# ---- workloads --json: 9 workloads with required flags ----
out="$(python3 "${SCRIPT}" workloads --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R272', d
assert d['workload_count'] == 9, d
# Critical workloads must be present
names = {w['workload'] for w in d['workloads']}
for needed in ('bitnet-ternary-inference','bf16-inference','fp16-mixed-precision',
               'sparse-attention','string-tokenization','aes-disk-encryption'):
    assert needed in names, f'missing workload {needed}'
# Each workload has required_flags non-empty
for w in d['workloads']:
    assert w['required_flags'], w
    assert 'summary' in w and 'operator_note' in w
# bitnet-ternary specifically requires VNNI
bitnet = next(w for w in d['workloads'] if w['workload']=='bitnet-ternary-inference')
assert 'VNNI' in bitnet['required_flags'], bitnet
" \
  && ok "workloads --json: 9 entries incl. bitnet-ternary requires VNNI" \
  || ko "workloads shape wrong"

# ---- advisory --json: severity enum + advisories list ----
set +e
out="$(python3 "${SCRIPT}" advisory --json 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "advisory rc ∈ {0,1} (got ${rc})"
else
  ko "advisory rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R272', d
assert d['severity'] in ('ok','attention','informational'), d
assert isinstance(d['advisories'], list)
" \
  && ok "advisory --json: severity enum constrained" \
  || ko "advisory shape wrong"

# ---- detect_avx512_extensions: live function ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('av','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ext = m.detect_avx512_extensions()
assert len(ext) == 16, ext
# Every key has a bool value
for k, v in ext.items():
    assert isinstance(v, bool), f'{k}={v!r} not bool'
" \
  && ok "detect_avx512_extensions: 16 boolean flags" \
  || ko "detect function wrong"

# ---- WORKLOAD_FIT structural contract ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('av','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for name, spec_ in m.WORKLOAD_FIT.items():
    for k in ('required','summary','operator_note'):
        assert k in spec_, f'{name} missing {k}'
    # Required flags must all exist in AVX512_FLAGS
    for f in spec_['required']:
        assert f in m.AVX512_FLAGS, f'{name} required={f!r} not in AVX512_FLAGS'
" \
  && ok "WORKLOAD_FIT contract: every required flag exists in AVX512_FLAGS" \
  || ko "WORKLOAD_FIT contract violated"

# ---- bitnet workload requires VNNI (verbatim master spec §17.1) ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('av','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
bw = m.WORKLOAD_FIT['bitnet-ternary-inference']
assert 'VNNI' in bw['required'], bw
assert 'Pulse' in bw['operator_note'], bw
" \
  && ok "bitnet-ternary workload: requires VNNI + cites Pulse tier" \
  || ko "bitnet workload meta wrong"

# ---- human render: banner + flag table ----
out_h="$(python3 "${SCRIPT}" probe 2>&1)"
echo "${out_h}" | grep -q "R272 sovereign-os avx512-advisor probe" \
  && ok "probe human banner present" || ko "banner missing"
echo "${out_h}" | grep -qE "avx512f " \
  && ok "probe human render shows AVX-512 F flag row" || ko "F flag missing"

# ---- workloads human render ----
out_h="$(python3 "${SCRIPT}" workloads 2>&1)"
echo "${out_h}" | grep -q "bitnet-ternary-inference" \
  && ok "workloads human shows bitnet-ternary-inference" || ko "workload row missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r272.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" avx512-advisor probe --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl avx512-advisor probe rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R272', d
" \
  && ok "osctl bridge surfaces R272 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" avx512-advisor nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown avx512-advisor subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_avx512_advisor: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
