#!/usr/bin/env bash
# tests/nspawn/test_memory_profile.sh — R257 (SDD-026 Z-17 follow-up).
# Per-DIMM XMP/EXPO verdict. rc=1 when ≥1 DIMM under-clocked.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/memory-profile.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_memory_profile.sh"
echo

[ -x "${SCRIPT}" ] && ok "memory-profile.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R257" "${SCRIPT}" && ok "memory-profile.py cites R257" || ko "R257 missing"
grep -q "^  memory-profile)" "${OSCTL}" \
  && ok "osctl bridges 'memory-profile'" || ko "osctl dispatch missing"
grep -q "memory-profile status" "${OSCTL}" \
  && ok "osctl help documents 'memory-profile'" || ko "osctl help missing"

# ---- status --json: stable shape regardless of dmidecode ----
set +e
out="$(python3 "${SCRIPT}" status --json 2>/dev/null)"
rc=$?
set -e
# rc=0 on CI (no DIMM data); rc=1 if any DIMM under-clocked on a real host.
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "status --json rc ∈ {0,1} (got ${rc})"
else
  ko "unexpected rc=${rc}"
fi
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R257', d
assert d['vector'].startswith('SDD-026 Z-17'), d
for f in ('baseboard_product','dimm_count','dimms','advisory'):
    assert f in d, f'missing {f}'
assert 'verdict' in d['advisory'], d
" \
  && ok "status --json: round + dimm_count + dimms + advisory shape" \
  || ko "status shape wrong"

# ---- advisory --json: verdict + actionable message OR no-data ----
out="$(python3 "${SCRIPT}" advisory --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R257', d
assert d['verdict'] in ('no-data','ok','xmp-expo-disabled','manually-overclocked'), d
" \
  && ok "advisory --json: verdict enum constrained" \
  || ko "advisory shape wrong"

# ---- unit-test the verdict logic via in-process import ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('mp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Synthetic DIMMs: rated 6000 MT/s, configured 4800 (JEDEC default)
synth = [
    {'slot':'DIMM_A1','size':'32 GB','type':'DDR5',
     'rated_mts':6000,'configured_mts':4800,
     'delta_pct':-20.0,'verdict':'underclocked-xmp-disabled',
     'manufacturer':'Test','part_number':'TEST'},
    {'slot':'DIMM_A2','size':'32 GB','type':'DDR5',
     'rated_mts':6000,'configured_mts':4800,
     'delta_pct':-20.0,'verdict':'underclocked-xmp-disabled',
     'manufacturer':'Test','part_number':'TEST'},
]
adv = m.derive_advisory(synth, 'ProArt X870E-CREATOR WIFI')
assert adv['verdict']=='xmp-expo-disabled', adv
assert adv['underclocked_count']==2, adv
assert adv['avg_recovery_mts']==1200, adv
assert 'EXPO' in adv['message'], adv  # AMD chipset → EXPO
"  \
  && ok "verdict logic: 2 DIMMs at 4800 vs rated 6000 → xmp-expo-disabled (AMD EXPO)" \
  || ko "verdict logic wrong"

python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('mp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Synthetic: configured == rated → ok
synth = [{'slot':'DIMM_A1','rated_mts':6000,'configured_mts':6000,'verdict':'at-rated'}]
adv = m.derive_advisory(synth, None)
assert adv['verdict']=='ok', adv
"  \
  && ok "verdict logic: configured==rated → ok" \
  || ko "ok-verdict logic wrong"

python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('mp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Synthetic: configured > rated → manually-overclocked
synth = [{'slot':'DIMM_A1','rated_mts':6000,'configured_mts':7200,'verdict':'manually-overclocked'}]
adv = m.derive_advisory(synth, None)
assert adv['verdict']=='manually-overclocked', adv
assert 'memtest' in adv['message'].lower(), adv
"  \
  && ok "verdict logic: overclocked → memtest86+ hint" \
  || ko "overclock advisory wrong"

# ---- Intel chipset hint ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('mp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
synth = [
    {'slot':'DIMM_A1','rated_mts':7200,'configured_mts':5600,
     'delta_pct':-22.2,'verdict':'underclocked-xmp-disabled'},
]
adv = m.derive_advisory(synth, 'Z790-PRO WIFI')
assert 'XMP' in adv['message'], adv  # Intel chipset → XMP not EXPO
"  \
  && ok "verdict logic: Intel chipset → 'XMP' in message" \
  || ko "Intel-XMP hint wrong"

# ---- parse_mts helper ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('mp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.parse_mts('6000 MT/s') == 6000
assert m.parse_mts('Unknown') is None
assert m.parse_mts('') is None
assert m.parse_mts('5600') == 5600
"  \
  && ok "parse_mts helper: '6000 MT/s' / 'Unknown' / '' edge cases" \
  || ko "parse_mts wrong"

# ---- human render: banner ----
out_h="$(python3 "${SCRIPT}" status 2>&1 || true)"
echo "${out_h}" | grep -q "R257 sovereign-os memory-profile" \
  && ok "human render carries R257 banner" || ko "banner missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r257.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" memory-profile advisory --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl memory-profile advisory rc ∈ {0,1} (got ${rc})"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R257', d
" \
  && ok "osctl bridge surfaces R257 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" memory-profile nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown memory-profile subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_memory_profile: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
